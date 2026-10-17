# Technical Documentation & Code Audit: Data Ingestion Pipeline

**Repository:** `data_ingestion`  
**Domain:** Multi-Source Job Market Data Ingestion & Normalization Engine  
**Target Environments:** Local SQLite (`data/db/jobs.db`) / Cloud PostgreSQL (`Neon`)  
**Execution Context:** Scheduled Automated Batch Pipeline (Windows Task Scheduler / CLI)  
**Document Version:** 1.0.0  

---

## SECTION 1: REPOSITORY & DIRECTORY WALKTHROUGH

### 1. Directory Tree Overview

```
data_ingestion/
├── config/
│   └── sources.yaml                # Source configurations, rate limits, and contract schemas
├── data/
│   ├── db/
│   │   └── jobs.db                 # SQLite database target (local execution)
│   └── raw/                        # Daily raw immutable payload snapshots
│       ├── adzuna/<date>/data.json
│       ├── arbeitnow/<date>/data.json
│       ├── himalayas/<date>/data.json
│       ├── hn_hiring/<date>/data.json
│       ├── jobicy/<date>/data.json
│       ├── remoteok/<date>/data.json
│       ├── usajobs/<date>/data.json
│       └── wwr/<date>/data.json
├── logs/
│   ├── pipeline_YYYY-MM-DD.log     # Pipeline execution logs and batch summary outputs
│   └── source_health_YYYY-MM-DD.json # Pre-flight diagnostic audits and latency telemetry
├── scripts/
│   ├── check_sources.py            # Pre-flight liveness, schema drift & robots.txt auditor
│   └── run_daily.ps1               # Production entrypoint wrapper for Windows Task Scheduler
├── src/
│   ├── pipeline.py                 # Core CLI orchestrator driving fetch -> store -> parse -> load
│   ├── db/
│   │   ├── __init__.py             # Database module initialization
│   │   ├── load.py                 # SQLite idempotent persistence engine
│   │   ├── load_postgres.py        # PostgreSQL (Neon) idempotent persistence engine
│   │   ├── schema.sql              # Normalized SQLite DDL schema
│   │   └── schema_postgres.sql     # Normalized PostgreSQL DDL schema
│   ├── fetchers/
│   │   ├── __init__.py             # Fetcher package namespace
│   │   ├── base.py                 # Shared HTTP client: rate limiting, retries, headers
│   │   ├── adzuna.py               # REST API client for Adzuna (API Key + App ID)
│   │   ├── arbeitnow.py            # REST API client for Arbeitnow
│   │   ├── himalayas.py            # REST API client for Himalayas
│   │   ├── hn_hiring.py            # Algolia API client for Hacker News 'Who is hiring'
│   │   ├── jobicy.py               # REST API client for Jobicy
│   │   ├── remoteok.py             # REST API client for RemoteOK
│   │   ├── usajobs.py              # REST API client for USAJobs (Authorization-Key)
│   │   └── wwr.py                  # RSS XML feed client for We Work Remotely
│   └── parsers/
│       ├── __init__.py             # Canonical row schema definition & validation logic
│       ├── adzuna.py               # Adzuna payload normalizer
│       ├── arbeitnow.py            # Arbeitnow payload normalizer
│       ├── himalayas.py            # Himalayas payload normalizer
│       ├── hn_hiring.py            # HN comment payload normalizer
│       ├── jobicy.py               # Jobicy payload normalizer
│       ├── remoteok.py             # RemoteOK payload normalizer
│       ├── usajobs.py              # USAJobs payload normalizer
│       └── wwr.py                  # We Work Remotely RSS normalizer
├── tests/
│   ├── conftest.py                 # Pytest root path resolution
│   ├── test_db_load.py             # Database upsert idempotency and relational tests
│   ├── test_parsers.py             # Normalization and contract validation tests
│   ├── test_rate_limit.py          # Monotonic throttling and interval isolation tests
│   ├── test_retry.py               # Tenacity exponential backoff and HTTP status tests
│   └── fixtures/                   # Real-world snapshot payloads for offline testing
│       ├── arbeitnow_sample.json
│       ├── himalayas_sample.json
│       ├── hn_hiring_sample.json
│       ├── jobicy_sample.json
│       ├── remoteok_sample.json
│       └── wwr_sample.json
└── requirements.txt                # Third-party Python dependencies
```

---

### 2. Folder-by-Folder Analysis

| Directory Path | Role in Ingestion Lifecycle |
| :--- | :--- |
| `config/` | **Configuration Layer:** Stores declarative YAML configuration files specifying ingestion metadata (target endpoints, rate limits, access modes, credentials requirements, and expected schema fields). |
| `scripts/` | **Operations & Automation:** Houses auxiliary automation tools, including pre-flight source health auditing scripts and scheduled operational wrappers (PowerShell runner). |
| `src/` | **Core Application Package:** Contains the top-level pipeline orchestrator driving the complete end-to-end extraction, normalization, and persistence workflow. |
| `src/fetchers/` | **Extraction Layer:** Encapsulates network communication with external APIs and RSS feeds. Handles respectful throttling, exponential retry/backoff, and raw snapshot extraction. |
| `src/parsers/` | **Transformation & Validation Layer:** Converts raw heterogeneous upstream JSON/RSS dictionaries into a standardized intermediate 13-field row schema while validating record integrity. |
| `src/db/` | **Loading & Storage Layer:** Implements normalized relational database targets (SQLite and PostgreSQL/Neon), DDL scripts, and idempotent upsert mechanisms. |
| `data/raw/` | **Data Lake / Raw Staging:** Immutable, date-partitioned landing zone where verbatim JSON/XML payloads land before transformation. |
| `data/db/` | **Local Storage Target:** Houses the SQLite relational database file (`jobs.db`) for local analytics. |
| `logs/` | **Telemetry & Observability:** Stores timestamped run logs and pre-flight diagnostic health check JSON reports. |
| `tests/` | **Quality Assurance:** Contains test fixtures and unit/integration test suites validating HTTP retries, rate-limiting, field parsers, and database upsert behaviors. |

