import feedparser

from . import base


def fetch_sample(session, cfg):
    resp = base.get(
        session, cfg["base_url"],
        rate_key="wwr", min_interval_sec=cfg["rate_limit_sec"],
        headers=base.build_headers(cfg["contact_email"]),
    )
    feed = feedparser.parse(resp.content)
    records = [dict(entry) for entry in feed.entries]
    raw = {"feed": dict(feed.feed), "entries": records}
    return raw, records


# RSS feed has no pagination -- one fetch always returns everything it has.
fetch_all = fetch_sample
