import datetime

from . import empty_row


def parse_record(raw: dict, retrieved_at: str) -> dict:
    posted = raw.get("created_at")
    if isinstance(posted, (int, float)):
        posted = datetime.datetime.fromtimestamp(posted, tz=datetime.timezone.utc).isoformat()

    return empty_row(
        source="arbeitnow",
        external_id=raw["slug"],
        title=raw.get("title"),
        company=raw.get("company_name"),
        location=raw.get("location") or None,
        remote_type="remote" if raw.get("remote") else "unspecified",
        posted_date=posted,
        retrieved_at=retrieved_at,
        url=raw.get("url"),
        salary_min=None,
        salary_max=None,
        description_raw=raw.get("description"),
        tags_raw=raw.get("tags"),
    )
