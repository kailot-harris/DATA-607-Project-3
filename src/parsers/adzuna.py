from . import empty_row


def parse_record(raw: dict, retrieved_at: str) -> dict:
    location = raw.get("location") or {}
    company = raw.get("company") or {}
    category = raw.get("category") or {}

    return empty_row(
        source="adzuna",
        external_id=str(raw["id"]),
        title=raw.get("title"),
        company=company.get("display_name"),
        location=location.get("display_name"),
        remote_type="unspecified",
        posted_date=raw.get("created"),
        retrieved_at=retrieved_at,
        url=raw.get("redirect_url"),
        salary_min=raw.get("salary_min"),
        salary_max=raw.get("salary_max"),
        description_raw=raw.get("description"),
        tags_raw=[category["tag"]] if category.get("tag") else None,
    )