---

### 3. File-by-File Breakdown

#### Configuration & Operations
*   `config/sources.yaml`
    *   **Primary Responsibility:** Defines source endpoints, rate-limiting constraints, authentication requirements, and contract schema fields across all 8 ingestion targets.
    *   **Key Declarations:** `contact_email`, `sources.<name>.base_url`, `rate_limit_sec`, `requires_key`, `credential_env`, `required_fields`.
    *   **Upstream Dependencies:** None.
    *   **Downstream Consumers:** `src/pipeline.py`, `scripts/check_sources.py`.
*   `scripts/check_sources.py`
    *   **Primary Responsibility:** Executes pre-flight diagnostics across all sources, evaluating endpoint liveness, latency, schema drift against `required_fields`, and `robots.txt` compliance.
    *   **Key Classes & Functions:** `check_robots()`, `check_source()`, `main()`.
    *   **Upstream Dependencies:** `requests`, `yaml`, `urllib.robotparser`, `src.fetchers.*`, `config/sources.yaml`.
    *   **Downstream Consumers:** Invoked manually or in CI/CD pre-flight checks; outputs to `logs/source_health_<date>.json`.
*   `scripts/run_daily.ps1`
    *   **Primary Responsibility:** Production execution wrapper invoked daily by Windows Task Scheduler (`Data607-JobPipeline-DailyFetch`), executing the pipeline and appending stdout/stderr to dated logs.
    *   **Key Directives:** `$Python`, `$LogFile`, `Set-Location`, execution of `src/pipeline.py`.
    *   **Upstream Dependencies:** Windows PowerShell, Python runtime.
    *   **Downstream Consumers:** Windows Task Scheduler.

#### Orchestration Layer
*   `src/pipeline.py`
    *   **Primary Responsibility:** Master pipeline orchestrator that iterates over active sources, executes extraction, persists raw payloads, invokes parsers and validation, and loads rows into the database.
    *   **Key Classes & Functions:** `run_source()`, `main()`.
    *   **Upstream Dependencies:** `argparse`, `requests`, `yaml`, `dotenv`, `src.fetchers.*`, `src.parsers.*`, `src.db.load`, `src.db.load_postgres`.
    *   **Downstream Consumers:** `scripts/run_daily.ps1`, command-line operators.

#### Fetchers (Extraction Layer)
*   `src/fetchers/base.py`
    *   **Primary Responsibility:** Provides shared HTTP networking utilities including monotonic rate-limit throttling, exponential backoff retries via Tenacity, and standard User-Agent header generation.
    *   **Key Classes & Functions:** `throttle()`, `build_headers()`, `_is_retryable()`, `get()`.
    *   **Upstream Dependencies:** `requests`, `tenacity`.
    *   **Downstream Consumers:** All source-specific fetchers in `src/fetchers/`, `scripts/check_sources.py`.
*   `src/fetchers/remoteok.py`
    *   **Primary Responsibility:** Fetches complete active job listing from the RemoteOK public REST endpoint, stripping the non-posting legal header object.
    *   **Key Functions:** `fetch_sample()`, `fetch_all`.
    *   **Upstream Dependencies:** `src.fetchers.base`.
    *   **Downstream Consumers:** `src/pipeline.py`, `scripts/check_sources.py`.
*   `src/fetchers/arbeitnow.py`
    *   **Primary Responsibility:** Fetches active listings from the Arbeitnow API endpoint.
    *   **Key Functions:** `fetch_sample()`, `fetch_all`.
    *   **Upstream Dependencies:** `src.fetchers.base`.
    *   **Downstream Consumers:** `src/pipeline.py`, `scripts/check_sources.py`.
*   `src/fetchers/jobicy.py`
    *   **Primary Responsibility:** Fetches remote job postings from the Jobicy v2 API supporting sample and batch counts (up to 50 items).
    *   **Key Functions:** `_fetch()`, `fetch_sample()`, `fetch_all()`.
    *   **Upstream Dependencies:** `src.fetchers.base`.
    *   **Downstream Consumers:** `src/pipeline.py`, `scripts/check_sources.py`.
*   `src/fetchers/himalayas.py`
    *   **Primary Responsibility:** Queries the Himalayas REST API with configurable record limits.
    *   **Key Functions:** `_fetch()`, `fetch_sample()`, `fetch_all()`.
    *   **Upstream Dependencies:** `src.fetchers.base`.
    *   **Downstream Consumers:** `src/pipeline.py`, `scripts/check_sources.py`.
*   `src/fetchers/wwr.py`
    *   **Primary Responsibility:** Downloads and parses the We Work Remotely RSS feed into raw entries.
    *   **Key Functions:** `fetch_sample()`, `fetch_all`.
    *   **Upstream Dependencies:** `feedparser`, `src.fetchers.base`.
    *   **Downstream Consumers:** `src/pipeline.py`, `scripts/check_sources.py`.
*   `src/fetchers/hn_hiring.py`
    *   **Primary Responsibility:** Two-step fetcher querying Algolia HN API: resolves the latest "Ask HN: Who is hiring?" submission, then extracts child comment postings (up to 1,000 hits).
    *   **Key Functions:** `_find_latest_thread()`, `_fetch_comments()`, `fetch_sample()`, `fetch_all()`.
    *   **Upstream Dependencies:** `src.fetchers.base`.
    *   **Downstream Consumers:** `src/pipeline.py`, `scripts/check_sources.py`.
