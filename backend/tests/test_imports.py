from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

import app.importers as importers
from app.db import get_connection
from app.importers import (
    ImportedPoint,
    ImportedSegment,
    ImportFailure,
    parse_iata_airport_location,
    select_train_rows,
    train_query_dates,
)
from app.main import app
from app.migrate import run_migrations

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


def imported_segment(source_type: str) -> ImportedSegment:
    transport_type = "flight" if source_type == "flight" else "train"
    metadata = (
        {
            "vehicleModel": "B763",
            "registration": "N671UA",
            "operatorName": "UAL",
            "operatorCode": "UA",
            "originLocation": "Chicago O'Hare International",
            "destinationLocation": "London Heathrow",
            "logoKind": "airline",
            "logoText": "UA",
        }
        if source_type == "flight"
        else {
            "vehicleModel": "CR400",
            "operatorName": "中国铁路",
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
        assert data["metadata"]["operatorName"] == "中国铁路"
        assert data["metadata"]["logoText"] == "12306"
        assert data["metadata"]["logoUrl"] == importers.RAILWAY_12306_LOGO_URL
        assert len(data["points"]) == 2
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
    requested = date(2020, 1, 1)
    fallback = date(2026, 7, 2)
    rows = [
        {"station_name": "廊坊", "start_time": "08:00", "arrive_time": "----", "arrive_day_diff": "0"},
        {"station_name": "济南西", "start_time": "----", "arrive_time": "10:00", "arrive_day_diff": "0"},
    ]
    geocode_addresses = []

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
    def fake_geocode(address: str):
        geocode_addresses.append(address)
        return 39.0, 116.0, {"address": address}

    monkeypatch.setattr(importers, "geocode", fake_geocode)
    monkeypatch.setattr(importers, "fetch_train_unit_record", lambda _code: {"emu_no": "CR400BFB5154"})

    segment = importers.resolve_train_import("G803", requested, "廊坊", "济南西")

    assert segment.title == "G803 廊坊-济南西"
    assert "2020-01-01" in segment.summary
    assert segment.started_at and segment.started_at.date() == requested
    assert [point.name for point in segment.points] == ["廊坊", "济南西"]
    assert segment.metadata["vehicleModel"] == "CR400"
    assert geocode_addresses == ["廊坊站", "济南西站"]


def test_parse_iata_airport_location():
    html = """
    <table><tbody>
      <tr><td>Guangzhou</td><td>Baiyun Intl</td><td>CAN</td></tr>
      <tr><td>Can Tho</td><td>International</td><td>VCA</td></tr>
    </tbody></table>
    """
    assert parse_iata_airport_location(html, "CAN") == "Guangzhou Baiyun Intl"
    assert parse_iata_airport_location(html, "ORD") is None


def test_train_vehicle_model_parses_rail_re_unit():
    assert importers.train_vehicle_model("CR400BFB5154") == "CR400"
    assert importers.train_vehicle_model("CRH380A2723") == "CRH380A"


def test_train_station_coordinate_uses_local_table(monkeypatch):
    def fail_geocode(_address: str):
        raise AssertionError("本地表命中时不应调用 Google Geocoding")

    monkeypatch.setattr(importers, "geocode", fail_geocode)
    lat, lng, raw = importers.train_station_coordinate("云梦东站")

    assert (lat, lng) == (31.0479946, 113.7788677)
    assert raw == {"source": "local_train_station_coordinates", "station": "云梦东"}


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
