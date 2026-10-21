from . import empty_row


def parse_record(raw: dict, retrieved_at: str) -> dict:
    # WWR titles are "Company Name: Job Title"; fall back to the whole
    # string as title if there's no colon to split on.
    raw_title = raw.get("title", "")
    company, sep, title = raw_title.partition(": ")
    if not sep:
        company, title = None, raw_title

    tags = raw.get("tags") or []
    tags_raw = [t.get("term") for t in tags if isinstance(t, dict) and t.get("term")]

    return empty_row(
        source="wwr",
        external_id=raw.get("id") or raw.get("link"),
        title=title or None,
        company=company or None,
        location=raw.get("region") or None,
        remote_type="remote",
        posted_date=raw.get("published"),
        retrieved_at=retrieved_at,
        url=raw.get("link"),
        salary_min=None,
        salary_max=None,
        description_raw=raw.get("summary"),
        tags_raw=tags_raw or None,
    )
