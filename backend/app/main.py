from datetime import date, datetime
from typing import Any

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field
from psycopg.types.json import Json

from app.config import settings
from app.db import get_connection
from app.importers import (
    ImportedSegment,
    ImportFailure,
    resolve_flight_import,
    resolve_train_import,
)
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


class TrackPointResponse(BaseModel):
    id: int
    sequence: int
    lat: float
    lng: float
    altitude: float | None = None
    speed: float | None = None
    recordedAt: datetime | None = None
    name: str | None = None
    raw: dict[str, Any] | None = None


class SegmentUpdateRequest(BaseModel):
    version: int
    title: str | None = Field(default=None, min_length=1, max_length=200)
    startedAt: datetime | None = None
    endedAt: datetime | None = None
    summary: str | None = None
    note: str | None = None


class FlightImportRequest(BaseModel):
    flightNumber: str = Field(min_length=2, max_length=16)
    date: date


class TrainImportRequest(BaseModel):
    trainCode: str = Field(min_length=1, max_length=16)
    date: date
    fromStation: str = Field(min_length=1, max_length=64)
    toStation: str = Field(min_length=1, max_length=64)


class TrackSegmentResponse(BaseModel):
    id: int
    title: str
    sourceType: str
    transportType: str
    externalCode: str | None
    startedAt: datetime | None
    endedAt: datetime | None
    summary: str | None
    note: str | None
    isApproximate: bool
    version: int
    createdAt: datetime
    updatedAt: datetime
    points: list[TrackPointResponse]


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


def point_response(point: dict) -> TrackPointResponse:
    return TrackPointResponse(
        id=point["id"],
        sequence=point["sequence"],
        lat=point["lat"],
        lng=point["lng"],
        altitude=point["altitude"],
        speed=point["speed"],
        recordedAt=point["recorded_at"],
        name=point["name"],
        raw=point["raw"],
    )


def segment_response(segment: dict, points: list[dict]) -> TrackSegmentResponse:
    return TrackSegmentResponse(
        id=segment["id"],
        title=segment["title"],
        sourceType=segment["source_type"],
        transportType=segment["transport_type"],
        externalCode=segment["external_code"],
        startedAt=segment["started_at"],
        endedAt=segment["ended_at"],
        summary=segment["summary"],
        note=segment["note"],
        isApproximate=segment["is_approximate"],
        version=segment["version"],
        createdAt=segment["created_at"],
        updatedAt=segment["updated_at"],
        points=[point_response(point) for point in points],
    )


