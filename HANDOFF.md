# HANDOFF

Written 2026-10-17, as of commit `662c2c5` (the only commit so far — root
commit, "Initial commit: job posting ingestion pipeline"). For whoever picks
this up next, with zero prior context. Supersedes the previous version of
this doc, which was written *before* git was initialized and *before*
Postgres was backfilled — both of those are now done; see below.

## What this project is

A DATA-607 group-project data-ingestion pipeline: it fetches job postings
from 8 public job-board sources, normalizes them, and loads them into a
relational schema (`sources` / `companies` / `jobs` / `tags` / `job_tags`).
There is no separate spec doc — the code and `config/sources.yaml` are the
source of truth. `PIPELINE_DOCUMENTATION.md` / `.pdf` / `.tex` (root of this
directory) are a generated technical walkthrough of every file and the
end-to-end architecture; `METHODOLOGY.md` and `PLAN.md` one level up in
`../` (outside this git repo — see "Not fully in one repo" below) cover the
*why* behind source selection and scope decisions.

- `src/pipeline.py` — orchestrator: fetch → save raw JSON snapshot → parse →
  validate → load, once per source. `--backend {sqlite,postgres}` (default
  `sqlite`), `--db-url` override, `--sources` filter.
- `src/fetchers/*.py`, `src/parsers/*.py` — one pair per source
  (`remoteok`, `arbeitnow`, `jobicy`, `himalayas`, `wwr`, `hn_hiring`,
  `adzuna`, `usajobs`).
- `config/sources.yaml` — per-source config (base URL, rate limit, which raw
  fields are required, which sources need API keys).
- `scripts/run_daily.ps1` — invoked by a Windows Scheduled Task
  ("Data607-JobPipeline-DailyFetch"), logs to `logs/pipeline_<date>.log`.
  **Still SQLite-only** — see "Open decision" below.
- `scripts/migrate_sqlite_to_postgres.py` — new this session (105 lines).
  One-off/reusable backfill: reads every row out of SQLite, skips rows
  already present in Neon (matched on `(source name, external_id)`), upserts
  the rest. Idempotent and safe to re-run; commits every 150 rows so a crash
  mid-run doesn't lose progress (see "Neon migration had to be retried
  repeatedly" below — this is why that commit cadence exists).
- `scripts/check_sources.py` — pre-flight health/schema-drift/robots.txt
  auditor, unrelated to this session's work, unchanged.

## Not fully in one repo

This directory (`data_ingestion/`) is its own git repo as of this session
(`git init` + initial commit, `662c2c5`). The parent directory
("group project") is **not** a git repo and holds `METHODOLOGY.md`,
`PLAN.md`, `DB_SHARING_SETUP.md`, and a sibling `Project 3/` folder that
**is** its own separate git repo. Per that project's `CLAUDE.md`: `Project 3/`
is read-only for agents, and even read-only access requires asking the user
first each time — don't assume a prior read authorizes a later one. Nothing
in this session touched `Project 3/`.

## Current state: both stores populated, Postgres now caught up

The project has two live backends, both now holding real data as of this
session:

| Store | Rows in `jobs` | Latest `retrieved_at` | How it got there |
|---|---|---|---|
| SQLite (`data/db/jobs.db`, gitignored) | 2,877 | 2026-10-17T17:03:54Z | Daily scheduled task (`run_daily.ps1`) accumulating since ~Oct 12, plus one manual `python src/pipeline.py` run this session |
| Neon Postgres (`neondb`, project `broad-frost-05827113`) | 2,897 | 2026-10-17T17:16:37Z | One manual `python src/pipeline.py --backend postgres` run this session (1,003 rows), **plus** a full backfill via `scripts/migrate_sqlite_to_postgres.py` bringing in everything SQLite had |

