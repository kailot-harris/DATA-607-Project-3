"""One-off/reusable migration: push rows present in local SQLite but missing
from the shared Neon Postgres database. Upserts are idempotent (ON CONFLICT
DO UPDATE on (source_id, external_id)), so re-running this is always safe --
it only ever adds or refreshes rows, never deletes.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

from src.db import load as sqlite_db
from src.db import load_postgres as pg_db

load_dotenv()

SQLITE_PATH = str(Path(__file__).resolve().parents[1] / "data" / "db" / "jobs.db")


def fetch_sqlite_rows(conn):
    sources = {r[0]: {"name": r[1], "base_url": r[2], "access_type": r[3]}
               for r in conn.execute("SELECT source_id, name, base_url, access_type FROM sources")}
    companies = {r[0]: r[1] for r in conn.execute("SELECT company_id, name FROM companies")}

    tags_by_job = {}
    for job_id, tag_name in conn.execute(
        "SELECT jt.job_id, t.tag_name FROM job_tags jt JOIN tags t ON t.tag_id = jt.tag_id"
    ):
        tags_by_job.setdefault(job_id, []).append(tag_name)

    rows = []
    for r in conn.execute(
        """
        SELECT job_id, source_id, external_id, company_id, title, location, remote_type,
               posted_date, retrieved_at, url, salary_min, salary_max, description_raw
        FROM jobs
        """
    ):
        (job_id, source_id, external_id, company_id, title, location, remote_type,
         posted_date, retrieved_at, url, salary_min, salary_max, description_raw) = r
        src = sources[source_id]
        row = {
            "source": src["name"],
            "external_id": external_id,
            "title": title,
            "company": companies.get(company_id),
            "location": location,
            "remote_type": remote_type,
            "posted_date": posted_date,
            "retrieved_at": retrieved_at,
            "url": url,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "description_raw": description_raw,
            "tags_raw": tags_by_job.get(job_id),
        }
        rows.append((row, src["base_url"], src["access_type"]))
    return rows


def main():
    dsn = os.environ.get("DATABASE_URL_UNPOOLED")
    if not dsn:
        print("DATABASE_URL_UNPOOLED not set in environment/.env", file=sys.stderr)
        sys.exit(1)

    sconn = sqlite_db.connect(SQLITE_PATH)
    rows = fetch_sqlite_rows(sconn)
    sconn.close()
    print(f"read {len(rows)} rows from sqlite ({SQLITE_PATH})")

    pconn = pg_db.connect(dsn)
    before = pconn.execute("SELECT count(*) FROM jobs").fetchone()[0]

    existing = set(
        pconn.execute(
            "SELECT s.name, j.external_id FROM jobs j JOIN sources s ON s.source_id = j.source_id"
        ).fetchall()
    )
    print(f"{len(existing)} rows already present in neon; skipping those")

    migrated = 0
    skipped = 0
    for row, base_url, access_type in rows:
        if (row["source"], row["external_id"]) in existing:
            skipped += 1
            continue
        pg_db.load_row(pconn, row, access_type, base_url)
        migrated += 1
        if migrated % 150 == 0:
            pconn.commit()
            print(f"  ...{migrated} new rows upserted ({skipped} skipped so far)")
    pconn.commit()

    after = pconn.execute("SELECT count(*) FROM jobs").fetchone()[0]
    pconn.close()

    print(f"upserted {migrated} new rows into neon postgres ({skipped} already present, skipped)")
    print(f"jobs table row count: {before} -> {after} (net new: {after - before})")


if __name__ == "__main__":
    main()
