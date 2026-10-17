from . import base

RATE_KEY = "hn_hiring"


def _find_latest_thread(session, cfg):
    resp = base.get(
        session, cfg["base_url"],
        rate_key=RATE_KEY, min_interval_sec=cfg["rate_limit_sec"],
        headers=base.build_headers(cfg["contact_email"]),
        params={"tags": "story", "query": "Who is hiring"},
    )
    hits = resp.json().get("hits", [])
    for hit in hits:
        if hit.get("title", "").lower().startswith("ask hn: who is hiring"):
            return hit
    return None


def _fetch_comments(session, cfg, thread, hits_per_page):
    resp = base.get(
        session, cfg["base_url"],
        rate_key=RATE_KEY, min_interval_sec=cfg["rate_limit_sec"],
        headers=base.build_headers(cfg["contact_email"]),
        params={"tags": f"comment,story_{thread['objectID']}", "hitsPerPage": hits_per_page},
    )
    data = resp.json()
    return data, data.get("hits", [])


def fetch_sample(session, cfg):
    thread = _find_latest_thread(session, cfg)
    if thread is None:
        return {"hits": []}, []
    return _fetch_comments(session, cfg, thread, hits_per_page=20)


def fetch_all(session, cfg):
    thread = _find_latest_thread(session, cfg)
    if thread is None:
        return {"hits": []}, []
    return _fetch_comments(session, cfg, thread, hits_per_page=1000)  # Algolia's per-page max
