from datetime import datetime

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.config import settings
from app.db import get_connection
from app.security import create_access_token, hash_password, read_account_id, verify_password

app = FastAPI(title="SEMAP API")


class AuthRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class AccountResponse(BaseModel):
    id: int
    username: str
    createdAt: datetime
    updatedAt: datetime


class LoginResponse(BaseModel):
    accessToken: str
    tokenType: str
    account: AccountResponse


def database_ready() -> bool:
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("select 1")
            return cur.fetchone()[0] == 1


def account_response(account: dict) -> AccountResponse:
    return AccountResponse(
        id=account["id"],
        username=account["username"],
        createdAt=account["created_at"],
        updatedAt=account["updated_at"],
    )


def get_current_account(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "请先登录")

    account_id = read_account_id(authorization.removeprefix("Bearer ").strip())
    if account_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录已失效")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, username, created_at, updated_at
                from accounts
                where id = %s
                """,
                (account_id,),
            )
            account = cur.fetchone()

    if not account:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录已失效")
    return account


@app.get("/health")
def health():
    return {"status": "ok", "database": "ok" if database_ready() else "error"}


@app.get("/api/health")
def api_health():
    return health()


@app.post("/api/auth/register", response_model=AccountResponse, status_code=201)
def register(payload: AuthRequest):
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into accounts (username, password_hash)
                    values (%s, %s)
                    returning id, username, created_at, updated_at
                    """,
                    (payload.username, hash_password(payload.password)),
                )
                account = cur.fetchone()
            conn.commit()
        except psycopg.errors.UniqueViolation:
            conn.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "用户名已存在")

    return account_response(account)


@app.post("/api/auth/login", response_model=LoginResponse)
def login(payload: AuthRequest):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, username, password_hash, created_at, updated_at
                from accounts
                where username = %s
                """,
                (payload.username,),
            )
            account = cur.fetchone()

    if not account or not verify_password(payload.password, account["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")

    return LoginResponse(
        accessToken=create_access_token(account["id"]),
        tokenType="bearer",
        account=account_response(account),
    )


@app.get("/api/auth/me", response_model=AccountResponse)
def me(account: dict = Depends(get_current_account)):
    return account_response(account)
