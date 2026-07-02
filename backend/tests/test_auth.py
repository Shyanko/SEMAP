from uuid import uuid4

from fastapi.testclient import TestClient

from app.db import get_connection
from app.main import app
from app.migrate import run_migrations

client = TestClient(app)


def unique_username() -> str:
    return f"user_{uuid4().hex[:12]}"


def delete_account(username: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from accounts where username = %s", (username,))
        conn.commit()


def test_register_login_and_me():
    run_migrations()
    username = unique_username()
    password = "password123"
    try:
        register_response = client.post(
            "/api/auth/register",
            json={"username": username, "password": password},
        )
        assert register_response.status_code == 201
        assert register_response.json()["username"] == username

        login_response = client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )
        assert login_response.status_code == 200
        token = login_response.json()["accessToken"]

        me_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_response.status_code == 200
        assert me_response.json()["username"] == username
    finally:
        delete_account(username)


def test_duplicate_register_returns_conflict():
    run_migrations()
    username = unique_username()
    password = "password123"
    try:
        assert client.post(
            "/api/auth/register",
            json={"username": username, "password": password},
        ).status_code == 201
        duplicate_response = client.post(
            "/api/auth/register",
            json={"username": username, "password": password},
        )
        assert duplicate_response.status_code == 409
        assert duplicate_response.json()["detail"] == "用户名已存在"
    finally:
        delete_account(username)


def test_me_requires_token():
    run_migrations()
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "请先登录"