Postgres has 20 *more* rows than SQLite, not an exact match — expected, not
a bug: the live `--backend postgres` run and the SQLite-accumulated history
were each independent fetches at different times, so each could pick up a
small number of postings the other didn't (sources return "currently live"
listings, not a fixed set). Don't try to force these two counts to be
exactly equal; what matters is that Postgres is no longer missing SQLite's
backlog, which it was before this session (it previously had only 1,003
rows — a single day's run with no history).

**Open decision, not resolved this session:** `scripts/run_daily.ps1` still
calls `python src\pipeline.py` with no `--backend` flag, i.e. the Scheduled
Task writes only to SQLite. Postgres will again silently fall behind SQLite
every day until someone either (a) updates `run_daily.ps1` to also pass
`--backend postgres`, or (b) decides SQLite remains the single source of
truth and periodically re-runs the migration script. **Nobody has made that
call — don't assume one over the other.**

## What's actually implemented

| Component | File | State |
|---|---|---|
| SQLite schema | `src/db/schema.sql` (39 lines) | Unchanged. `AUTOINCREMENT` ids. |
| SQLite loader | `src/db/load.py` (84 lines) | Unchanged. `sqlite3`, `?` placeholders. |
| Postgres schema | `src/db/schema_postgres.sql` (39 lines) | Same tables, `SERIAL` ids. Already applied to Neon (`CREATE TABLE IF NOT EXISTS`, idempotent). |
| Postgres loader | `src/db/load_postgres.py` (85 lines) | Line-for-line port of `load.py` to `psycopg` v3 (`%s` placeholders, no `PRAGMA foreign_keys`). Functions: `connect`, `get_or_create_source`, `get_or_create_company`, `upsert_job`, `upsert_tags`, `load_row` — same signatures as the SQLite version. |
| Pipeline backend switch | `src/pipeline.py` (132 lines) | `--backend {sqlite,postgres}` (default `sqlite`), `--db-url` override. Loads `.env` via `python-dotenv` at import time. |
| Migration script | `scripts/migrate_sqlite_to_postgres.py` (105 lines) | New this session. See above. Not covered by any automated test — it was run interactively and its row-count deltas were verified by hand each time (see run history below), not via `pytest`. |
| Tests | `tests/test_db_load.py` | Only covers the SQLite loader (3 tests). **No automated tests exist for `load_postgres.py` or `migrate_sqlite_to_postgres.py`.** |
| Pipeline documentation | `PIPELINE_DOCUMENTATION.md` / `.tex` / `.pdf` | Generated this session (compiled via local TinyTeX `pdflatex`, 11 pages). Two raw unescaped underscores in `.texttt{scripts/check_sources.py}` and `.texttt{scripts/run_daily.ps1}` were breaking the LaTeX build and were fixed (`\_` escaping) — if the `.tex` is regenerated wholesale later, re-check for this class of bug before recompiling. |
| Git repo | — | Initialized this session (`git init`, root commit `662c2c5`, 47 files). `.gitignore` extended to also exclude `.claude/` and `skills-lock.json` (Claude Code's local skill cache — not project content) in addition to the pre-existing `data/raw/`, `logs/`, `.env`; `data/db/` (the 21MB SQLite binary) was also added to `.gitignore` before the first commit, since it's a regenerated artifact, not source. |

Full suite: `python -m pytest -q` → **16 passed, 0 failed**, run fresh this
session (not carried over from memory).

## Environment / tooling notes

- **Neon project:** org `kailot` (`org-falling-bread-45273969`), project
  `Data 607 - Project 3` (`broad-frost-05827113`), database `neondb`,
  region `aws-us-east-1`. Auth is via `npx neon <cmd> --org-id
  org-falling-bread-45273969` (OAuth device flow already completed once on
  this machine).
- **`.env`** (gitignored, confirmed absent from the git commit) holds
  `DATABASE_URL` (pooled, `-pooler` host) and `DATABASE_URL_UNPOOLED`
  (direct host — this is what `pipeline.py --backend postgres` and
  `migrate_sqlite_to_postgres.py` both read). Neither value is reproduced
  here.
- **`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `USAJOBS_API_KEY`, `USAJOBS_EMAIL`**
  are machine-level environment variables, confirmed present — all 8
  sources load real rows in both backends (no `skipped_no_key` statuses
  observed in any run this session).
- **No `psql` on PATH** — all Postgres interaction this session went
  through `python -c "..."` one-liners / small scripts using `psycopg`, not
  a CLI.
- **TinyTeX is installed** at
  `C:\Users\kailo\AppData\Roaming\TinyTeX\bin\windows\` (`pdflatex`,
  `xelatex`, `lualatex` all present) — used to compile
  `PIPELINE_DOCUMENTATION.pdf`. A second, separate MiKTeX install also
  exists on this machine; the TinyTeX one was used.
- **Background shell commands on this machine get killed under memory
  pressure unpredictably**, independent of how much memory the Python
  process itself actually uses. The Postgres migration script above had to
  be re-run **five times** before it finished, because the background
  process kept getting killed with "system is running low on memory" partway
  through (confirmed via Neon row-count checks between attempts: 1003 → 2412
  → 2412 (no progress, killed before first commit) → 2712 → 2897/done). The
  fix that made this tractable was adding a pre-check in the migration
  script that skips `(source, external_id)` pairs already present in Neon,
  so each retry only has to redo the still-missing tail instead of
  restarting the whole 2,877-row set from scratch. If you hit this again on
  any future long-running script against this DB, apply the same pattern
  (idempotent upsert + skip-already-present + frequent commits) rather than
  assuming a single long-lived foreground run will succeed.
- **CLAUDE.md in the parent directory** sets hard rules about `Project 3/`
  (read-only, ask before any read) that apply regardless of which
  subdirectory an agent is invoked from — re-read it if touching anything
  outside `data_ingestion/`.

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
7. Dry-run via `python src/pipeline.py --sources <name>` (SQLite, default
   backend, safe/local) before ever pointing a new source at
   `--backend postgres` — Postgres is a shared resource other
   collaborators may be reading from.

## Reusable workflow (backfilling Postgres from SQLite again later)

If SQLite accumulates more history than Postgres again (e.g. because
`run_daily.ps1` keeps writing SQLite-only — see "Open decision" above),
re-run `python scripts/migrate_sqlite_to_postgres.py`. It is safe to run
repeatedly: it always re-derives the skip-set from Neon's current contents
first, so partial/interrupted runs just pick up where they left off on the
next invocation. Expect to need 2+ invocations if background-process memory
kills recur on this machine (see note above) — check the printed
before/after row counts each time rather than assuming one run finished the
job.

## Concrete next step

**Decide the SQLite-vs-Postgres resolution** — this is the one unresolved
decision left from this session, not a new task:

1. Ask the user (don't decide unilaterally): is Neon Postgres becoming the
   primary store, a mirror kept in sync via the migration script, or was
   the Postgres work just a one-off exercise with SQLite remaining
   canonical?
2. If Postgres becomes primary or a mirror: update `scripts/run_daily.ps1`
   line 13 (`$Output = & $Python "src\pipeline.py" 2>&1`) to add
   `--backend postgres`. Note `pipeline.py main()` currently picks **one**
   backend per invocation — writing to both SQLite and Postgres in a single
   scheduled run isn't supported yet and would need a small code change if
   the group wants both kept live simultaneously going forward.
3. Add automated tests for `src/db/load_postgres.py` (mirror
   `tests/test_db_load.py`'s 3 cases) and ideally a smoke test for
   `scripts/migrate_sqlite_to_postgres.py`'s skip-logic — both currently
   have zero test coverage and were only verified by hand/by the row-count
   deltas printed during this session's interactive runs.
4. After that, the two-steps-ahead item is updating `METHODOLOGY.md` (one
   directory up, in `../`) — it currently states Adzuna and USAJobs "have no
   parser wired in yet" and are "not currently contributing rows." That's no
   longer true: both fetchers *and* parsers exist and are loading real rows
   in this session's runs (50 and 66 rows respectively, each run). Whoever
   picks this up should re-verify that against a fresh pipeline run before
   editing `METHODOLOGY.md`, since that file lives outside this git repo and
   wasn't touched this session.
