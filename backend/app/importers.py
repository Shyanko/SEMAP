from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from html import unescape
from pathlib import Path
import re
from typing import Any

import httpx

from app.config import settings
from app.train_station_coordinates import TRAIN_STATION_COORDINATES

FR24_BASE_URL = "https://fr24api.flightradar24.com/api"
CHINA_TZ = timezone(timedelta(hours=8))
RAILWAY_12306_LOGO_URL = "/logos/China_Railways.svg"
IATA_CODE_SEARCH_URL = "https://www.iata.org/en/publications/directories/code-search/"
AIRLINE_LOGO_BASE_URL = "https://images.kiwi.com/airlines/64"
AIRLINE_LOGO_CACHE_DIR = Path("/var/cache/semap/airline_logos")


class ImportFailure(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class ImportedPoint:
    sequence: int
    lat: float
    lng: float
    altitude: float | None = None
    speed: float | None = None
    recorded_at: datetime | None = None
    name: str | None = None
    raw: dict[str, Any] | None = None


@dataclass
class ImportedSegment:
    title: str
    source_type: str
    transport_type: str
    external_code: str
    started_at: datetime | None
    ended_at: datetime | None
    summary: str
    is_approximate: bool
    metadata: dict[str, Any]
    points: list[ImportedPoint]
    response_payload: dict[str, Any]


@dataclass
class TrainStations:
    train_code: str
    requested_date: date
    query_date: date
    stations: list[dict[str, Any]]


def parse_fr24_token(value: str) -> str:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    for index, line in enumerate(lines[:-1]):
        if line.lower() == "token":
            return lines[index + 1]
    return next((line for line in lines if "|" in line), value.strip())


def fr24_headers() -> dict[str, str]:
    token = parse_fr24_token(settings.fr24_api_token)
    if not token or token == "change-me":
        raise ImportFailure("缺少 FlightRadar24 token")
    return {
        "Accept": "application/json",
        "Accept-Version": "v1",
        "Authorization": f"Bearer {token}",
    }


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def request_json(
    client: httpx.Client,
    url: str,
    failure_message: str,
    **kwargs: Any,
) -> tuple[httpx.Response, Any]:
    try:
        response = client.get(url, **kwargs)
    except httpx.TimeoutException as error:
        raise ImportFailure(f"{failure_message}：请求超时") from error
    except httpx.HTTPError as error:
        raise ImportFailure(f"{failure_message}：{error}") from error

    try:
        data = response.json()
    except ValueError as error:
        raise ImportFailure(f"{failure_message}：HTTP {response.status_code}，外部服务返回了非 JSON 响应") from error
    return response, data


def request_text(
    client: httpx.Client,
    url: str,
    failure_message: str,
    **kwargs: Any,
) -> tuple[httpx.Response, str]:
    try:
        response = client.get(url, **kwargs)
    except httpx.TimeoutException as error:
        raise ImportFailure(f"{failure_message}：请求超时") from error
    except httpx.HTTPError as error:
        raise ImportFailure(f"{failure_message}：{error}") from error
    return response, response.text


def response_error(data: dict[str, Any]) -> str:
    for key in ("error", "error_message", "message", "msg", "status"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return "没有返回错误详情"


def flight_airline_code(flight_code: str) -> str | None:
    match = re.match(r"^[A-Z]{2,3}", flight_code)
    return match.group(0) if match else None


def normalized_airline_logo_code(code: str | None) -> str | None:
    if not code:
        return None
    normalized = code.upper()
    return normalized if re.fullmatch(r"[A-Z0-9]{2,3}", normalized) else None


def airline_logo_url(code: str | None) -> str | None:
    normalized = normalized_airline_logo_code(code)
    if not normalized:
        return None
    return f"/api/assets/airline-logos/{normalized}.png"


def cached_airline_logo_path(code: str) -> Path:
    normalized = normalized_airline_logo_code(code)
    if not normalized:
        raise ImportFailure("航司 logo 代码无效", 404)
    AIRLINE_LOGO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = AIRLINE_LOGO_CACHE_DIR / f"{normalized}.png"
    if path.is_file():
        return path

    with httpx.Client(timeout=12, trust_env=False, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
        try:
            response = client.get(f"{AIRLINE_LOGO_BASE_URL}/{normalized}.png")
        except httpx.TimeoutException as error:
            raise ImportFailure("航司 logo 获取失败：请求超时", 504) from error
        except httpx.HTTPError as error:
            raise ImportFailure(f"航司 logo 获取失败：{error}", 502) from error
    content_type = response.headers.get("content-type", "")
    if response.status_code != 200 or not content_type.startswith("image/") or not response.content:
        raise ImportFailure(f"未找到航司 logo：{normalized}", 404)
    path.write_bytes(response.content)
    return path


def text_from_cell(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", value))).strip()


def parse_iata_airport_location(html: str, code: str) -> str | None:
    target = code.upper()
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.DOTALL | re.IGNORECASE):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.DOTALL | re.IGNORECASE)
        if len(cells) < 3:
            continue
        city, airport, location_code = [text_from_cell(cell) for cell in cells[:3]]
        if location_code.upper() == target and city and airport:
            return f"{city} {airport}"
    return None


def parse_iata_airline_name(html: str, code: str) -> str | None:
    target = code.upper()
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.DOTALL | re.IGNORECASE):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.DOTALL | re.IGNORECASE)
        if len(cells) < 3:
            continue
        company_name, _country, airline_code = [text_from_cell(cell) for cell in cells[:3]]
        if airline_code.upper() == target and company_name:
            return company_name
    return None


