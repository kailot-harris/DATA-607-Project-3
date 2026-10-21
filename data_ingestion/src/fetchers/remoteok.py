from . import base


def fetch_sample(session, cfg):
    resp = base.get(
        session, cfg["base_url"],
        rate_key="remoteok", min_interval_sec=cfg["rate_limit_sec"],
        headers=base.build_headers(cfg["contact_email"]),
    )
    data = resp.json()
    # first element is a legal/meta notice, not a posting
    records = [r for r in data if isinstance(r, dict) and "id" in r]
    return data, records


# RemoteOK's /api always returns the full current listing in one call.
fetch_all = fetch_sample
