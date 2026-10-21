from . import empty_row


def parse_record(raw: dict, retrieved_at: str) -> dict:
    location = raw.get("locationRestrictions")
    if isinstance(location, list):
        location = ", ".join(location) or None

    return empty_row(
        source="himalayas",
        external_id=raw["guid"],
        title=raw.get("title"),
        company=raw.get("companyName"),
        location=location,
        remote_type="remote",
        posted_date=raw.get("pubDate"),
        retrieved_at=retrieved_at,
        url=raw.get("applicationLink"),
        salary_min=raw.get("minSalary") or None,
        salary_max=raw.get("maxSalary") or None,
        description_raw=raw.get("description") or raw.get("excerpt"),
        tags_raw=raw.get("categories"),
    )
