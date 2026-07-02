from uuid import uuid4

from fastapi.testclient import TestClient

from app.db import get_connection
from app.main import app
from app.migrate import run_migrations

client = TestClient(app)


def create_user() -> tuple[str, dict, int]:
    username = f"user_{uuid4().hex[:12]}"
    password = "password123"
    client.post("/api/auth/register", json={"username": username, "password": password})
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    token = response.json()["accessToken"]
    account_id = response.json()["account"]["id"]
    return username, {"Authorization": f"Bearer {token}"}, account_id


def delete_account(username: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from accounts where username = %s", (username,))
        conn.commit()


def insert_segment(account_id: int, title: str = "航班轨迹") -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into track_segments (
                    account_id, title, source_type, transport_type,
                    started_at, ended_at, summary, note, is_approximate
                )
                values (
                    %s, %s, 'flight', 'flight',
                    '2026-07-02T08:00:00Z', '2026-07-02T10:00:00Z',
                    '导入生成的测试轨迹', '测试备注', false
                )
                returning id
                """,
                (account_id, title),
            )
            segment_id = cur.fetchone()["id"]
            cur.execute(
                """
                insert into track_points (segment_id, sequence, lat, lng, name)
                values
                    (%s, 0, 39.9042, 116.4074, '北京'),
                    (%s, 1, 31.2304, 121.4737, '上海')
                """,
                (segment_id, segment_id),
            )
        conn.commit()
    return segment_id


def test_post_segments_is_not_supported():
    run_migrations()
    username, headers, _ = create_user()
    try:
        response = client.post(
            "/api/segments",
            headers=headers,
            json={"title": "不支持的手动轨迹", "points": []},
        )
        assert response.status_code == 405
    finally:
        delete_account(username)


def test_list_get_update_and_delete_segment():
    run_migrations()
    username, headers, account_id = create_user()
    try:
        segment_id = insert_segment(account_id)

        list_response = client.get("/api/segments", headers=headers)
        assert list_response.status_code == 200
        segment = list_response.json()[0]
        assert segment["id"] == segment_id
        assert segment["sourceType"] == "flight"
        assert segment["version"] == 1
        assert [point["sequence"] for point in segment["points"]] == [0, 1]

        detail_response = client.get(f"/api/segments/{segment_id}", headers=headers)
        assert detail_response.status_code == 200
        assert detail_response.json()["points"][0]["name"] == "北京"

        update_response = client.patch(
            f"/api/segments/{segment_id}",
            headers=headers,
            json={"version": 1, "title": "更新后的轨迹"},
        )
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["title"] == "更新后的轨迹"
        assert updated["version"] == 2
        assert updated["note"] == "测试备注"

        delete_response = client.delete(
            f"/api/segments/{segment_id}?version=2",
            headers=headers,
        )
        assert delete_response.status_code == 204
        assert client.get("/api/segments", headers=headers).json() == []
    finally:
        delete_account(username)


def test_segments_are_isolated_by_account():
    run_migrations()
    first_username, _, first_account_id = create_user()
    second_username, second_headers, _ = create_user()
    try:
        segment_id = insert_segment(first_account_id, "用户一轨迹")

        assert client.get("/api/segments", headers=second_headers).json() == []
        hidden_response = client.get(f"/api/segments/{segment_id}", headers=second_headers)
        assert hidden_response.status_code == 404
        assert hidden_response.json()["detail"] == "轨迹不存在"
    finally:
        delete_account(first_username)
        delete_account(second_username)


def test_segment_version_conflict():
    run_migrations()
    username, headers, account_id = create_user()
    try:
        segment_id = insert_segment(account_id)

        stale_update = client.patch(
            f"/api/segments/{segment_id}",
            headers=headers,
            json={"version": 0, "title": "旧版本更新"},
        )
        assert stale_update.status_code == 409
        assert stale_update.json()["detail"] == "轨迹已被修改，请刷新后重试"

        stale_delete = client.delete(
            f"/api/segments/{segment_id}?version=0",
            headers=headers,
        )
        assert stale_delete.status_code == 409
        assert stale_delete.json()["detail"] == "轨迹已被修改，请刷新后重试"
    finally:
        delete_account(username)