*   `src/fetchers/adzuna.py`
    *   **Primary Responsibility:** Queries Adzuna US Job Search API with authentication credentials (`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`) for data science roles.
    *   **Key Functions:** `has_credentials()`, `fetch_sample()`, `fetch_all`.
    *   **Upstream Dependencies:** `os`, `src.fetchers.base`.
    *   **Downstream Consumers:** `src/pipeline.py`, `scripts/check_sources.py`.
*   `src/fetchers/usajobs.py`
    *   **Primary Responsibility:** Authenticates against USAJobs API (`USAJOBS_API_KEY`, `USAJOBS_EMAIL`), extracting and flattening nested `MatchedObjectDescriptor` records.
    *   **Key Functions:** `has_credentials()`, `fetch_sample()`, `fetch_all`.
    *   **Upstream Dependencies:** `os`, `src.fetchers.base`.
    *   **Downstream Consumers:** `src/pipeline.py`, `scripts/check_sources.py`.

#### Parsers (Transformation & Validation Layer)
*   `src/parsers/__init__.py`
    *   **Primary Responsibility:** Defines canonical 13-column `ROW_FIELDS` tuple, empty schema generator, and pre-load validation rules.
    *   **Key Constants & Functions:** `ROW_FIELDS`, `empty_row()`, `validate_row()`.
    *   **Upstream Dependencies:** `urllib.parse.urlparse`.
    *   **Downstream Consumers:** All individual parsers in `src/parsers/`, `src/pipeline.py`, test suites.
*   `src/parsers/remoteok.py`
    *   **Primary Responsibility:** Maps RemoteOK payload dictionaries to standard rows with remote flags.
    *   **Key Functions:** `parse_record()`.
    *   **Upstream Dependencies:** `src.parsers.empty_row`.
    *   **Downstream Consumers:** `src/pipeline.py`.
*   `src/parsers/arbeitnow.py`
    *   **Primary Responsibility:** Maps Arbeitnow postings; converts Unix epoch timestamps to ISO8601 UTC strings.
    *   **Key Functions:** `parse_record()`.
    *   **Upstream Dependencies:** `datetime`, `src.parsers.empty_row`.
    *   **Downstream Consumers:** `src/pipeline.py`.
*   `src/parsers/jobicy.py`
    *   **Primary Responsibility:** Normalizes Jobicy postings, extracting excerpt/description and salary bounds.
    *   **Key Functions:** `parse_record()`.
    *   **Upstream Dependencies:** `src.parsers.empty_row`.
    *   **Downstream Consumers:** `src/pipeline.py`.
*   `src/parsers/himalayas.py`
    *   **Primary Responsibility:** Transforms Himalayas records; joins array-based `locationRestrictions` into clean comma-delimited strings.
    *   **Key Functions:** `parse_record()`.
    *   **Upstream Dependencies:** `src.parsers.empty_row`.
    *   **Downstream Consumers:** `src/pipeline.py`.
*   `src/parsers/wwr.py`
    *   **Primary Responsibility:** Normalizes RSS feed items; parses composite `"Company: Title"` strings and extracts tags from RSS metadata objects.
    *   **Key Functions:** `parse_record()`.
    *   **Upstream Dependencies:** `src.parsers.empty_row`.
    *   **Downstream Consumers:** `src/pipeline.py`.
*   `src/parsers/hn_hiring.py`
    *   **Primary Responsibility:** Normalizes unstructured HN comments into verbatim text without speculative regex parsing, constructing permalink URLs from `objectID`.
    *   **Key Functions:** `parse_record()`.
    *   **Upstream Dependencies:** `src.parsers.empty_row`.
    *   **Downstream Consumers:** `src/pipeline.py`.
*   `src/parsers/adzuna.py`
    *   **Primary Responsibility:** Normalizes Adzuna API response dictionaries, unwrapping nested location and company display names.
    *   **Key Functions:** `parse_record()`.
    *   **Upstream Dependencies:** `src.parsers.empty_row`.
    *   **Downstream Consumers:** `src/pipeline.py`.
*   `src/parsers/usajobs.py`
    *   **Primary Responsibility:** Extracts USAJobs remuneration minimum/maximum ranges to floating-point numbers, mapping civil service categories to tags.
    *   **Key Functions:** `_salary_bound()`, `parse_record()`.
    *   **Upstream Dependencies:** `src.parsers.empty_row`.
    *   **Downstream Consumers:** `src/pipeline.py`.

#### Database Layer (Persistence)
*   `src/db/schema.sql`
    *   **Primary Responsibility:** SQLite DDL schema defining 5 normalized tables (`sources`, `companies`, `jobs`, `tags`, `job_tags`) and composite unique constraints.
    *   **Upstream Dependencies:** None.
    *   **Downstream Consumers:** `src/db/load.py`.
*   `src/db/schema_postgres.sql`
    *   **Primary Responsibility:** PostgreSQL/Neon DDL schema using `SERIAL` auto-incrementing identity keys and identical relational constraints.
    *   **Upstream Dependencies:** None.
    *   **Downstream Consumers:** `src/db/load_postgres.py`.
*   `src/db/load.py`
    *   **Primary Responsibility:** Local SQLite database persistence driver; executes schema migration on connect and executes idempotent upsert queries.
    *   **Key Functions:** `connect()`, `get_or_create_source()`, `get_or_create_company()`, `upsert_job()`, `upsert_tags()`, `load_row()`.
    *   **Upstream Dependencies:** `sqlite3`, `src/db/schema.sql`.
    *   **Downstream Consumers:** `src/pipeline.py`, `tests/test_db_load.py`.
*   `src/db/load_postgres.py`
    *   **Primary Responsibility:** Production PostgreSQL / Neon persistence driver; executes schema migrations and uses `psycopg` with `%s` parameter interpolation.
    *   **Key Functions:** `connect()`, `get_or_create_source()`, `get_or_create_company()`, `upsert_job()`, `upsert_tags()`, `load_row()`.
    *   **Upstream Dependencies:** `psycopg`, `src/db/schema_postgres.sql`.
    *   **Downstream Consumers:** `src/pipeline.py`.

