import os

from . import base


def has_credentials(cfg):
    return all(os.environ.get(var) for var in cfg["credential_env"])


def fetch_sample(session, cfg):
    api_key = os.environ["USAJOBS_API_KEY"]
    email = os.environ["USAJOBS_EMAIL"]
    headers = base.build_headers(cfg["contact_email"])
    headers.update({
        "Host": "data.usajobs.gov",
        "User-Agent": email,
        "Authorization-Key": api_key,
    })
    resp = base.get(
        session, cfg["base_url"],
        rate_key="usajobs", min_interval_sec=cfg["rate_limit_sec"],
        headers=headers,
        params={"Keyword": "data scientist", "ResultsPerPage": 250},
    )
    data = resp.json()
    records = data.get("SearchResult", {}).get("SearchResultItems", [])
    # USAJobs nests the actual fields one level deeper, under MatchedObjectDescriptor
    flat = [r.get("MatchedObjectDescriptor", {}) for r in records]
    return data, flat


fetch_all = fetch_sample
