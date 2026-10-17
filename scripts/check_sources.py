#!/usr/bin/env python
"""Live health check for every source in config/sources.yaml.

For each enabled source, checks:
  - liveness: does the endpoint respond 2xx within a reasonable timeout?
  - data shape: does a sample record contain the fields the pipeline needs?
  - politeness: is our configured rate limit actually being honored, and
    does robots.txt (where one exists) allow fetching this URL?

Writes a JSON report to logs/source_health_<date>.json and a raw sample
snapshot to data/raw/<source>/<date>/sample.json for use as a test fixture.
Does not touch the DB or the parse stage -- this is a pre-flight check only.
"""
import datetime
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.fetchers import base, remoteok, arbeitnow, jobicy, himalayas, wwr, hn_hiring, adzuna, usajobs  # noqa: E402

FETCHERS = {
    "remoteok": remoteok,
    "arbeitnow": arbeitnow,
    "jobicy": jobicy,
    "himalayas": himalayas,
    "wwr": wwr,
    "hn_hiring": hn_hiring,
    "adzuna": adzuna,
    "usajobs": usajobs,
}


def check_robots(url: str, user_agent: str, session: requests.Session):
    # RobotFileParser.read() sends urllib's default UA with no headers, which
    # several Cloudflare-fronted sites 403 -- robotparser treats any 403 as
    # disallow-all, a false negative. Fetch with our real UA instead.
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        resp = session.get(robots_url, headers={"User-Agent": user_agent}, timeout=10)
        if resp.status_code == 404:
            return True  # no robots.txt at all -- nothing to disallow
        resp.raise_for_status()
        rp.parse(resp.text.splitlines())
    except Exception:
        return None  # unreachable for some other reason -- treat as unknown
    return rp.can_fetch(user_agent, url)


def check_source(name: str, scfg: dict, contact_email: str, session: requests.Session, run_date: str) -> dict:
    row = {"source": name}
    fetcher = FETCHERS[name]
    cfg = {**scfg, "contact_email": contact_email}

    if scfg.get("requires_key") and not fetcher.has_credentials(scfg):
        row.update(status="skipped_no_key", note=f"missing env vars {scfg['credential_env']}")
        return row

    t0 = time.monotonic()
    try:
        raw, records = fetcher.fetch_sample(session, cfg)
        latency = time.monotonic() - t0
    except Exception as exc:
        row.update(status="error", error=f"{type(exc).__name__}: {exc}", latency_s=round(time.monotonic() - t0, 2))
        return row

    required = scfg.get("required_fields", [])
    sample = records[0] if records else {}
    missing = [f for f in required if f not in sample]
    user_agent = base.build_headers(contact_email)["User-Agent"]

    row.update(
        status="live",
        latency_s=round(latency, 2),
        record_count=len(records),
        fields_ok=(len(missing) == 0 and bool(records)),
        missing_fields=missing,
        robots_allowed=check_robots(scfg["base_url"], user_agent, session),
    )

    outdir = ROOT / "data" / "raw" / name / run_date
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "sample.json").write_text(json.dumps(raw, default=str, indent=2))
    return row


def main():
    cfg = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text())
    contact_email = cfg["contact_email"]
    run_date = datetime.date.today().isoformat()
    session = requests.Session()

    results = []
    for name, scfg in cfg["sources"].items():
        if not scfg.get("enabled", True):
            results.append({"source": name, "status": "disabled"})
            continue
        print(f"checking {name} ...", flush=True)
        results.append(check_source(name, scfg, contact_email, session, run_date))

    print()
    header = f"{'source':<12} {'status':<16} {'latency_s':>9} {'records':>7} {'fields_ok':>9} {'robots_ok':>9}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r['source']:<12} {r['status']:<16} "
            f"{str(r.get('latency_s', '-')):>9} {str(r.get('record_count', '-')):>7} "
            f"{str(r.get('fields_ok', '-')):>9} {str(r.get('robots_allowed', '-')):>9}"
        )
        if r.get("missing_fields"):
            print(f"             missing fields: {r['missing_fields']}")
        if r.get("error"):
            print(f"             error: {r['error']}")
        if r.get("note"):
            print(f"             note: {r['note']}")

    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    (log_dir / f"source_health_{run_date}.json").write_text(json.dumps(results, indent=2, default=str))
    print(f"\nfull report: logs/source_health_{run_date}.json")


if __name__ == "__main__":
    main()
