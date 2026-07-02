from csv import DictReader
from pathlib import Path
from typing import Any

import httpx
from psycopg.types.json import Json

from app.config import settings
from app.db import get_connection

SEED_CSV = Path(__file__).resolve().parents[1] / "data" / "train_station_seed.csv"
BAIDU_PLACE_REGION_URL = "https://api.map.baidu.com/place/v3/region"
AMAP_PLACE_TEXT_URL = "https://restapi.amap.com/v5/place/text"
USER_AGENT = "SEMAP train station coordinate lookup/1.0 (https://semap.xyz)"


class CoordinateLookupFailure(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class BaiduQuotaExceeded(Exception):
    pass


class AmapQuotaExceeded(Exception):
    pass


def normalize_station_name(value: str) -> str:
    name = "".join(value.split())
    return name[:-1] if name.endswith("站") else name


def parse_12306_station_names(text: str) -> list[dict[str, Any]]:
    payload = text.partition("'")[2].rpartition("'")[0] if "'" in text else text
    stations: list[dict[str, Any]] = []
    for raw_record in payload.split("@"):
        if not raw_record:
            continue
        fields = raw_record.split("|")
        if len(fields) < 6 or not fields[1]:
            continue
        try:
            sequence_no = int(fields[5])
        except ValueError:
            sequence_no = None
        stations.append(
            {
                "name": normalize_station_name(fields[1]),
                "telecode": fields[2] or None,
                "pinyin": fields[3] or None,
                "short_pinyin": fields[4] or None,
                "sequence_no": sequence_no,
                "city": fields[7] if len(fields) > 7 and fields[7] else None,
            }
        )
    return stations


def upsert_12306_stations(stations: list[dict[str, Any]]) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            for station in stations:
                cur.execute(
                    """
                    insert into train_stations (
                        name, telecode, pinyin, short_pinyin, sequence_no, city
                    )
                    values (%s, %s, %s, %s, %s, %s)
                    on conflict (name) do update set
                        telecode = excluded.telecode,
                        pinyin = excluded.pinyin,
                        short_pinyin = excluded.short_pinyin,
                        sequence_no = excluded.sequence_no,
                        city = excluded.city,
                        updated_at = now()
                    """,
                    (
                        station["name"],
                        station.get("telecode"),
                        station.get("pinyin"),
                        station.get("short_pinyin"),
                        station.get("sequence_no"),
                        station.get("city"),
                    ),
                )
        conn.commit()
    return len(stations)


def import_station_seed(path: Path = SEED_CSV) -> int:
    with path.open(encoding="utf-8", newline="") as file:
        rows = list(DictReader(file))

    with get_connection() as conn:
        with conn.cursor() as cur:
            for row in rows:
                name = normalize_station_name(row["name"])
                raw = {
                    "source": row.get("coordinate_source") or "seed",
                    "query": row.get("coordinate_query") or f"{name}站",
                }
                cur.execute(
                    """
                    insert into train_stations (
                        name, lat, lng, coordinate_source, coordinate_status,
                        coordinate_query, coordinate_raw
                    )
                    values (%s, %s, %s, %s, 'verified', %s, %s)
                    on conflict (name) do update set
                        lat = excluded.lat,
                        lng = excluded.lng,
                        coordinate_source = excluded.coordinate_source,
                        coordinate_status = 'verified',
                        coordinate_query = excluded.coordinate_query,
                        coordinate_raw = excluded.coordinate_raw,
                        updated_at = now()
                    """,
                    (
                        name,
                        float(row["lat"]),
                        float(row["lng"]),
                        row.get("coordinate_source") or "seed",
                        row.get("coordinate_query") or f"{name}站",
                        Json(raw),
                    ),
                )
        conn.commit()
    return len(rows)


def train_station_row(name: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select name, city, lat, lng, coordinate_source, coordinate_status,
                       coordinate_query, coordinate_raw
                from train_stations
                where name = %s
                """,
                (normalize_station_name(name),),
            )
            return cur.fetchone()


def row_coordinate(row: dict[str, Any]) -> tuple[float, float, dict[str, Any]] | None:
    if (
        row["coordinate_status"] != "verified"
        or row["lat"] is None
        or row["lng"] is None
    ):
        return None
    return row["lat"], row["lng"], {
        "source": row["coordinate_source"],
        "station": row["name"],
        "query": row["coordinate_query"],
        "raw": row["coordinate_raw"],
    }


def train_station_coordinate(
    station: str,
    resolve_missing: bool = False,
) -> tuple[float, float, dict[str, Any]] | None:
    name = normalize_station_name(station)
    row = train_station_row(name)
    if not row:
        return None
    coordinate = row_coordinate(row)
    if coordinate or not resolve_missing:
        return coordinate
    return resolve_station_coordinate(row)


def in_china_bbox(lat: float, lng: float) -> bool:
    return 18 <= lat <= 54 and 73 <= lng <= 135


def baidu_result_location(result: dict[str, Any]) -> tuple[float, float] | None:
    location = result.get("location") or {}
    try:
        lat = float(location["lat"])
        lng = float(location["lng"])
    except (KeyError, TypeError, ValueError):
        return None
    return (lat, lng) if in_china_bbox(lat, lng) else None


def baidu_result_matches_station(name: str, result: dict[str, Any]) -> bool:
    if not baidu_result_location(result):
        return False
    detail = result.get("detail_info") or {}
    poi_type = " ".join(
        str(value)
        for value in [
            result.get("tag"),
            detail.get("tag"),
            detail.get("label"),
            detail.get("classified_poi_tag"),
            detail.get("type"),
        ]
        if value
    )
    if not any(keyword in poi_type for keyword in ["火车站", "铁路", "高铁", "动车", "城际"]):
        return False

    result_name = str(result.get("name") or "")
    targets = [name, f"{name}站", f"{name}火车站"]
    return any(target in result_name for target in targets)


def baidu_api_key() -> str:
    key = settings.baidu_maps_api_key.strip()
    return "" if key in {"", "change-me", "missing"} else key


def amap_api_key() -> str:
    key = settings.amap_maps_api_key.strip()
    return "" if key in {"", "change-me", "missing"} else key


def baidu_place_search(
    client: httpx.Client,
    name: str,
    city: str | None,
    api_key: str,
) -> tuple[float, float, dict[str, Any] | None]:
    query = f"{name}站"
    region = city or "全国"
    response = client.get(
        BAIDU_PLACE_REGION_URL,
        params={
            "query": query,
            "region": region,
            "region_limit": "true" if city else "false",
            "output": "json",
            "ak": api_key,
            "scope": "2",
            "page_size": "10",
            "ret_coordtype": "gcj02ll",
        },
    )
    response.raise_for_status()
    data = response.json()
    if data.get("status") != 0:
        message = str(data.get("message") or data.get("msg") or data.get("status"))
        if any(keyword in message.lower() for keyword in ["配额", "quota", "limit"]):
            raise BaiduQuotaExceeded(message)
        raise CoordinateLookupFailure(message)

    results = data.get("results") or []
    accepted = next((item for item in results if baidu_result_matches_station(name, item)), None)
    if not accepted:
        return 0.0, 0.0, {
            "query": query,
            "region": region,
            "coordinateSystem": "gcj02",
            "results": results,
        }

    lat, lng = baidu_result_location(accepted) or (0.0, 0.0)
    raw = {
        "query": query,
        "region": region,
        "coordinateSystem": "gcj02",
        "result": accepted,
    }
    return lat, lng, raw


def amap_result_location(result: dict[str, Any]) -> tuple[float, float] | None:
    location = str(result.get("location") or "")
    try:
        lng_text, lat_text = location.split(",", 1)
        lat = float(lat_text)
        lng = float(lng_text)
    except ValueError:
        return None
    return (lat, lng) if in_china_bbox(lat, lng) else None


def amap_result_matches_station(name: str, result: dict[str, Any]) -> bool:
    if not amap_result_location(result):
        return False
    poi_type = " ".join(str(value) for value in [result.get("type"), result.get("typecode")] if value)
    if not any(keyword in poi_type for keyword in ["火车站", "铁路", "150200"]):
        return False
    result_name = str(result.get("name") or "")
    targets = [name, f"{name}站", f"{name}火车站"]
    return any(target in result_name for target in targets)


def amap_place_search(
    client: httpx.Client,
    name: str,
    city: str | None,
    api_key: str,
) -> tuple[float, float, dict[str, Any] | None]:
    query = f"{name}站"
    response = client.get(
        AMAP_PLACE_TEXT_URL,
        params={
            "key": api_key,
            "keywords": query,
            "types": "150200",
            "region": city or "",
            "city_limit": "true" if city else "false",
            "page_size": "10",
            "page_num": "1",
            "output": "json",
        },
    )
    response.raise_for_status()
    data = response.json()
    if data.get("status") != "1":
        message = str(data.get("info") or data.get("infocode") or data.get("status"))
        if any(keyword in message.lower() for keyword in ["quota", "limit", "daily", "访问已超出"]):
            raise AmapQuotaExceeded(message)
        raise CoordinateLookupFailure(message)

    pois = data.get("pois") or []
    accepted = next((item for item in pois if amap_result_matches_station(name, item)), None)
    raw_base = {
        "query": query,
        "region": city or "",
        "coordinateSystem": "gcj02",
    }
    if not accepted:
        return 0.0, 0.0, {**raw_base, "pois": pois}

    lat, lng = amap_result_location(accepted) or (0.0, 0.0)
    return lat, lng, {**raw_base, "result": accepted}


def coordinate_source_tried(row: dict[str, Any], source: str) -> bool:
    raw = row.get("coordinate_raw") or {}
    attempts = raw.get("attempts") if isinstance(raw, dict) else None
    return row.get("coordinate_source") == source or (isinstance(attempts, dict) and source in attempts)


def resolve_station_coordinate(row: dict[str, Any]) -> tuple[float, float, dict[str, Any]] | None:
    failures: list[str] = []
    for source, resolver in [
        ("amap_place", resolve_station_coordinate_with_amap),
        ("baidu_place", resolve_station_coordinate_with_baidu),
    ]:
        if coordinate_source_tried(row, source):
            continue
        try:
            coordinate = resolver(row["name"], row["city"])
        except CoordinateLookupFailure as error:
            failures.append(error.message)
            continue
        if coordinate:
            return coordinate

    if failures:
        raise CoordinateLookupFailure("；".join(failures))
    return None


def resolve_station_coordinate_with_amap(name: str, city: str | None) -> tuple[float, float, dict[str, Any]] | None:
    key = amap_api_key()
    if not key:
        return None

    try:
        with httpx.Client(timeout=20, trust_env=False, headers={"User-Agent": USER_AGENT}) as client:
            result = amap_place_search(client, name, city, key)
    except AmapQuotaExceeded as error:
        raise CoordinateLookupFailure(f"高德地图坐标查询已超出配额：{error}") from error
    except (httpx.HTTPError, ValueError, CoordinateLookupFailure) as error:
        raise CoordinateLookupFailure(f"高德地图坐标查询失败：{error}") from error

    lat, lng, raw = result
    if raw.get("result"):
        save_station_coordinate(name, lat, lng, "amap_place", raw["query"], raw)
        return train_station_coordinate(name)

    save_station_coordinate_miss(name, "amap_place", raw["query"], raw)
    return None


def resolve_station_coordinate_with_baidu(name: str, city: str | None) -> tuple[float, float, dict[str, Any]] | None:
    key = baidu_api_key()
    if not key:
        return None

    try:
        with httpx.Client(timeout=20, trust_env=False, headers={"User-Agent": USER_AGENT}) as client:
            result = baidu_place_search(client, name, city, key)
    except BaiduQuotaExceeded as error:
        raise CoordinateLookupFailure(f"百度地图坐标查询已超出当日配额：{error}") from error
    except (httpx.HTTPError, ValueError, CoordinateLookupFailure) as error:
        raise CoordinateLookupFailure(f"百度地图坐标查询失败：{error}") from error

    lat, lng, raw = result
    if raw.get("result"):
        save_station_coordinate(name, lat, lng, "baidu_place", raw["query"], raw)
        return train_station_coordinate(name)

    save_station_coordinate_miss(name, "baidu_place", raw["query"], raw)
    return None


def missing_coordinate_station_rows(limit: int, skipped_source: str | None = None) -> list[dict[str, str | None]]:
    source_filter = "" if skipped_source is None else "and coordinate_source is distinct from %s"
    params: tuple[Any, ...] = (limit,) if skipped_source is None else (skipped_source, limit)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select name, city
                from train_stations
                where coordinate_status = 'missing'
                  {source_filter}
                order by sequence_no nulls last, name
                limit %s
                """,
                params,
            )
            return [{"name": row["name"], "city": row["city"]} for row in cur.fetchall()]


def missing_coordinate_stations(limit: int) -> list[str]:
    return [row["name"] for row in missing_coordinate_station_rows(limit)]


def save_station_coordinate(
    name: str,
    lat: float,
    lng: float,
    source: str,
    query: str,
    raw: dict[str, Any],
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update train_stations
                set lat = %s,
                    lng = %s,
                    coordinate_source = %s,
                    coordinate_status = 'verified',
                    coordinate_query = %s,
                    coordinate_raw = %s,
                    updated_at = now()
                where name = %s
                """,
                (lat, lng, source, query, Json(raw), normalize_station_name(name)),
            )
        conn.commit()


def save_station_coordinate_miss(name: str, source: str, query: str, raw: dict[str, Any]) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select coordinate_source, coordinate_raw from train_stations where name = %s",
                (normalize_station_name(name),),
            )
            row = cur.fetchone()
            attempts: dict[str, Any] = {}
            if row and isinstance(row["coordinate_raw"], dict):
                old_raw = row["coordinate_raw"]
                if isinstance(old_raw.get("attempts"), dict):
                    attempts.update(old_raw["attempts"])
                elif row["coordinate_source"]:
                    attempts[row["coordinate_source"]] = old_raw
            attempts[source] = raw
            cur.execute(
                """
                update train_stations
                set lat = null,
                    lng = null,
                    coordinate_source = 'lookup_miss',
                    coordinate_status = 'missing',
                    coordinate_query = %s,
                    coordinate_raw = %s,
                    updated_at = now()
                where name = %s
                """,
                (query, Json({"attempts": attempts}), normalize_station_name(name)),
            )
        conn.commit()


def reject_station_coordinate(name: str, source: str, query: str, raw: dict[str, Any]) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update train_stations
                set coordinate_source = %s,
                    coordinate_status = 'rejected',
                    coordinate_query = %s,
                    coordinate_raw = %s,
                    updated_at = now()
                where name = %s
                """,
                (source, query, Json(raw), normalize_station_name(name)),
            )
        conn.commit()


def station_coverage() -> dict[str, int]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select count(*) as value from train_stations")
            total = cur.fetchone()["value"]
            cur.execute(
                """
                select count(*) as value
                from train_stations
                where coordinate_status = 'verified' and lat is not null and lng is not null
                """
            )
            verified = cur.fetchone()["value"]
            cur.execute("select count(*) as value from train_stations where coordinate_status = 'rejected'")
            rejected = cur.fetchone()["value"]
    return {"total": total, "verified": verified, "missing": total - verified, "rejected": rejected}