def iata_airport_location(code: str) -> str | None:
    with httpx.Client(timeout=20, trust_env=False, headers={"User-Agent": "Mozilla/5.0"}) as client:
        try:
            response, html = request_text(
                client,
                IATA_CODE_SEARCH_URL,
                f"IATA 机场代码查询失败：{code}",
                params={"airport.search": code},
            )
        except ImportFailure:
            return None
    if response.status_code != 200:
        return None
    return parse_iata_airport_location(html, code)


def iata_airline_name(code: str) -> str | None:
    with httpx.Client(timeout=20, trust_env=False, headers={"User-Agent": "Mozilla/5.0"}) as client:
        response, html = request_text(
            client,
            IATA_CODE_SEARCH_URL,
            f"IATA 航司代码查询失败：{code}",
            params={"airline.search": code},
            follow_redirects=True,
        )
    if response.status_code != 200:
        raise ImportFailure(f"IATA 航司代码查询失败：{code}。HTTP {response.status_code}")
    name = parse_iata_airline_name(html, code)
    if not name:
        raise ImportFailure(f"IATA 未找到航司代码：{code}", 404)
    return name


def airport_location(code: str | None) -> str | None:
    if not code:
        return None
    return iata_airport_location(code) or code


def flight_metadata(
    flight_code: str,
    flight: dict[str, Any],
    origin_location: str | None = None,
    destination_location: str | None = None,
) -> dict[str, Any]:
    airline_code = flight_airline_code(flight_code)
    operator_code = flight.get("painted_as") or flight.get("operating_as") or airline_code
    operator_name = iata_airline_name(airline_code or operator_code) if airline_code or operator_code else None
    metadata = {
        "vehicleModel": flight.get("type"),
        "registration": flight.get("reg"),
        "operatorName": operator_name,
        "operatorCode": airline_code or operator_code,
        "originLocation": origin_location,
        "destinationLocation": destination_location,
        "logoKind": "airline",
        "logoUrl": airline_logo_url(airline_code),
        "logoText": airline_code or operator_code,
    }
    return {key: value for key, value in metadata.items() if value}


def train_vehicle_model(emu_no: str | None) -> str | None:
    if not emu_no:
        return None
    value = emu_no.strip()
    return value[:-4] if len(value) > 4 else value


def fetch_train_unit_record(train_code: str) -> dict[str, Any] | None:
    with httpx.Client(timeout=12, trust_env=False, headers={"User-Agent": "Mozilla/5.0"}) as client:
        try:
            response, data = request_json(
                client,
                f"https://api.rail.re/train/{train_code}",
                "rail.re 担当车型查询失败",
            )
        except ImportFailure:
            return None
    if response.status_code != 200 or not isinstance(data, list) or not data:
        return None
    first = data[0]
    return first if isinstance(first, dict) else None