#### Test Suite
*   `tests/conftest.py`: Bootstraps `sys.path` to include repository root during test runs.
*   `tests/test_parsers.py`: Validates all parser implementations against recorded offline JSON fixtures.
*   `tests/test_db_load.py`: Verifies relational schema creation, tag replacement, and idempotent upserts.
*   `tests/test_rate_limit.py`: Asserts monotonic timer accuracy and rate-key isolation.
*   `tests/test_retry.py`: Validates HTTP error handling, checking retry on 429/503 and immediate failure on 404.

---

## SECTION 2: END-TO-END PIPELINE ARCHITECTURE

### 1. Architecture Diagram

```mermaid
graph TD
    subgraph Trigger_and_Orchestration ["Trigger & Orchestration"]
        CRON["Windows Task Scheduler<br>('Data607-JobPipeline-DailyFetch')"] --> PS["scripts/run_daily.ps1"]
        CLI["Manual CLI Execution<br>(python src/pipeline.py)"] --> PIPE["src/pipeline.py (Master Orchestrator)"]
        PS --> PIPE
        CFG[("config/sources.yaml")] -.->|Load config, rate limits, keys| PIPE
    end

    subgraph Source_Extraction ["Source Extraction Layer (src/fetchers/*)"]
        PIPE -->|Iterate Sources| BASE["src/fetchers/base.py<br>throttle() + Tenacity retry + User-Agent"]
        BASE -->|HTTP GET| S1["RemoteOK (REST API)"]
        BASE -->|HTTP GET| S2["Arbeitnow (REST API)"]
        BASE -->|HTTP GET| S3["Jobicy (REST API)"]
        BASE -->|HTTP GET| S4["Himalayas (REST API)"]
        BASE -->|HTTP GET| S5["WeWorkRemotely (RSS/XML)"]
        BASE -->|HTTP GET| S6["Hacker News (Algolia API)"]
        BASE -->|Auth GET| S7["Adzuna (REST API)"]
        BASE -->|Auth GET| S8["USAJobs (REST API)"]
    end

    subgraph Raw_Staging ["Raw Staging / Landing Zone"]
        S1 & S2 & S3 & S4 & S5 & S6 & S7 & S8 --> RAW_WRITE["Persist Raw JSON Payload"]
        RAW_WRITE --> LAKE[("data/raw/&lt;source&gt;/&lt;date&gt;/data.json")]
    end

    subgraph Transformation_Validation ["Transformation & Validation Layer (src/parsers/*)"]
        RAW_WRITE --> PARSER_DISPATCH["src/parsers/&lt;source&gt;.py<br>parse_record()"]
        PARSER_DISPATCH --> ROW_INIT["src/parsers/__init__.py<br>empty_row() (ROW_FIELDS contract)"]
        ROW_INIT --> VAL{"validate_row()<br>Required fields? Valid URL?"}
        VAL -->|Invalid| DISCARD["Increment invalid counter & Skip"]
        VAL -->|Valid| ROW_OBJ["Standardized Row Dictionary"]
    end

    subgraph Destination_Persistence ["Destination Loading Layer (src/db/*)"]
        ROW_OBJ --> LOADER{"Backend Selector<br>(--backend sqlite | postgres)"}
        LOADER -->|sqlite| SQLITE_MOD["src/db/load.py"]
        LOADER -->|postgres| PG_MOD["src/db/load_postgres.py"]
        
        SQLITE_MOD --> REL_LOAD["Idempotent Upsert Engine"]
        PG_MOD --> REL_LOAD
        
        REL_LOAD --> T1["sources<br>(ON CONFLICT name DO UPDATE)"]
        REL_LOAD --> T2["companies<br>(ON CONFLICT name DO NOTHING)"]
        REL_LOAD --> T3["jobs<br>(ON CONFLICT source_id, external_id DO UPDATE)"]
        REL_LOAD --> T4["tags & job_tags<br>(DELETE old tags + INSERT ON CONFLICT)"]
        
        T1 & T2 & T3 & T4 --> DB_SQLITE[("SQLite: data/db/jobs.db")]
        T1 & T2 & T3 & T4 --> DB_PG[("PostgreSQL: Neon Cloud Database")]
    end
```

---

### 2. Data Lifecycle Stages

#### 1. Ingestion Trigger
*   **Production Trigger:** Controlled by a daily Windows Task Scheduler job named `Data607-JobPipeline-DailyFetch`. The task executes the PowerShell wrapper script `scripts/run_daily.ps1` using the local Python 3.11 runtime.
*   **Ad-hoc / Diagnostic Trigger:** Executed manually via the CLI with `src/pipeline.py`, which supports running specific sources (`--sources`) and switching storage engines (`--backend postgres`).
*   **Pre-flight Trigger:** Executed via `scripts/check_sources.py` to assess upstream API availability before triggering batch runs.

#### 2. Source Extraction
*   **Extraction Pattern:** Batch snapshot extraction. Each source is queried using a pull-based REST API call or an RSS feed fetch.
*   **Upstream Sources:**
    *   *RemoteOK:* Single HTTP request retrieving the full unpaginated active listing.
    *   *Arbeitnow:* Single HTTP request returning recent postings.
    *   *Jobicy:* Parameterized batch fetch (`count=50`, API maximum).
    *   *Himalayas:* Parameterized batch fetch (`limit=100`).
    *   *We Work Remotely (WWR):* RSS XML feed fetch, parsed into Python dictionaries via `feedparser`.
    *   *Hacker News ("Who is hiring"):* Two-stage extraction via Algolia Search API. Queries Algolia for the latest monthly story thread matching `"Ask HN: Who is hiring"`, then queries child comments using `tags=comment,story_<objectID>` with `hitsPerPage=1000`.
    *   *Adzuna:* Authenticated search query (`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`) for data science roles (`results_per_page=50`).
    *   *USAJobs:* Authenticated query (`USAJOBS_API_KEY`, `USAJOBS_EMAIL`) for data scientist postings (`ResultsPerPage=250`).
