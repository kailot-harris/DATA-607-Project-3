# HANDOFF

Written 2026-10-17. No git history to anchor to — **this directory is not a
git repository** (`git status` fails with "not a git repository"), so there
is no commit to cite as "as of." This doc reflects live file and database
state as of the timestamp above. For whoever picks this up next, with zero
prior context.

## What this project is

A DATA-607 group-project data-ingestion pipeline: it fetches job postings
from 8 public job-board sources, normalizes them, and loads them into a
relational schema (`sources` / `companies` / `jobs` / `tags` / `job_tags`).
There is no separate spec doc — the code and `config/sources.yaml` are the
source of truth.

- `src/pipeline.py` — orchestrator: fetch → save raw JSON snapshot → parse →
  validate → load, once per source.
- `src/fetchers/*.py`, `src/parsers/*.py` — one pair per source
  (`remoteok`, `arbeitnow`, `jobicy`, `himalayas`, `wwr`, `hn_hiring`,
  `adzuna`, `usajobs`).
- `config/sources.yaml` — per-source config (base URL, rate limit, which raw
  fields are required, which sources need API keys).
- `scripts/run_daily.ps1` — invoked by a Windows Scheduled Task
  ("Data607-JobPipeline-DailyFetch"), logs to `logs/pipeline_<date>.log`.

## Current state: two parallel, out-of-sync data stores

This is the most important thing to know before touching anything here.

The project originally had only a SQLite store (`data/db/jobs.db`,
schema in `src/db/schema.sql`, loader in `src/db/load.py`). This session
added a second backend: a Neon Postgres project, wired up as an *alternate*
backend behind `--backend postgres`, not a replacement. Both now have real
but **different** data:

| Store | Rows in `jobs` | Latest `retrieved_at` | How it got populated |
|---|---|---|---|
| SQLite (`data/db/jobs.db`) | 2877 | 2026-10-17T17:03:54Z | Daily scheduled task (`run_daily.ps1`), accumulating since ~Oct 12 |
| Neon Postgres (`neondb`, project `broad-frost-05827113`) | 1003 | 2026-10-17T17:16:37Z | One manual `python -m src.pipeline --backend postgres` run this session — a single day's worth, not a backfill |

**`scripts/run_daily.ps1` still calls `python src\pipeline.py` with no
`--backend` flag**, i.e. the Scheduled Task writes only to SQLite. Postgres
will silently fall behind every day until someone either (a) updates
`run_daily.ps1` to pass `--backend postgres`, or (b) decides SQLite remains
primary and Postgres was just a one-off exercise. **Nobody has made that
call yet — don't assume one over the other.**

## What's actually implemented

| Component | File | State |
|---|---|---|
| SQLite schema | `src/db/schema.sql` (39 lines) | Original, unchanged. `AUTOINCREMENT` ids. |
| SQLite loader | `src/db/load.py` (84 lines) | Original, unchanged. `sqlite3`, `?` placeholders. |
| Postgres schema | `src/db/schema_postgres.sql` (39 lines) | New this session. Same tables, `SERIAL` ids. Already applied to Neon (`CREATE TABLE IF NOT EXISTS`, idempotent). |
| Postgres loader | `src/db/load_postgres.py` (85 lines) | New this session. Line-for-line port of `load.py` to `psycopg` v3 (`%s` placeholders, no `PRAGMA foreign_keys`). Functions: `connect`, `get_or_create_source`, `get_or_create_company`, `upsert_job`, `upsert_tags`, `load_row` — same signatures as the SQLite version. |
| Pipeline backend switch | `src/pipeline.py` (132 lines) | `--backend {sqlite,postgres}` (default `sqlite` — existing behavior untouched), `--db-url` override. Loads `.env` via `python-dotenv` at import time. |
| Tests | `tests/test_db_load.py` | Only covers the SQLite loader (3 tests). **No automated tests exist for `load_postgres.py`** — it was verified once by hand this session (idempotency + tags, against the live Neon DB, with cleanup), not via `pytest`. |

Full suite: `python -m pytest -q` → 16 passed, 0 failed, as of this session.

## Environment / tooling notes

- **Not a git repo.** If this project is meant to be tracked in git,
  nobody has run `git init` yet. Flagging, not fixing — that's a decision
  for the project owner, not something to do silently in a handoff.
