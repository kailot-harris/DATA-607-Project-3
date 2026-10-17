import os

from . import base


def has_credentials(cfg):
    return all(os.environ.get(var) for var in cfg["credential_env"])


def fetch_sample(session, cfg):
    app_id = os.environ["ADZUNA_APP_ID"]
    app_key = os.environ["ADZUNA_APP_KEY"]
    resp = base.get(
        session, cfg["base_url"],
        rate_key="adzuna", min_interval_sec=cfg["rate_limit_sec"],
        headers=base.build_headers(cfg["contact_email"]),
        params={"app_id": app_id, "app_key": app_key, "what": "data science", "results_per_page": 50},
    )
    data = resp.json()
    records = data.get("results", [])
    return data, records


fetch_all = fetch_sample