*   **Polite Scraping Enforcement:** All requests flow through `src/fetchers/base.py`, enforcing source-specific minimum intervals (`rate_limit_sec`), descriptive `User-Agent` headers containing project contact details, and exponential retries on transient errors.

#### 3. Staging / Raw Persistence
*   Before parsing, every raw payload response is saved to disk:
    $$\text{data/raw/}\langle\text{source}\rangle/\langle\text{YYYY-MM-DD}\rangle/\text{data.json}$$
*   This landing zone guarantees full auditability and enables replaying parsers offline without repeating upstream network requests.

#### 4. Validation & Transformation
*   **Normalization:** Each source module in `src/parsers/` implements `parse_record(raw, retrieved_at)`, transforming heterogeneous raw keys into a standardized 13-column row dictionary.
*   **Zero-Inference Policy:** As designed in the parsing layer, free-text or ambiguous fields (such as Hacker News comments) are stored verbatim in `description_raw` without regex-based title/company guesswork.
*   **Pre-load Validation:** `validate_row(row)` checks:
    1.  Non-null presence of primary keys: `source`, `external_id`, and `retrieved_at`.
    2.  URL validity: Verifies using `urllib.parse.urlparse` that any populated `url` contains both a valid URI `scheme` (e.g., `http`/`https`) and `netloc`.
*   Records failing validation are dropped from the database transaction and logged in the batch summary metrics.

#### 5. Loading & Destination
*   **Storage Target:** Local SQLite (`data/db/jobs.db`) or Cloud PostgreSQL (`Neon`).
*   **Write Pattern:** Idempotent upsert (`INSERT ... ON CONFLICT DO UPDATE`).
    *   `sources`: Upserted on `name`.
    *   `companies`: Upserted on `name` (`ON CONFLICT DO NOTHING`).
    *   `jobs`: Upserted on composite natural key `(source_id, external_id)`. If a job already exists, all mutable metadata (`title`, `location`, `remote_type`, `posted_date`, `retrieved_at`, `url`, `salary_min`, `salary_max`, `description_raw`) is updated in place without duplicate key errors.
    *   `job_tags`: Existing associations for `job_id` are purged and re-inserted against normalized `tags`, preventing tag drift between runs.

---

## SECTION 3: CODE SECTION & LOGIC BREAKDOWN

### Logical Section 1: Configuration & Pipeline Orchestration
*   **Related Files:**
    *   `config/sources.yaml`
    *   `src/pipeline.py`
*   **Detailed Mechanism:**
    1.  `main()` loads environment variables from `.env` via `python-dotenv` and parses CLI flags (`--sources`, `--db`, `--backend`, `--db-url`).
    2.  Parses `config/sources.yaml` to obtain contact emails, target URLs, rate limits, and authentication mappings.
    3.  Initializes a persistent `requests.Session()` and connects to the selected database backend (SQLite by default or PostgreSQL).
    4.  Iterates over each configured source:
        *   Skips disabled sources (`enabled: false`).
        *   Filters by the `--sources` argument if provided.
        *   Delegates extraction, disk snapshotting, parsing, and loading to `run_source()`.
        *   Executes `conn.commit()` after each source, guaranteeing transaction boundaries per source.
    5.  Prints an aligned execution table showing `fetched`, `loaded`, `invalid`, and any caught exceptions, concluding with a count query against `jobs`.
*   **Key Functions / Methods:**
    *   `run_source(name, scfg, contact_email, session, run_date, conn, loader) -> dict`:
        *   *Parameters:* Source name identifier, source configuration dictionary, contact email string, requests session, ISO execution date, active database connection, and selected DB loader module.
        *   *Operational Behavior:* Checks credentials; calls `fetcher.fetch_all()`; writes raw snapshot to `data/raw/<name>/<run_date>/data.json`; iterates records, passing each to `parser.parse_record()`; validates with `validate_row()`; invokes `loader.load_row()`.
        *   *Return Value:* Telemetry dictionary: `{"source": str, "status": str, "fetched": int, "loaded": int, "invalid": int, ["error": str]}`.
        *   *Side Effects:* Writes disk files under `data/raw/`; writes rows to relational database tables.
    *   `main()`:
        *   *Operational Behavior:* CLI entry point. Parses command arguments, establishes DB connection, iterates configured sources, commits transactions, and logs summary metrics.
*   **Data Schemas & Contracts:**
    *   *Input Contract:* YAML structure in `sources.yaml` requiring top-level keys `contact_email` and `sources` (mapping source names to properties `enabled`, `access_type`, `base_url`, `rate_limit_sec`, `requires_key`, `required_fields`).
    *   *Output Contract:* Telemetry status dictionary (`source`, `status`, `fetched`, `loaded`, `invalid`).
*   **State Management & Watermarking:**
    *   Snapshots are partitioned by run date (`run_date = datetime.date.today().isoformat()`).
    *   Transactions are committed on a per-source boundary (`conn.commit()`), preventing failure in one source from rolling back previously ingested sources.
*   **Error Handling & Resilience:**
    *   Missing credentials trigger an early graceful bypass (`status: "skipped_no_key"`).
    *   A broad `try...except Exception` wraps the network fetch stage; any failure sets `status: "fetch_error"`, records the exception class and message, and continues processing remaining sources without crashing the run.

---

### Logical Section 2: HTTP Infrastructure & Ingestion Politeness
*   **Related Files:**
    *   `src/fetchers/base.py`
