from pathlib import Path

from app.db import get_connection

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


def run_migrations() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                create table if not exists semap_migrations (
                    filename text primary key,
                    applied_at timestamptz not null default now()
                )
                """
            )

            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                cur.execute(
                    "select 1 from semap_migrations where filename = %s",
                    (path.name,),
                )
                if cur.fetchone():
                    continue
                cur.execute(path.read_text(encoding="utf-8"))
                cur.execute(
                    "insert into semap_migrations (filename) values (%s)",
                    (path.name,),
                )
        conn.commit()


if __name__ == "__main__":
    run_migrations()