def train_metadata(train_code: str) -> dict[str, Any]:
    unit_record = fetch_train_unit_record(train_code)
    emu_no = unit_record.get("emu_no") if unit_record else None
    metadata: dict[str, Any] = {
        "vehicleModel": train_vehicle_model(emu_no),
        "unitNo": emu_no,
        "operatorCode": "12306",
        "logoKind": "railway_12306",
        "logoUrl": RAILWAY_12306_LOGO_URL,
        "logoText": "12306",
    }
    if unit_record:
        metadata["railRe"] = unit_record
    return {key: value for key, value in metadata.items() if value}


def geocode(address: str) -> tuple[float, float, dict[str, Any]]:
    if not settings.google_maps_api_key or settings.google_maps_api_key == "change-me":
        raise ImportFailure("缺少 GOOGLE_MAPS_API_KEY")

    with httpx.Client(timeout=20, trust_env=False) as client:
        response, data = request_json(
            client,
            "https://maps.googleapis.com/maps/api/geocode/json",
            f"无法解析坐标：{address}",
            params={"address": address, "key": settings.google_maps_api_key},
        )
    if response.status_code != 200 or data.get("status") != "OK" or not data.get("results"):
        raise ImportFailure(f"无法解析坐标：{address}。Google Geocoding 返回：{response_error(data)}")

    location = data["results"][0]["geometry"]["location"]
    return location["lat"], location["lng"], {
        "address": address,
        "place_id": data["results"][0].get("place_id"),
        "formatted_address": data["results"][0].get("formatted_address"),
    }


def train_station_coordinate(station: str) -> tuple[float, float, dict[str, Any]]:
    name = normalize_station_name(station)
    if name in TRAIN_STATION_COORDINATES:
        lat, lng = TRAIN_STATION_COORDINATES[name]
        return lat, lng, {"source": "local_train_station_coordinates", "station": name}
    return geocode(f"{name}站")


def resolve_flight_import(flight_number: str, flight_date: date) -> ImportedSegment:
    flight_code = flight_number.strip().upper().replace(" ", "")
    if not flight_code:
        raise ImportFailure("请输入航班号", 400)

    start = datetime.combine(flight_date, time.min).strftime("%Y-%m-%dT%H:%M:%S")
    end = datetime.combine(flight_date + timedelta(days=1), time.min).strftime("%Y-%m-%dT%H:%M:%S")
    params = {
        "flight_datetime_from": start,
        "flight_datetime_to": end,
        "flights": flight_code,
        "limit": "10",
    }

    with httpx.Client(timeout=30, trust_env=False) as client:
        response, data = request_json(
            client,
            f"{FR24_BASE_URL}/flight-summary/full",
            "FlightRadar24 航班查询失败",
            headers=fr24_headers(),
            params=params,
        )
    if response.status_code in {401, 403}:
        raise ImportFailure("当前 FlightRadar24 token 无权访问航班摘要接口")
    if response.status_code != 200:
        raise ImportFailure(f"FlightRadar24 航班查询失败：HTTP {response.status_code}，{response_error(data)}")

    records = data.get("data") or []
    flight = next((item for item in records if item.get("flight") == flight_code), None)
    if not flight:
        raise ImportFailure(f"未找到 {flight_date.isoformat()} 的 {flight_code} 航班记录", 404)

    origin = flight.get("orig_iata") or flight.get("orig_icao")
    destination = flight.get("dest_iata_actual") or flight.get("dest_iata") or flight.get("dest_icao_actual") or flight.get("dest_icao")
    if not origin or not destination:
        raise ImportFailure(f"FlightRadar24 未返回 {flight_code} 的起降机场")

    origin_location = airport_location(origin)
    destination_location = airport_location(destination)
    origin_lat, origin_lng, origin_raw = geocode(f"{origin} airport")
    dest_lat, dest_lng, dest_raw = geocode(f"{destination} airport")
    started_at = parse_datetime(flight.get("datetime_takeoff") or flight.get("first_seen"))
    ended_at = parse_datetime(flight.get("datetime_landed") or flight.get("last_seen"))

    live_point = live_flight_point(flight_code, flight_date)
    points = [
        ImportedPoint(0, origin_lat, origin_lng, recorded_at=started_at, name=origin, raw=origin_raw),
    ]
    if live_point:
        live_point.sequence = 1
        points.append(live_point)
    points.append(
        ImportedPoint(
            len(points),
            dest_lat,
            dest_lng,
            recorded_at=ended_at,
            name=destination,
            raw=dest_raw,
        )
    )

    return ImportedSegment(
        title=f"{flight_code} {origin}-{destination}",
        source_type="flight",
        transport_type="flight",
        external_code=flight_code,
        started_at=started_at,
        ended_at=ended_at,
        summary="按 FlightRadar24 航班摘要和起降机场坐标近似生成。",
        is_approximate=True,
        metadata=flight_metadata(flight_code, flight, origin_location, destination_location),
        points=points,
        response_payload={"summary": flight, "livePointUsed": live_point is not None},
    )


