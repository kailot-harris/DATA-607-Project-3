"""Pre-flight storage check for the daily fetch pipeline.

The shared Neon project caps storage at 512 MB, and ~480 MB is committed to
the Barousse 2023 dataset + the October 2026 scrapeSnapshot. run_daily.ps1
runs this BEFORE src/pipeline.py and skips the fetch while there is less
room than MIN_FREE_MB below the cap, so a final oversized batch can never
crash the shared DB mid-transaction.

Exit codes: 0 = proceed with the fetch, 1 = skip fetch (near cap),
2 = guard itself failed (treated as "proceed" by the caller but logged).
"""
import os
import sys
from pathlib import Path

MIN_FREE_MB = 20.0
CAP_MB = 512.0

ROOT = Path(__file__).resolve().parents[1]  # data_ingestion/

try:
    import psycopg
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    dsn = os.environ.get("DATABASE_URL_UNPOOLED")
    if not dsn:
        print("guard: DATABASE_URL_UNPOOLED not set")
        sys.exit(2)

    with psycopg.connect(dsn, connect_timeout=30) as conn:
        size_mb = float(conn.execute(
            "SELECT pg_database_size(current_database()) / 1048576.0"
        ).fetchone()[0])
except Exception as exc:  # network hiccup etc: fail open, log loudly
    print(f"guard: could not verify DB size ({exc})")
    sys.exit(2)

free_mb = CAP_MB - size_mb
print(
    f"guard: db at {size_mb:.1f}/{CAP_MB:.0f} MB, headroom {free_mb:.1f} MB "
    f"(threshold {MIN_FREE_MB:.1f} MB)"
)
sys.exit(1 if free_mb < MIN_FREE_MB else 0)