*   **Detailed Mechanism:**
    1.  **Monotonic Throttling:** Maintains a module-level dictionary `_last_call_at` mapping `rate_key` identifiers to floating-point timestamps using `time.monotonic()`. When `throttle()` is called, it calculates the remaining time required to satisfy `min_interval_sec` and calls `time.sleep()`.
    2.  **Identified User-Agent:** `build_headers()` constructs a transparent User-Agent string adhering to web standards:  
        `"data607-job-pipeline-research/0.1 (school project; contact: <contact_email>)"`.
    3.  **Tenacity Exponential Retry:** Wraps HTTP GET operations using `@retry` with:
        *   `stop=stop_after_attempt(4)`: Maximum 4 request attempts.
        *   `wait=wait_exponential(multiplier=1, min=1, max=10)`: Exponential wait starting at 1 second up to 10 seconds.
        *   `retry=retry_if_exception(_is_retryable)`: Filters errors, retrying only transient status codes.
        *   `reraise=True`: Re-raises the final error upon retry exhaustion.
*   **Key Functions / Methods:**
    *   `throttle(rate_key: str, min_interval_sec: float) -> None`: Blocks execution until the configured interval has elapsed since the last invocation under `rate_key`.
    *   `build_headers(contact_email: str) -> dict`: Constructs standard request headers including User-Agent.
    *   `_is_retryable(exc: BaseException) -> bool`: Returns `True` if `exc` is a `requests.HTTPError` with status code 429 (Too Many Requests), 500 (Internal Server Error), 502 (Bad Gateway), 503 (Service Unavailable), or 504 (Gateway Timeout).
    *   `get(session: requests.Session, url: str, *, rate_key: str, min_interval_sec: float, timeout: float = 15, **kwargs) -> requests.Response`: Executes rate-limited GET with retries and timeout enforcement, invoking `resp.raise_for_status()`.
*   **Data Schemas & Contracts:**
    *   Input: `requests.Session`, target URL string, keyword rate limit configuration.
    *   Output: `requests.Response` instance guaranteed to have a 2xx HTTP status.
*   **State Management & Watermarking:**
    *   In-memory state dictionary `_last_call_at: dict[str, float]` ensures intervals are tracked across requests within a single process.
*   **Error Handling & Resilience:**
    *   Explicitly distinguishes between transient errors (429, 5xx) and fatal client errors (400, 401, 403, 404). Fatal client errors fail immediately without retry waste.

---

### Logical Section 3: Source Extractors / Fetchers
*   **Related Files:**
    *   `src/fetchers/remoteok.py`
    *   `src/fetchers/arbeitnow.py`
    *   `src/fetchers/jobicy.py`
    *   `src/fetchers/himalayas.py`
    *   `src/fetchers/wwr.py`
    *   `src/fetchers/hn_hiring.py`
    *   `src/fetchers/adzuna.py`
    *   `src/fetchers/usajobs.py`
*   **Detailed Mechanism:**
    *   *RemoteOK:* Retrieves full payload array. Omits the first element if it lacks an `id` attribute (RemoteOK prefixes listings with a legal/metadata notice).
    *   *Arbeitnow:* Extracts the list under the JSON key `"data"`.
    *   *Jobicy:* Passes query parameter `count=50` to retrieve the batch max.
    *   *Himalayas:* Passes query parameter `limit=100`.
    *   *WWR:* Issues an HTTP GET to the RSS endpoint, passes content to `feedparser.parse()`, and converts feed entries to dictionaries.
    *   *HN Hiring:* First performs an Algolia query (`tags=story&query=Who is hiring`) to identify the newest submission titled `"Ask HN: Who is hiring"`. If found, triggers a second query targeting `tags=comment,story_<objectID>` with `hitsPerPage=1000`.
    *   *Adzuna:* Validates existence of `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`, requesting 50 data science postings.
    *   *USAJobs:* Validates `USAJOBS_API_KEY` and `USAJOBS_EMAIL`. Injects required headers (`Host`, `User-Agent: email`, `Authorization-Key: key`) and flattens nested items located inside `SearchResult -> SearchResultItems -> MatchedObjectDescriptor`.
*   **Key Functions / Methods:**
    *   `fetch_all(session, cfg) -> tuple[raw_payload, list[dict]]`: Common contract implemented by all fetchers. Returns the raw payload object for snapshotting and an extracted list of records for parsing.
    *   `fetch_sample(session, cfg) -> tuple[raw_payload, list[dict]]`: Fetches a minimal sample (typically 5 to 20 records) for health checks and fixture generation.
    *   `has_credentials(cfg) -> bool`: (Adzuna, USAJobs) Verifies that required environment variables exist.
*   **Data Schemas & Contracts:**
    *   Input: `session: requests.Session`, `cfg: dict` (derived from `sources.yaml`).
    *   Output: `tuple(raw, records)` where `raw` is JSON-serializable (dict/list) and `records` is a list of individual posting dictionaries.
*   **Error Handling & Resilience:**
    *   Sources requiring credentials cleanly report missing variables through `has_credentials()`, preventing runtime auth errors.
    *   In `hn_hiring.py`, if no active thread is returned by the Algolia search, it returns empty results `({"hits": []}, [])` rather than raising `IndexError`.

---

### Logical Section 4: Data Normalization & Quality Validation
*   **Related Files:**
    *   `src/parsers/__init__.py`
    *   `src/parsers/remoteok.py`
    *   `src/parsers/arbeitnow.py`
    *   `src/parsers/jobicy.py`
    *   `src/parsers/himalayas.py`
    *   `src/parsers/wwr.py`
    *   `src/parsers/hn_hiring.py`
    *   `src/parsers/adzuna.py`
    *   `src/parsers/usajobs.py`