def live_flight_point(flight_code: str, flight_date: date) -> ImportedPoint | None:
    if flight_date != datetime.now(timezone.utc).date():
        return None
    with httpx.Client(timeout=20, trust_env=False) as client:
        try:
            response, data = request_json(
                client,
                f"{FR24_BASE_URL}/live/flight-positions/full",
                "FlightRadar24 实时位置查询失败",
                headers=fr24_headers(),
                params={"flights": flight_code},
            )
        except ImportFailure:
            return None
    if response.status_code != 200:
        return None
    rows = data.get("data") or []
    row = next((item for item in rows if item.get("flight") == flight_code), None)
    if not row or row.get("lat") is None or row.get("lon") is None:
        return None
    return ImportedPoint(
        sequence=1,
        lat=row["lat"],
        lng=row["lon"],
        altitude=row.get("alt"),
        speed=row.get("gspeed"),
        recorded_at=parse_datetime(row.get("timestamp")),
        name="实时位置",
        raw=row,
    )


def normalize_station_name(value: str) -> str:
    name = "".join(value.split())
    return name[:-1] if name.endswith("站") else name


def select_train_rows(
    rows: list[dict[str, Any]],
    from_station: str,
    to_station: str,
) -> list[dict[str, Any]]:
    start_name = normalize_station_name(from_station)
    end_name = normalize_station_name(to_station)
    start_index = next(
        (index for index, row in enumerate(rows) if normalize_station_name(row.get("station_name", "")) == start_name),
        None,
    )
    end_index = next(
        (index for index, row in enumerate(rows) if normalize_station_name(row.get("station_name", "")) == end_name),
        None,
    )
    if start_index is None:
        available = "、".join(row.get("station_name", "") for row in rows)
        raise ImportFailure(f"车次经停站中没有乘车起点：{from_station}。经停站为：{available}", 404)
    if end_index is None:
        available = "、".join(row.get("station_name", "") for row in rows)
        raise ImportFailure(f"车次经停站中没有乘车终点：{to_station}。经停站为：{available}", 404)
    if start_index >= end_index:
        raise ImportFailure("乘车终点必须在起点之后", 400)
    return rows[start_index : end_index + 1]


def train_query_dates(requested_date: date) -> list[date]:
    dates = [requested_date]
    server_today = datetime.now(CHINA_TZ).date()
    for offset in range(8):
        fallback_date = server_today + timedelta(days=offset)
        if fallback_date not in dates:
            dates.append(fallback_date)
    return dates


def fetch_train_rows(
    client: httpx.Client,
    code: str,
    query_date: date,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str | None]:
    search_response, search_data = request_json(
        client,
        "https://search.12306.cn/search/v1/train/search",
        "12306 车次搜索失败",
        params={"keyword": code, "date": query_date.strftime("%Y%m%d")},
    )
    matches = search_data.get("data") or []
    match = next((item for item in matches if item.get("station_train_code") == code), None)
    if search_response.status_code != 200:
        return None, [], f"{query_date.isoformat()} 搜索 {code} 失败：HTTP {search_response.status_code}，{response_error(search_data)}"
    if not match:
        return None, [], f"{query_date.isoformat()} 未找到 {code}"

    detail_response, detail_data = request_json(
        client,
        "https://kyfw.12306.cn/otn/queryTrainInfo/query",
        "12306 经停站查询失败",
        params={
            "leftTicketDTO.train_no": match["train_no"],
            "leftTicketDTO.train_date": query_date.strftime("%Y-%m-%d"),
            "rand_code": "",
        },
    )
    rows = detail_data.get("data", {}).get("data") or []
    if detail_response.status_code != 200:
        return match, [], f"{query_date.isoformat()} 查询 {code} 经停站失败：HTTP {detail_response.status_code}，{response_error(detail_data)}"
    if len(rows) < 2:
        return match, [], f"{query_date.isoformat()} 的 {code} 没有有效经停站：{response_error(detail_data)}"
    return match, rows, None