def fetch_segment_with_points(segment_id: int, account_id: int) -> TrackSegmentResponse:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select *
                from track_segments
                where id = %s and account_id = %s
                """,
                (segment_id, account_id),
            )
            segment = cur.fetchone()
            if not segment:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "轨迹不存在")

            cur.execute(
                """
                select *
                from track_points
                where segment_id = %s
                order by sequence
                """,
                (segment_id,),
            )
            points = cur.fetchall()
    return segment_response(segment, points)


def save_imported_segment(
    account_id: int,
    imported: ImportedSegment,
    request_payload: dict[str, Any],
) -> TrackSegmentResponse:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into track_segments (
                    account_id, title, source_type, transport_type, external_code,
                    started_at, ended_at, summary, note, is_approximate
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                returning *
                """,
                (
                    account_id,
                    imported.title,
                    imported.source_type,
                    imported.transport_type,
                    imported.external_code,
                    imported.started_at,
                    imported.ended_at,
                    imported.summary,
                    imported.note,
                    imported.is_approximate,
                ),
            )
            segment = cur.fetchone()

            for point in imported.points:
                cur.execute(
                    """
                    insert into track_points (
                        segment_id, sequence, lat, lng, altitude, speed,
                        recorded_at, name, raw
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        segment["id"],
                        point.sequence,
                        point.lat,
                        point.lng,
                        point.altitude,
                        point.speed,
                        point.recorded_at,
                        point.name,
                        Json(point.raw) if point.raw is not None else None,
                    ),
                )

            cur.execute(
                """
                insert into import_records (
                    account_id, segment_id, source_type, external_code,
                    request_payload, response_payload, status
                )
                values (%s, %s, %s, %s, %s, %s, 'success')
                """,
                (
                    account_id,
                    segment["id"],
                    imported.source_type,
                    imported.external_code,
                    Json(request_payload),
                    Json(imported.response_payload),
                ),
            )

            cur.execute(
                """
                select *
                from track_points
                where segment_id = %s
                order by sequence
                """,
                (segment["id"],),
            )
            points = cur.fetchall()
        conn.commit()

    return segment_response(segment, points)


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


@app.post("/api/import/flight", response_model=TrackSegmentResponse)
def import_flight(payload: FlightImportRequest, account: dict = Depends(get_current_account)):
    try:
        imported = resolve_flight_import(payload.flightNumber, payload.date)
    except ImportFailure as error:
        raise HTTPException(error.status_code, error.message)
    return save_imported_segment(
        account["id"],
        imported,
        payload.model_dump(mode="json"),
    )


@app.post("/api/import/train", response_model=TrackSegmentResponse)
def import_train(payload: TrainImportRequest, account: dict = Depends(get_current_account)):
    try:
        imported = resolve_train_import(
            payload.trainCode,
            payload.date,
            payload.fromStation,
            payload.toStation,
        )
    except ImportFailure as error:
        raise HTTPException(error.status_code, error.message)
    return save_imported_segment(
        account["id"],
        imported,
        payload.model_dump(mode="json"),
    )


@app.get("/api/segments", response_model=list[TrackSegmentResponse])
def list_segments(account: dict = Depends(get_current_account)):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select *
                from track_segments
                where account_id = %s
                order by updated_at desc, id desc
                """,
                (account["id"],),
            )
            segments = cur.fetchall()
            if not segments:
                return []

            segment_ids = [segment["id"] for segment in segments]
            cur.execute(
                """
                select *
                from track_points
                where segment_id = any(%s)
                order by segment_id, sequence
                """,
                (segment_ids,),
            )
            points_by_segment = {segment_id: [] for segment_id in segment_ids}
            for point in cur.fetchall():
                points_by_segment[point["segment_id"]].append(point)

    return [
        segment_response(segment, points_by_segment[segment["id"]])
        for segment in segments
    ]


@app.get("/api/segments/{segment_id}", response_model=TrackSegmentResponse)
def get_segment(segment_id: int, account: dict = Depends(get_current_account)):
    return fetch_segment_with_points(segment_id, account["id"])


@app.patch("/api/segments/{segment_id}", response_model=TrackSegmentResponse)
def update_segment(
    segment_id: int,
    payload: SegmentUpdateRequest,
    account: dict = Depends(get_current_account),
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select *
                from track_segments
                where id = %s and account_id = %s
                """,
                (segment_id, account["id"]),
            )
            current = cur.fetchone()
            if not current:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "轨迹不存在")
            if current["version"] != payload.version:
                raise HTTPException(status.HTTP_409_CONFLICT, "轨迹已被修改，请刷新后重试")

            fields = payload.model_fields_set
            cur.execute(
                """
                update track_segments
                set
                    title = %s,
                    started_at = %s,
                    ended_at = %s,
                    summary = %s,
                    note = %s,
                    version = version + 1,
                    updated_at = now()
                where id = %s and account_id = %s
                returning *
                """,
                (
                    payload.title if "title" in fields else current["title"],
                    payload.startedAt if "startedAt" in fields else current["started_at"],
                    payload.endedAt if "endedAt" in fields else current["ended_at"],
                    payload.summary if "summary" in fields else current["summary"],
                    payload.note if "note" in fields else current["note"],
                    segment_id,
                    account["id"],
                ),
            )
            segment = cur.fetchone()
            cur.execute(
                """
                select *
                from track_points
                where segment_id = %s
                order by sequence
                """,
                (segment_id,),
            )
            points = cur.fetchall()
        conn.commit()

    return segment_response(segment, points)


@app.delete("/api/segments/{segment_id}", status_code=204)
def delete_segment(
    segment_id: int,
    version: int,
    account: dict = Depends(get_current_account),
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select version
                from track_segments
                where id = %s and account_id = %s
                """,
                (segment_id, account["id"]),
            )
            current = cur.fetchone()
            if not current:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "轨迹不存在")
            if current["version"] != version:
                raise HTTPException(status.HTTP_409_CONFLICT, "轨迹已被修改，请刷新后重试")

            cur.execute(
                """
                delete from track_segments
                where id = %s and account_id = %s
                """,
                (segment_id, account["id"]),
            )
        conn.commit()
