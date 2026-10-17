from . import base


def _fetch(session, cfg, count):
    resp = base.get(
        session, cfg["base_url"],
        rate_key="jobicy", min_interval_sec=cfg["rate_limit_sec"],
        headers=base.build_headers(cfg["contact_email"]),
        params={"count": count},
    )
    data = resp.json()
    records = data.get("jobs", [])
    return data, records


def fetch_sample(session, cfg):
    return _fetch(session, cfg, count=5)


def fetch_all(session, cfg):
    return _fetch(session, cfg, count=50)  # API max per request