- **Neon project:** org `kailot` (`org-falling-bread-45273969`), project
  `Data 607 - Project 3` (`broad-frost-05827113`), database `neondb`,
  region `aws-us-east-1`. Auth is via `npx neon <cmd> --org-id
  org-falling-bread-45273969` (OAuth device flow already completed once on
  this machine).
- **`.env`** (gitignored, confirmed in `.gitignore`) holds `DATABASE_URL`
  (pooled, `-pooler` host — use for normal app queries) and
  `DATABASE_URL_UNPOOLED` (direct host — use for schema/DDL work,
  migrations, `pg_dump`). Neither value is reproduced here.
- **`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `USAJOBS_API_KEY`, `USAJOBS_EMAIL`**
  are set as machine-level environment variables (not in `.env` — checked,
  `.env` only contains the two `DATABASE_URL*` lines). They're present and
  presumably valid, since all 8 sources show up as populated in both
  stores (i.e. `adzuna`/`usajobs` aren't being skipped with
  `skipped_no_key`).
  - **Incident:** earlier in this session, a careless bash
    `${VAR:+yes}${VAR:-no}` presence-check actually printed partial values
    of `ADZUNA_APP_ID` and `USAJOBS_API_KEY` into the chat transcript (bug:
    `:-` only substitutes when a var is *unset*, not when checking
    "present" — when the var *is* set, `${VAR:-no}` yields the real value,
    not `no`). The values were not written to any file, but they did land
    in a conversation transcript. The user was told in-session and advised
    to consider rotating those two keys. Worth knowing so nobody re-prints
    them the same way.
- **Python 3.11.9**, deps in `requirements.txt`. This session added
  `psycopg[binary]>=3.1` and `python-dotenv>=1.0`; both are installed in
  the active environment.
- **No `psql` on PATH** — Postgres smoke-testing this session went through
  `python -c "..."` one-liners with `psycopg`, not a CLI.

## Reusable workflow (for adding a 9th source, or similar)

This project's established pattern, inferred from the existing 8 sources —
follow it rather than inventing a new shape:

1. Add a `sources.<name>` block to `config/sources.yaml` (base URL, rate
   limit, `required_fields`, `requires_key`/`credential_env` if needed).
2. Write `src/fetchers/<name>.py` (needs `has_credentials(cfg)` and
   `fetch_all(session, cfg)` returning `(raw, records)`).
3. Write `src/parsers/<name>.py` (`parse_record(record, retrieved_at)` →
   row dict matching the `jobs` table shape, including `tags_raw`).
4. Register both in `src/pipeline.py`'s `SOURCES` dict.
5. Add fixtures/tests under `tests/` mirroring the existing parser tests.
6. Run `python -m pytest -q`.
7. Dry-run via `python -m src.pipeline --sources <name>` (SQLite, safe/local)
   before ever pointing a new source at `--backend postgres`.

## Concrete next step

**Decide and implement the SQLite-vs-Postgres resolution** described above
— this is the actual unfinished piece of this session's work, not a new
task:

1. Decide: is Neon Postgres becoming the primary store, a mirror, or was it
   just an exercise? (Not this agent's/session's call — ask the user if
   picking this back up without them.)
2. If Postgres becomes primary or a mirror: update
   `scripts/run_daily.ps1` line 13 (`& $Python "src\pipeline.py" 2>&1`) to
   add `--backend postgres`, and decide whether SQLite writes should
   continue in parallel (would need `pipeline.py` to support writing to
   *both* backends in one run — not currently supported, `main()` picks
   one backend per invocation).
3. Either way, Postgres is currently missing the Oct 12–16 history that
   only lives in `data/raw/<source>/<date>/data.json` snapshots and in
   SQLite. If backfilling Postgres, the raw JSON snapshots can be replayed
   through the parsers without re-fetching (`fetcher.fetch_all` isn't
   strictly required if replaying from `data/raw/.../data.json` — would need
   a small script, not currently written).
4. Add automated tests for `src/db/load_postgres.py` (mirror
   `tests/test_db_load.py`, but note it needs a real Postgres connection —
   either point at a Neon branch created for testing, or skip-if-no-DSN).
