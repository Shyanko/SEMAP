from fastapi import FastAPI
import psycopg

from app.config import settings

app = FastAPI(title="SEMAP API")


def database_ready() -> bool:
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("select 1")
            return cur.fetchone()[0] == 1


@app.get("/health")
def health():
    return {"status": "ok", "database": "ok" if database_ready() else "error"}


@app.get("/api/health")
def api_health():
    return health()
