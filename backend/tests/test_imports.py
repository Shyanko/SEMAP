from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

import app.importers as importers
from app.db import get_connection
from app.importers import (
    ImportedPoint,
    ImportedSegment,
    ImportFailure,
    parse_iata_airline_name,
    parse_iata_airport_location,
    select_train_rows,
    train_query_dates,
)
from app.main import app
from app.migrate import run_migrations
from app.train_stations import import_station_seed

client = TestClient(app)


def create_user() -> tuple[str, dict]:
    username = f"user_{uuid4().hex[:12]}"
    password = "password123"
    client.post("/api/auth/register", json={"username": username, "password": password})
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    return username, {"Authorization": f"Bearer {response.json()['accessToken']}"}


def delete_account(username: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from accounts where username = %s", (username,))
        conn.commit()


def upsert_test_station(name: str, lat: float, lng: float) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into train_stations (
                    name, lat, lng, coordinate_source, coordinate_status, coordinate_query
                )
                values (%s, %s, %s, 'test', 'verified', %s)
                on conflict (name) do update set
                    lat = excluded.lat,
                    lng = excluded.lng,
                    coordinate_source = 'test',
                    coordinate_status = 'verified',
                    coordinate_query = excluded.coordinate_query,
                    updated_at = now()
                """,
                (name, lat, lng, f"{name}站"),
            )
        conn.commit()


def delete_test_stations(*names: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "delete from train_stations where coordinate_source = 'test' and name = any(%s)",
                (list(names),),
            )
        conn.commit()


def imported_segment(source_type: str) -> ImportedSegment:
    transport_type = "flight" if source_type == "flight" else "train"
    metadata = (
        {
            "vehicleModel": "B763",
            "registration": "N671UA",
            "operatorName": "United Airlines Inc",
            "operatorCode": "UA",
            "originLocation": "Chicago O'Hare International",
            "destinationLocation": "London Heathrow",
            "logoKind": "airline",
            "logoUrl": importers.airline_logo_url("UA"),
            "logoText": "UA",
        }
        if source_type == "flight"
        else {
            "vehicleModel": "CR400",
            "operatorCode": "12306",
            "logoKind": "railway_12306",
            "logoUrl": importers.RAILWAY_12306_LOGO_URL,
            "logoText": "12306",
        }
    )
    return ImportedSegment(
        title="导入轨迹",
        source_type=source_type,
        transport_type=transport_type,
        external_code="UA938" if source_type == "flight" else "G803",
        started_at=datetime(2026, 7, 2, 8, 0, tzinfo=timezone.utc),
        ended_at=datetime(2026, 7, 2, 10, 0, tzinfo=timezone.utc),
        summary="测试导入",
        is_approximate=True,
        metadata=metadata,
        points=[
            ImportedPoint(0, 39.9042, 116.4074, name="起点"),
            ImportedPoint(1, 31.2304, 121.4737, name="终点"),
        ],
        response_payload={"ok": True},
    )


def segment_count(headers: dict) -> int:
    return len(client.get("/api/segments", headers=headers).json())


def test_import_flight_creates_segment(monkeypatch):
    run_migrations()
    username, headers = create_user()
    try:
        monkeypatch.setattr(
            "app.main.resolve_flight_import",
            lambda flight_number, flight_date: imported_segment("flight"),
        )
        response = client.post(
            "/api/import/flight",
            headers=headers,
            json={"flightNumber": "UA938", "date": "2026-07-02"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sourceType"] == "flight"
        assert data["externalCode"] == "UA938"
        assert data["isApproximate"] is True
        assert data["metadata"]["vehicleModel"] == "B763"
        assert data["metadata"]["registration"] == "N671UA"
        assert data["metadata"]["logoUrl"] == "/api/assets/airline-logos/UA.png"
        assert [point["name"] for point in data["points"]] == ["起点", "终点"]
    finally:
        delete_account(username)


def test_import_train_creates_segment(monkeypatch):
    run_migrations()
    username, headers = create_user()
    try:
        monkeypatch.setattr(
            "app.main.resolve_train_import",
            lambda train_code, travel_date, from_station, to_station: imported_segment("train"),
        )
        response = client.post(
            "/api/import/train",
            headers=headers,
            json={
                "trainCode": "G803",
                "date": "2026-07-02",
                "fromStation": "北京南",
                "toStation": "上海虹桥",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sourceType"] == "train"
        assert data["transportType"] == "train"
        assert data["externalCode"] == "G803"
        assert data["metadata"]["vehicleModel"] == "CR400"
        assert "operatorName" not in data["metadata"]
        assert data["metadata"]["logoText"] == "12306"
        assert data["metadata"]["logoUrl"] == importers.RAILWAY_12306_LOGO_URL
        assert len(data["points"]) == 2
    finally:
        delete_account(username)


def test_train_stations_returns_available_stations(monkeypatch):
    run_migrations()
    username, headers = create_user()
    try:
        monkeypatch.setattr(
            "app.main.resolve_train_stations",
            lambda train_code, travel_date: importers.TrainStations(
                train_code=train_code,
                requested_date=travel_date,
                query_date=travel_date,
                stations=[
                    {"station_name": "北京南", "arrive_time": "----", "start_time": "12:12", "arrive_day_diff": "0"},
                    {"station_name": "济南西", "arrive_time": "14:30", "start_time": "14:32", "arrive_day_diff": "0"},
                    {"station_name": "上海虹桥", "arrive_time": "18:18", "start_time": "----", "arrive_day_diff": "0"},
                ],
            ),
        )
        response = client.post(
            "/api/import/train/stations",
            headers=headers,
            json={"trainCode": "G803", "date": "2026-07-02"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["trainCode"] == "G803"
        assert data["requestedDate"] == "2026-07-02"
        assert data["queryDate"] == "2026-07-02"
        assert [station["name"] for station in data["stations"]] == ["北京南", "济南西", "上海虹桥"]
        assert data["stations"][0]["startTime"] == "12:12"
    finally:
        delete_account(username)


def test_select_train_rows_uses_user_station_range():
    rows = [
        {"station_name": "北京南"},
        {"station_name": "廊坊"},
        {"station_name": "天津南"},
        {"station_name": "济南西"},
    ]
    selected = select_train_rows(rows, "廊坊站", "济南西")
    assert [row["station_name"] for row in selected] == ["廊坊", "天津南", "济南西"]


def test_train_query_dates_falls_back_to_server_week():
    requested = date(2020, 1, 1)
    dates = train_query_dates(requested)
    assert dates[0] == requested
    assert len(dates) == 9
    assert len(set(dates)) == len(dates)


def test_train_import_fallback_keeps_requested_date(monkeypatch):
    run_migrations()
    requested = date(2020, 1, 1)
    fallback = date(2026, 7, 2)
    rows = [
        {"station_name": "测试起点", "start_time": "08:00", "arrive_time": "----", "arrive_day_diff": "0"},
        {"station_name": "测试终点", "start_time": "----", "arrive_time": "10:00", "arrive_day_diff": "0"},
    ]
    try:
        upsert_test_station("测试起点", 39.0, 116.0)
        upsert_test_station("测试终点", 36.0, 117.0)
        monkeypatch.setattr(importers, "train_query_dates", lambda _requested: [requested, fallback])
        monkeypatch.setattr(
            importers,
            "fetch_train_rows",
            lambda _client, _code, query_date: (
                ({"train_no": "240000G8030B"} if query_date == fallback else None),
                (rows if query_date == fallback else []),
                (None if query_date == fallback else "2020-01-01 未找到 G803"),
            ),
        )
        monkeypatch.setattr(importers, "geocode", lambda _address: (_ for _ in ()).throw(AssertionError("火车导入不应调用 Google Geocoding")))
        monkeypatch.setattr(importers, "fetch_train_unit_record", lambda _code: {"emu_no": "CR400BFB5154"})

        segment = importers.resolve_train_import("G803", requested, "测试起点", "测试终点")

        assert segment.title == "G803 测试起点-测试终点"
        assert "2020-01-01" in segment.summary
        assert segment.started_at and segment.started_at.date() == requested
        assert [point.name for point in segment.points] == ["测试起点", "测试终点"]
        assert segment.metadata["vehicleModel"] == "CR400BFB"
        assert "operatorName" not in segment.metadata
    finally:
        delete_test_stations("测试起点", "测试终点")


def test_train_stations_fallback_returns_requested_and_query_date(monkeypatch):
    requested = date(2020, 1, 1)
    fallback = date(2026, 7, 2)
    rows = [
        {"station_name": "廊坊", "start_time": "08:00", "arrive_time": "----", "arrive_day_diff": "0"},
        {"station_name": "济南西", "start_time": "----", "arrive_time": "10:00", "arrive_day_diff": "0"},
    ]

    monkeypatch.setattr(importers, "train_query_dates", lambda _requested: [requested, fallback])
    monkeypatch.setattr(
        importers,
        "fetch_train_rows",
        lambda _client, _code, query_date: (
            ({"train_no": "240000G8030B"} if query_date == fallback else None),
            (rows if query_date == fallback else []),
            (None if query_date == fallback else "2020-01-01 未找到 G803"),
        ),
    )

    result = importers.resolve_train_stations("G803", requested)

    assert result.requested_date == requested
    assert result.query_date == fallback
    assert [row["station_name"] for row in result.stations] == ["廊坊", "济南西"]


def test_parse_iata_airport_location():
    html = """
    <table><tbody>
      <tr><td>Guangzhou</td><td>Baiyun Intl</td><td>CAN</td></tr>
      <tr><td>Can Tho</td><td>International</td><td>VCA</td></tr>
    </tbody></table>
    """
    assert parse_iata_airport_location(html, "CAN") == "Guangzhou Baiyun Intl"
    assert parse_iata_airport_location(html, "ORD") is None


def test_parse_iata_airline_name():
    html = """
    <table><tbody>
      <tr><td>United Airlines Inc</td><td>United States of America</td><td>UA</td></tr>
      <tr><td>Uganda Airlines</td><td>Uganda</td><td>UR</td></tr>
    </tbody></table>
    """
    assert parse_iata_airline_name(html, "UA") == "United Airlines Inc"
    assert parse_iata_airline_name(html, "UAL") is None


def test_flight_metadata_uses_iata_airline_name(monkeypatch):
    monkeypatch.setattr(importers, "iata_airline_name", lambda code: "United Airlines Inc" if code == "UA" else None)

    metadata = importers.flight_metadata(
        "UA938",
        {"painted_as": "UAL", "type": "B763", "reg": "N674UA"},
        "Chicago O'Hare International",
        "London Heathrow",
    )

    assert metadata["operatorName"] == "United Airlines Inc"
    assert metadata["operatorCode"] == "UA"
    assert metadata["vehicleModel"] == "B763"
    assert metadata["registration"] == "N674UA"
    assert metadata["logoUrl"] == "/api/assets/airline-logos/UA.png"


def test_airline_logo_endpoint_returns_backend_cached_file(monkeypatch, tmp_path):
    logo_path = tmp_path / "UA.png"
    logo_path.write_bytes(b"png-data")
    monkeypatch.setattr("app.main.cached_airline_logo_path", lambda code: logo_path)

    response = client.get("/api/assets/airline-logos/UA.png")

    assert response.status_code == 200
    assert response.content == b"png-data"
    assert response.headers["cache-control"] == "public, max-age=604800"
    assert client.head("/api/assets/airline-logos/UA.png").status_code == 200


def test_cached_airline_logo_rejects_invalid_code():
    try:
        importers.cached_airline_logo_path("../UA")
    except ImportFailure as error:
        assert error.status_code == 404
    else:
        raise AssertionError("无效航司代码应返回失败")


def test_train_vehicle_model_parses_rail_re_unit():
    assert importers.train_vehicle_model("CR400BFB5154") == "CR400BFB"
    assert importers.train_vehicle_model("CRH380A2723") == "CRH380A"
    assert importers.train_vehicle_model("ABC") == "ABC"


def test_train_station_seed_imports_required_stations(monkeypatch):
    run_migrations()
    monkeypatch.setattr(importers, "geocode", lambda _address: (_ for _ in ()).throw(AssertionError("火车站坐标不应调用 Google Geocoding")))
    import_station_seed()

    expected = {
        "云梦东": (31.0479946, 113.7788677),
        "安陆西": (31.2567844, 113.6470509),
        "孝感东": (30.9357745, 113.9424846),
        "汉口": (30.6216514, 114.2494144),
        "大板": (43.52433806, 118.63308389),
    }
    for station, coordinates in expected.items():
        result = importers.train_station_coordinate(f"{station}站")
        assert result is not None
        lat, lng, raw = result
        assert (lat, lng) == coordinates
        assert raw["source"] == "seed"
        assert raw["station"] == station


def test_train_import_rejects_endpoint_without_database_coordinate(monkeypatch):
    run_migrations()
    import_station_seed()
    requested = date(2026, 7, 2)
    rows = [
        {"station_name": "不存在东", "start_time": "08:00", "arrive_time": "----", "arrive_day_diff": "0"},
        {"station_name": "汉口", "start_time": "----", "arrive_time": "10:00", "arrive_day_diff": "0"},
    ]
    monkeypatch.setattr(importers, "train_query_dates", lambda _requested: [requested])
    monkeypatch.setattr(importers, "fetch_train_rows", lambda _client, _code, _query_date: ({"train_no": "X"}, rows, None))
    monkeypatch.setattr(importers, "geocode", lambda _address: (0.0, 0.0, {"formatted_address": "错误地点"}))
    monkeypatch.setattr(
        importers,
        "train_station_coordinate",
        lambda station: importers.database_train_station_coordinate(station, resolve_missing=False),
    )

    try:
        importers.resolve_train_import("G1", requested, "不存在东", "汉口")
    except ImportFailure as error:
        assert error.status_code == 422
        assert "缺少乘车起点坐标" in error.message
    else:
        raise AssertionError("起点没有数据库坐标时应失败")


def test_train_import_skips_middle_station_without_coordinate(monkeypatch):
    run_migrations()
    import_station_seed()
    requested = date(2026, 7, 2)
    rows = [
        {"station_name": "汉口", "start_time": "08:00", "arrive_time": "----", "arrive_day_diff": "0"},
        {"station_name": "中间缺坐标", "start_time": "09:00", "arrive_time": "09:00", "arrive_day_diff": "0"},
        {"station_name": "孝感东", "start_time": "----", "arrive_time": "10:00", "arrive_day_diff": "0"},
    ]
    monkeypatch.setattr(importers, "train_query_dates", lambda _requested: [requested])
    monkeypatch.setattr(importers, "fetch_train_rows", lambda _client, _code, _query_date: ({"train_no": "X"}, rows, None))
    monkeypatch.setattr(importers, "fetch_train_unit_record", lambda _code: None)
    monkeypatch.setattr(
        importers,
        "train_station_coordinate",
        lambda station: importers.database_train_station_coordinate(station, resolve_missing=False),
    )

    segment = importers.resolve_train_import("G1", requested, "汉口", "孝感东")

    assert [point.sequence for point in segment.points] == [0, 1]
    assert [point.name for point in segment.points] == ["汉口", "孝感东"]
    assert segment.response_payload["skippedMissingCoordinateStations"] == ["中间缺坐标"]


def test_failed_import_does_not_write_segment(monkeypatch):
    run_migrations()
    username, headers = create_user()
    try:
        def fail(_flight_number: str, _flight_date: date):
            raise ImportFailure("外部服务失败")

        monkeypatch.setattr("app.main.resolve_flight_import", fail)
        response = client.post(
            "/api/import/flight",
            headers=headers,
            json={"flightNumber": "BAD1", "date": "2026-07-02"},
        )
        assert response.status_code == 502
        assert response.json()["detail"] == "外部服务失败"
        assert segment_count(headers) == 0
    finally:
        delete_account(username)
