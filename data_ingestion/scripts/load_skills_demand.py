"""Load a long-format job/skill CSV (one row per job-skill pair) into the shared
Neon Postgres database, alongside the scraped `jobs` tables.

Idempotent: rows are keyed on (dataset, job_external_id, skill) and upserted, so
re-running is always safe -- it only ever adds or refreshes rows, never deletes.
Loading goes through a TEMP table + COPY, which handles the ~225k rows in one
round trip instead of 225k INSERTs.

Usage:
    python scripts/load_skills_demand.py                      # default CSV, real load
    python scripts/load_skills_demand.py --dry-run            # validate only, no writes
    python scripts/load_skills_demand.py --dataset other_2023 --csv path/to.csv
"""
import argparse
import csv
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# The CSV lives in the Quarto project's data/ dir, one level above this pipeline.
DEFAULT_CSV = ROOT.parent / "data" / "skills_demand.csv"
EXPECTED_COLUMNS = ["job_id", "skill", "skill_category", "skill_level"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS skills_demand (
    dataset         TEXT NOT NULL,
    job_external_id TEXT NOT NULL,
    skill           TEXT NOT NULL,
    skill_category  TEXT,
    skill_level     TEXT,
    PRIMARY KEY (dataset, job_external_id, skill)
);
CREATE INDEX IF NOT EXISTS skills_demand_skill_idx ON skills_demand (skill);
CREATE INDEX IF NOT EXISTS skills_demand_dataset_skill_idx ON skills_demand (dataset, skill);
"""


def read_rows(csv_path: Path, dataset: str):
    """Yield validated (dataset, job_id, skill, category, level) tuples.

    Returns the rows plus a per-reason count of what was dropped, so the caller
    can report on data quality instead of silently loading a subset.
    """
    rows = []
    dropped = {"blank_key": 0, "duplicate": 0}
    seen = set()

    # utf-8-sig: the file may carry a BOM, which would otherwise corrupt the
    # first column name and make the header check fail confusingly.
    with csv_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in EXPECTED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(
                f"{csv_path}: missing expected column(s): {', '.join(missing)}\n"
                f"found: {', '.join(reader.fieldnames or ['<empty file>'])}"
            )

        for record in reader:
            job_id = (record["job_id"] or "").strip()
            skill = (record["skill"] or "").strip()
            if not job_id or not skill:
                dropped["blank_key"] += 1
                continue
            key = (job_id, skill)
            if key in seen:
                dropped["duplicate"] += 1
                continue
            seen.add(key)
            rows.append((
                dataset,
                job_id,
                skill,
                (record["skill_category"] or "").strip() or None,
                (record["skill_level"] or "").strip() or None,
            ))
    return rows, dropped


def load(conn, rows) -> None:
    """COPY into a TEMP table, then upsert into skills_demand in one statement."""
    conn.execute(SCHEMA)
    conn.execute(
        "CREATE TEMP TABLE staging_skills_demand "
        "(LIKE skills_demand INCLUDING DEFAULTS) ON COMMIT DROP"
    )
    copy_sql = (
        "COPY staging_skills_demand "
        "(dataset, job_external_id, skill, skill_category, skill_level) FROM STDIN"
    )
    with conn.cursor().copy(copy_sql) as copy:
        for row in rows:
            copy.write_row(row)

    conn.execute(
        """
        INSERT INTO skills_demand
            (dataset, job_external_id, skill, skill_category, skill_level)
        SELECT dataset, job_external_id, skill, skill_category, skill_level
        FROM staging_skills_demand
        ON CONFLICT (dataset, job_external_id, skill) DO UPDATE SET
            skill_category = excluded.skill_category,
            skill_level    = excluded.skill_level
        """
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV,
                        help=f"source CSV (default: {DEFAULT_CSV})")
    parser.add_argument("--dataset", default="skills_demand",
                        help="label stored in the dataset column, so several "
                             "historical extracts can coexist (default: skills_demand)")
    parser.add_argument("--db-url", help="Postgres DSN (default: $DATABASE_URL_UNPOOLED)")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate and summarise the CSV without touching the database")
    args = parser.parse_args()

    if not args.csv.exists():
        raise SystemExit(f"CSV not found: {args.csv}")

    rows, dropped = read_rows(args.csv, args.dataset)
    jobs = len({r[1] for r in rows})
    skills = len({r[2] for r in rows})
    print(f"csv:      {args.csv}")
    print(f"dataset:  {args.dataset}")
    print(f"parsed:   {len(rows)} job-skill rows ({jobs} distinct jobs, {skills} distinct skills)")
    if dropped["blank_key"]:
        print(f"dropped:  {dropped['blank_key']} rows with a blank job_id or skill")
    if dropped["duplicate"]:
        print(f"dropped:  {dropped['duplicate']} duplicate (job_id, skill) rows")

    if args.dry_run:
        print("\ndry run -- database not touched")
        return

    dsn = args.db_url or os.environ.get("DATABASE_URL_UNPOOLED")
    if not dsn:
        print("DATABASE_URL_UNPOOLED not set in environment/.env", file=sys.stderr)
        sys.exit(1)

    with psycopg.connect(dsn) as conn:
        before = conn.execute(
            "SELECT count(*) FROM skills_demand WHERE dataset = %s", (args.dataset,)
        ).fetchone()[0] if table_exists(conn) else 0
        load(conn, rows)
        conn.commit()
        after = conn.execute(
            "SELECT count(*) FROM skills_demand WHERE dataset = %s", (args.dataset,)
        ).fetchone()[0]

    print(f"\nskills_demand[{args.dataset}] row count: {before} -> {after} "
          f"(net new: {after - before})")


def table_exists(conn) -> bool:
    return conn.execute("SELECT to_regclass('public.skills_demand') IS NOT NULL").fetchone()[0]


if __name__ == "__main__":
    main()