*   **Detailed Mechanism:**
    1.  **Uniform Record Model:** Every parser instantiates an empty row with default `None` values via `empty_row()` based on `ROW_FIELDS`:
        ```python
        ROW_FIELDS = (
            "source", "external_id", "title", "company", "location", "remote_type",
            "posted_date", "retrieved_at", "url", "salary_min", "salary_max",
            "description_raw", "tags_raw",
        )
        ```
    2.  **Source-Specific Mapping Rules:**
        *   *RemoteOK:* Maps `position` $\to$ `title`, `apply_url` or `url` $\to$ `url`, forces `remote_type="remote"`.
        *   *Arbeitnow:* Converts numeric epoch timestamps (`created_at`) to ISO UTC format via `datetime.datetime.fromtimestamp()`. Maps `slug` $\to$ `external_id`.
        *   *Jobicy:* Maps `jobGeo` $\to$ `location`, `jobIndustry` $\to$ `tags_raw`, `pubDate` $\to$ `posted_date`.
        *   *Himalayas:* Converts list-based `locationRestrictions` into a single comma-separated string; maps `guid` $\to$ `external_id`.
        *   *WWR:* Splits composite titles formatted as `"Company: Job Title"` using `raw_title.partition(": ")`. Maps RSS tag dictionaries to string lists.
        *   *HN Hiring:* Sets `title`, `company`, `location`, `remote_type` to `None`. Generates deterministic permalink `https://news.ycombinator.com/item?id={objectID}` and stores verbatim comments in `description_raw`.
        *   *Adzuna:* Unwraps nested dictionaries `company.display_name`, `location.display_name`, and `category.tag`.
        *   *USAJobs:* Calls `_salary_bound()` to safely convert `MinimumRange` and `MaximumRange` strings to floating-point numbers.
    3.  **Schema Quality Validation:** `validate_row()` validates records pre-load, verifying primary keys and confirming URLs parse into non-empty schemes and network locations.
*   **Key Functions / Methods:**
    *   `empty_row(**overrides) -> dict`: Returns a dictionary initialized with all keys from `ROW_FIELDS` set to `None`, applying provided overrides.
    *   `validate_row(row: dict) -> list[str]`: Returns a list of error descriptions if any required fields are missing or if URLs are malformed.
    *   `parse_record(raw: dict, retrieved_at: str) -> dict`: Transforms raw dictionary to normalized row dictionary.
*   **Error Handling & Resilience:**
    *   Defensive navigation (`raw.get(...) or None`) prevents `KeyError` crashes on missing upstream attributes.
    *   Salary parsing handles invalid or missing values gracefully by catching `ValueError` in `_salary_bound()`.
    *   Invalid rows are logged in telemetry metrics and skipped without failing the pipeline.

---

### Logical Section 5: Relational Persistence & Multi-Backend Loading
*   **Related Files:**
    *   `src/db/load.py`
    *   `src/db/load_postgres.py`
    *   `src/db/schema.sql`
    *   `src/db/schema_postgres.sql`
*   **Detailed Mechanism:**
    1.  **Schema Initialization:**
        When `connect()` is invoked, it reads the corresponding SQL DDL file (`schema.sql` or `schema_postgres.sql`) and executes it using `CREATE TABLE IF NOT EXISTS`, ensuring foreign keys and indexes exist.
    2.  **Relational Normalization:**
        *   `sources`: Upserts the source name and base URL.
        *   `companies`: Deduplicates company names; creates records on demand.
        *   `jobs`: Stores posting attributes with foreign keys referencing `sources(source_id)` and `companies(company_id)`.
        *   `tags`: Stores unique tag strings.
        *   `job_tags`: Many-to-many bridge table joining `jobs(job_id)` and `tags(tag_id)`.
    3.  **Idempotent Upsert Strategy:**
        *   *Sources:* `ON CONFLICT(name) DO UPDATE SET base_url = excluded.base_url`.
        *   *Companies:* `ON CONFLICT(name) DO NOTHING`.
        *   *Jobs:* `ON CONFLICT(source_id, external_id) DO UPDATE SET title = excluded.title, location = excluded.location, ... RETURNING job_id`.
        *   *Tags Reconciliation:* Drops existing links with `DELETE FROM job_tags WHERE job_id = ?`, then inserts new tags into `tags` (`ON CONFLICT DO NOTHING`) and re-links them in `job_tags`.
*   **Key Functions / Methods:**
    *   `connect(target) -> Connection`: Establishes connection, enables foreign keys (`PRAGMA foreign_keys = ON` in SQLite), and applies DDL schema migrations.
    *   `get_or_create_source(conn, name, base_url, access_type) -> int`: Returns primary key `source_id`.
    *   `get_or_create_company(conn, name) -> int | None`: Returns `company_id` or `None` if `name` is empty.
    *   `upsert_job(conn, row, source_id, company_id) -> int`: Inserts or updates job records, returning `job_id`.
    *   `upsert_tags(conn, job_id, tags) -> None`: Reconciles tag associations for `job_id`.
    *   `load_row(conn, row, access_type, base_url) -> int`: Orchestrates normalization sequence across tables, returning the resulting `job_id`.
*   **Data Schemas & Relational Model:**
    ```
    sources (source_id PK, name UNIQUE, base_url, access_type)
       │
       └──< jobs (job_id PK, source_id FK, external_id, company_id FK, title, 
                  location, remote_type, posted_date, retrieved_at, url, 
                  salary_min, salary_max, description_raw)
               │          >── UNIQUE(source_id, external_id)
               │
    companies -┘ (company_id PK, name UNIQUE)
       │
       └──< job_tags (job_id FK, tag_id FK) >── PK(job_id, tag_id)
                 │
    tags --------┘ (tag_id PK, tag_name UNIQUE)
    ```
*   **State Management & Watermarking:**
    *   Deduplication relies on the unique constraint `UNIQUE(source_id, external_id)`.
    *   Re-running ingestion over identical data updates existing rows in place without inflating row counts.
*   **Error Handling & Resilience:**
    *   Parameterized query interfaces (`?` in SQLite, `%s` in psycopg) prevent SQL injection vulnerabilities.
    *   Foreign keys ensure relational integrity across child tables.