def resolve_train_import(
    train_code: str,
    travel_date: date,
    from_station: str,
    to_station: str,
) -> ImportedSegment:
    code = train_code.strip().upper()
    if not code:
        raise ImportFailure("请输入车次号", 400)
    if not normalize_station_name(from_station) or not normalize_station_name(to_station):
        raise ImportFailure("请输入乘车起止站", 400)

    query_failures: list[str] = []
    with httpx.Client(timeout=30, trust_env=False, headers={"User-Agent": "Mozilla/5.0"}) as client:
        for query_date in train_query_dates(travel_date):
            match, rows, failure = fetch_train_rows(client, code, query_date)
            if match and rows:
                break
            if failure:
                query_failures.append(failure)
        else:
            detail = "；".join(query_failures)
            raise ImportFailure(f"未找到可用车次：{detail}", 404)

    selected_rows = select_train_rows(rows, from_station, to_station)
    points: list[ImportedPoint] = []
    for index, row in enumerate(selected_rows):
        station = row["station_name"]
        lat, lng, raw = train_station_coordinate(station)
        points.append(
            ImportedPoint(
                sequence=index,
                lat=lat,
                lng=lng,
                recorded_at=train_station_time(
                    travel_date,
                    row,
                    prefer_arrival=index == len(selected_rows) - 1,
                ),
                name=station if index in {0, len(selected_rows) - 1} else None,
                raw={"station": row, "geocode": raw},
            )
        )

    start_name = selected_rows[0]["station_name"]
    end_name = selected_rows[-1]["station_name"]
    return ImportedSegment(
        title=f"{code} {start_name}-{end_name}",
        source_type="train",
        transport_type="train",
        external_code=code,
        started_at=points[0].recorded_at,
        ended_at=points[-1].recorded_at,
        summary=f"按 {travel_date.isoformat()} 的 12306 车次信息近似生成，区间为 {start_name} 到 {end_name}。",
        is_approximate=True,
        metadata=train_metadata(code),
        points=points,
        response_payload={"search": match, "stations": rows, "selectedStations": selected_rows},
    )


def resolve_train_stations(train_code: str, travel_date: date) -> TrainStations:
    code = train_code.strip().upper()
    if not code:
        raise ImportFailure("请输入车次号", 400)

    query_failures: list[str] = []
    with httpx.Client(timeout=30, trust_env=False, headers={"User-Agent": "Mozilla/5.0"}) as client:
        for query_date in train_query_dates(travel_date):
            _match, rows, failure = fetch_train_rows(client, code, query_date)
            if rows:
                return TrainStations(
                    train_code=code,
                    requested_date=travel_date,
                    query_date=query_date,
                    stations=rows,
                )
            if failure:
                query_failures.append(failure)

    detail = "；".join(query_failures)
    raise ImportFailure(f"未找到可用车次：{detail}", 404)


def train_station_time(
    base_date: date,
    row: dict[str, Any],
    prefer_arrival: bool = False,
) -> datetime | None:
    value = row.get("arrive_time") if prefer_arrival else row.get("start_time")
    if not value or value == "----":
        value = row.get("start_time") if prefer_arrival else row.get("arrive_time")
    if not value or value == "----":
        return None
    hour, minute = [int(part) for part in value.split(":")]
    day_diff = int(row.get("arrive_day_diff") or 0)
    return datetime.combine(base_date + timedelta(days=day_diff), time(hour, minute), CHINA_TZ)
