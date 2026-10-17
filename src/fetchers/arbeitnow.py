from . import base


def fetch_sample(session, cfg):
    resp = base.get(
        session, cfg["base_url"],
        rate_key="arbeitnow", min_interval_sec=cfg["rate_limit_sec"],
        headers=base.build_headers(cfg["contact_email"]),
    )
    data = resp.json()
    records = data.get("data", [])
    return data, records


# per_page already covers the full current listing in one call (verified 2026-10-12).
fetch_all = fetch_sample