---

### Logical Section 6: Pre-flight Auditing & Source Health Checks
*   **Related Files:**
    *   `scripts/check_sources.py`
*   **Detailed Mechanism:**
    1.  **Liveness & Latency:** Measures round-trip HTTP latency for sample fetches across all enabled sources using `time.monotonic()`.
    2.  **Schema Drift Detection:** Evaluates extracted sample records against `required_fields` declared in `config/sources.yaml`. If any required field is missing from the raw record, `fields_ok` evaluates to `False` and missing keys are logged.
    3.  **Robots.txt Politeness Check:** Fetches `<origin>/robots.txt` using the pipeline's identified `User-Agent`. Passes text to `urllib.robotparser.RobotFileParser` to verify scraping authorization. (Includes fallback for 404 responses where `robots.txt` is absent).
    4.  **Fixture Generation:** Saves live raw payloads to `data/raw/<source>/<date>/sample.json` for use as offline test fixtures.
    5.  **Telemetry Reporting:** Writes a structured JSON report to `logs/source_health_<date>.json` and prints a summary diagnostic table to stdout.
*   **Key Functions / Methods:**
    *   `check_robots(url, user_agent, session) -> bool | None`: Inspects `robots.txt` rules using `RobotFileParser`. Returns `True` if fetching is permitted, `False` if blocked, or `None` if unreachable.
    *   `check_source(name, scfg, contact_email, session, run_date) -> dict`: Executes latency measurement, schema field verification, and robots permission checks for a single source.
    *   `main()`: Diagnostic runner orchestrating checks and reporting.

---

## SECTION 4: CONFIGURATION, DEPENDENCIES & RUNBOOK

### 1. Environment Variables & Secrets

Configuration variables must be declared in a `.env` file at repository root or set within the environment:

| Variable Name | Required | Default Value | Purpose |
| :--- | :---: | :--- | :--- |
| `ADZUNA_APP_ID` | Conditional | *None* | App ID for Adzuna Job Search API authentication. |
| `ADZUNA_APP_KEY` | Conditional | *None* | Access Key for Adzuna Job Search API authentication. |
| `USAJOBS_API_KEY` | Conditional | *None* | Host authorization API key for USAJobs REST endpoint. |
| `USAJOBS_EMAIL` | Conditional | *None* | Contact email required in `User-Agent` for USAJobs API requests. |
| `DATABASE_URL_UNPOOLED` | Conditional | *None* | PostgreSQL DSN for Neon cloud database (required when running with `--backend postgres`). |

*Note: Sources requiring keys are skipped with `status: "skipped_no_key"` if the corresponding environment variables are missing.*

---

### 2. External Dependencies

| Dependency | Minimum Version | Category | Purpose in Pipeline |
| :--- | :--- | :--- | :--- |
| `requests` | `>=2.31` | Network / HTTP | HTTP client session management, connection pooling, and endpoint requests. |
| `tenacity` | `>=8.2` | Resilience | Exponential retry, jitter, and status-based backoff logic. |
| `PyYAML` | `>=6.0` | Configuration | Parsing YAML configuration file (`config/sources.yaml`). |
| `feedparser` | `>=6.0` | XML / RSS Parsing | Extracting structured items from We Work Remotely RSS feed. |
| `psycopg[binary]` | `>=3.1` | Database Driver | PostgreSQL client driver for Neon cloud database persistence. |
| `python-dotenv` | `>=1.0` | Configuration | Loading `.env` key-value pairs into `os.environ`. |
| `pytest` | `>=7.4` | Quality Assurance | Test runner for test suites and fixture assertions. |

---

### 3. Execution Instructions & Runbook

#### A. Setup & Installation
```powershell
# 1. Navigate to the project root
Set-Location "c:\Users\kailo\Documents\Data607\Group Project\data_ingestion"

# 2. Install required dependencies
pip install -r requirements.txt

# 3. Create .env file with required credentials
Set-Content .env @"
ADZUNA_APP_ID=your_adzuna_app_id
ADZUNA_APP_KEY=your_adzuna_app_key
USAJOBS_API_KEY=your_usajobs_api_key
USAJOBS_EMAIL=your_email@domain.edu
DATABASE_URL_UNPOOLED=postgresql://user:password@ep-project.us-east-2.aws.neon.tech/neondb?sslmode=require
"@
```

#### B. Pre-flight Health & Diagnostic Auditing
Execute before scheduled runs to evaluate upstream endpoints and detect schema drift:
```powershell
python scripts\check_sources.py
```
*Output: Generates `logs/source_health_<date>.json` and sample payloads in `data/raw/<source>/<date>/sample.json`.*

#### C. Local Ingestion Execution (SQLite)
Run the full ingestion pipeline across all enabled sources into SQLite:
```powershell
python src\pipeline.py
```
*Target Database:* `data/db/jobs.db`

Execute for specific sources only:
```powershell
python src\pipeline.py --sources remoteok,arbeitnow,jobicy
```

#### D. Production Ingestion Execution (PostgreSQL / Neon)
Execute the pipeline targeting the PostgreSQL cloud database:
```powershell
python src\pipeline.py --backend postgres
```
*Or specify a custom connection string:*
```powershell
python src\pipeline.py --backend postgres --db-url "postgresql://user:password@host/dbname?sslmode=require"
```

#### E. Automated Production Execution (PowerShell Runner)
Invoked automatically via Windows Task Scheduler (`Data607-JobPipeline-DailyFetch`) or triggered manually:
```powershell
powershell -ExecutionPolicy Bypass -File "scripts\run_daily.ps1"
```
*Log Output:* Captured at `logs/pipeline_YYYY-MM-DD.log`.

#### F. Running Test Suites
Execute offline unit and integration tests across parsers, rate limiting, retries, and database upserts:
```powershell
pytest -v
```
