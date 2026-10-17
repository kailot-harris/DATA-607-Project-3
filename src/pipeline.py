#!/usr/bin/env python
"""Orchestrator: fetch -> save raw snapshot -> parse -> validate -> load, per source."""
import argparse
import datetime
import json
import os
import sys
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from src.fetchers import remoteok, arbeitnow, jobicy, himalayas, wwr, hn_hiring, adzuna, usajobs  # noqa: E402
from src.parsers import remoteok as p_remoteok, arbeitnow as p_arbeitnow, jobicy as p_jobicy  # noqa: E402
from src.parsers import himalayas as p_himalayas, wwr as p_wwr, hn_hiring as p_hn_hiring  # noqa: E402
from src.parsers import adzuna as p_adzuna, usajobs as p_usajobs  # noqa: E402
from src.parsers import validate_row  # noqa: E402
from src.db import load as sqlite_backend  # noqa: E402
from src.db import load_postgres as postgres_backend  # noqa: E402

SOURCES = {
    "remoteok": (remoteok, p_remoteok),
    "arbeitnow": (arbeitnow, p_arbeitnow),
    "jobicy": (jobicy, p_jobicy),
    "himalayas": (himalayas, p_himalayas),
    "wwr": (wwr, p_wwr),
    "hn_hiring": (hn_hiring, p_hn_hiring),
    "adzuna": (adzuna, p_adzuna),
    "usajobs": (usajobs, p_usajobs),
}


def run_source(name, scfg, contact_email, session, run_date, conn, loader) -> dict:
    fetcher, parser = SOURCES[name]
    cfg = {**scfg, "contact_email": contact_email}
    result = {"source": name, "fetched": 0, "loaded": 0, "invalid": 0}

    if scfg.get("requires_key") and not fetcher.has_credentials(scfg):
        result["status"] = "skipped_no_key"
        return result
    if parser is None:
        result["status"] = "skipped_no_parser"
        return result

    try:
        raw, records = fetcher.fetch_all(session, cfg)
    except Exception as exc:
        result["status"] = "fetch_error"
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    outdir = ROOT / "data" / "raw" / name / run_date
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "data.json").write_text(json.dumps(raw, default=str, indent=2))

    retrieved_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result["fetched"] = len(records)

    for record in records:
        row = parser.parse_record(record, retrieved_at)
        errors = validate_row(row)
        if errors:
            result["invalid"] += 1
            continue
        loader.load_row(conn, row, access_type=scfg["access_type"], base_url=scfg["base_url"])
        result["loaded"] += 1

    result["status"] = "ok"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", help="comma-separated source names (default: all enabled)")
    parser.add_argument("--db", default=str(ROOT / "data" / "db" / "jobs.db"))
    parser.add_argument("--backend", choices=["sqlite", "postgres"], default="sqlite")
    parser.add_argument("--db-url", help="Postgres DSN (default: $DATABASE_URL_UNPOOLED)")
    args = parser.parse_args()

    cfg = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text())
    contact_email = cfg["contact_email"]
    run_date = datetime.date.today().isoformat()
    session = requests.Session()

    wanted = set(args.sources.split(",")) if args.sources else None

    if args.backend == "postgres":
        loader = postgres_backend
        dsn = args.db_url or os.environ["DATABASE_URL_UNPOOLED"]
        conn = loader.connect(dsn)
        db_label = "neon postgres"
    else:
        loader = sqlite_backend
        Path(args.db).parent.mkdir(parents=True, exist_ok=True)
        conn = loader.connect(args.db)
        db_label = args.db

    results = []
    for name, scfg in cfg["sources"].items():
        if wanted is not None and name not in wanted:
            continue
        if not scfg.get("enabled", True):
            results.append({"source": name, "status": "disabled"})
            continue
        print(f"running {name} ...", flush=True)
        results.append(run_source(name, scfg, contact_email, session, run_date, conn, loader))
        conn.commit()

    print()
    header = f"{'source':<12} {'status':<18} {'fetched':>8} {'loaded':>7} {'invalid':>8}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r['source']:<12} {r['status']:<18} "
            f"{str(r.get('fetched', '-')):>8} {str(r.get('loaded', '-')):>7} {str(r.get('invalid', '-')):>8}"
        )
        if r.get("error"):
            print(f"             error: {r['error']}")

    total_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    print(f"\ntotal rows in jobs table: {total_jobs}")
    print(f"db: {db_label}")


if __name__ == "__main__":
    main()
