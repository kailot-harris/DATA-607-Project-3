"""Idempotent upsert of parsed rows into the normalized Postgres (Neon) schema."""
from pathlib import Path

import psycopg

SCHEMA_PATH = Path(__file__).parent / "schema_postgres.sql"


def connect(dsn: str) -> psycopg.Connection:
    conn = psycopg.connect(dsn)
    conn.execute(SCHEMA_PATH.read_text())
    conn.commit()
    return conn


def get_or_create_source(conn, name, base_url, access_type) -> int:
    conn.execute(
        "INSERT INTO sources (name, base_url, access_type) VALUES (%s, %s, %s) "
        "ON CONFLICT(name) DO UPDATE SET base_url = excluded.base_url",
        (name, base_url, access_type),
    )
    return conn.execute("SELECT source_id FROM sources WHERE name = %s", (name,)).fetchone()[0]


def get_or_create_company(conn, name) -> int | None:
    if not name:
        return None
    conn.execute(
        "INSERT INTO companies (name) VALUES (%s) ON CONFLICT(name) DO NOTHING", (name,),
    )
    return conn.execute("SELECT company_id FROM companies WHERE name = %s", (name,)).fetchone()[0]


def upsert_job(conn, row: dict, source_id: int, company_id) -> int:
    cur = conn.execute(
        """
        INSERT INTO jobs (
            source_id, external_id, company_id, title, location, remote_type,
            posted_date, retrieved_at, url, salary_min, salary_max, description_raw
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT(source_id, external_id) DO UPDATE SET
            company_id = excluded.company_id,
            title = excluded.title,
            location = excluded.location,
            remote_type = excluded.remote_type,
            posted_date = excluded.posted_date,
            retrieved_at = excluded.retrieved_at,
            url = excluded.url,
            salary_min = excluded.salary_min,
            salary_max = excluded.salary_max,
            description_raw = excluded.description_raw
        RETURNING job_id
        """,
        (
            source_id, row["external_id"], company_id, row["title"], row["location"],
            row["remote_type"], row["posted_date"], row["retrieved_at"], row["url"],
            row["salary_min"], row["salary_max"], row["description_raw"],
        ),
    )
    return cur.fetchone()[0]


def upsert_tags(conn, job_id: int, tags: list[str] | None) -> None:
    if not tags:
        return
    conn.execute("DELETE FROM job_tags WHERE job_id = %s", (job_id,))
    for tag_name in tags:
        if not tag_name:
            continue
        conn.execute(
            "INSERT INTO tags (tag_name) VALUES (%s) ON CONFLICT(tag_name) DO NOTHING", (tag_name,),
        )
        tag_id = conn.execute("SELECT tag_id FROM tags WHERE tag_name = %s", (tag_name,)).fetchone()[0]
        conn.execute(
            "INSERT INTO job_tags (job_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (job_id, tag_id),
        )


def load_row(conn, row: dict, access_type: str, base_url: str) -> int:
    source_id = get_or_create_source(conn, row["source"], base_url, access_type)
    company_id = get_or_create_company(conn, row["company"])
    job_id = upsert_job(conn, row, source_id, company_id)
    upsert_tags(conn, job_id, row.get("tags_raw"))
    return job_id
