from uuid import uuid4

from fastapi.testclient import TestClient

from app.db import get_connection
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


def point(lat: float, lng: float) -> dict:
    return {
        "lat": lat,
        "lng": lng,
        "altitude": 20.5,
        "speed": 1.8,
        "recordedAt": "2026-07-02T12:00:00Z",
        "accuracy": 8.0,
        "provider": "fused",
        "rawLat": lat - 0.001,
        "rawLng": lng - 0.001,
        "coordinateSystem": "gcj02",
    }


def test_location_session_complete_flow():
    run_migrations()
    username, headers = create_user()
    try:
        create_response = client.post("/api/location-sessions", headers=headers)
        assert create_response.status_code == 200
        session = create_response.json()
        session_id = session["id"]
        segment_id = session["segmentId"]
        assert session["status"] == "active"
        assert session["segment"]["sourceType"] == "gps"
        assert session["segment"]["title"] == "定位上传 1"
        assert session["segment"]["summary"] == "定位上传中"
        assert session["segment"]["metadata"]["logoKind"] == "gps_road"
        assert session["segment"]["metadata"]["logoUrl"] == "/logos/road.png"
        assert session["segment"]["points"] == []

        points_response = client.post(
            f"/api/location-sessions/{session_id}/points",
            headers=headers,
            json={"points": [point(39.9, 116.4), point(39.91, 116.41)]},
        )
        assert points_response.status_code == 200
        assert [item["sequence"] for item in points_response.json()["segment"]["points"]] == [0, 1]

        pause_response = client.patch(f"/api/location-sessions/{session_id}/pause", headers=headers)
        assert pause_response.status_code == 200
        assert pause_response.json()["status"] == "paused"

        rejected = client.post(
            f"/api/location-sessions/{session_id}/points",
            headers=headers,
            json={"points": [point(39.92, 116.42)]},
        )
        assert rejected.status_code == 409
        assert rejected.json()["detail"] == "定位会话未处于记录状态"

        resume_response = client.patch(f"/api/location-sessions/{session_id}/resume", headers=headers)
        assert resume_response.status_code == 200
        assert resume_response.json()["status"] == "active"

        finish_response = client.patch(f"/api/location-sessions/{session_id}/finish", headers=headers)
        assert finish_response.status_code == 200
        finished = finish_response.json()
        assert finished["status"] == "finished"
        assert finished["segment"]["endedAt"] is not None
        assert finished["segment"]["summary"] == "GPS 记录完成，共 2 个定位点"

        segment_response = client.get(f"/api/segments/{segment_id}", headers=headers)
        assert segment_response.status_code == 200
        assert segment_response.json()["sourceType"] == "gps"
        points = segment_response.json()["points"]
        assert len(points) == 2
        assert points[0]["raw"]["accuracy"] == 8.0
        assert points[0]["raw"]["provider"] == "fused"
        assert points[0]["raw"]["rawLat"] == 39.899
        assert points[0]["raw"]["coordinateSystem"] == "gcj02"
    finally:
        delete_account(username)


def test_location_session_isolated_by_account():
    run_migrations()
    first_username, first_headers = create_user()
    second_username, second_headers = create_user()
    try:
        session_id = client.post("/api/location-sessions", headers=first_headers).json()["id"]
        response = client.patch(f"/api/location-sessions/{session_id}/pause", headers=second_headers)
        assert response.status_code == 404
        assert response.json()["detail"] == "定位会话不存在"
    finally:
        delete_account(first_username)
        delete_account(second_username)
