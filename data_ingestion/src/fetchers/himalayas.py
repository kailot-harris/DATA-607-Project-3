from . import base


def _fetch(session, cfg, limit):
    resp = base.get(
        session, cfg["base_url"],
        rate_key="himalayas", min_interval_sec=cfg["rate_limit_sec"],
        headers=base.build_headers(cfg["contact_email"]),
        params={"limit": limit},
    )
    data = resp.json()
    records = data.get("jobs", [])
    return data, records


def fetch_sample(session, cfg):
    return _fetch(session, cfg, limit=5)


def fetch_all(session, cfg):
    return _fetch(session, cfg, limit=100)
