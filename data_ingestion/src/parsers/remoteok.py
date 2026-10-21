from . import empty_row


def parse_record(raw: dict, retrieved_at: str) -> dict:
    return empty_row(
        source="remoteok",
        external_id=str(raw["id"]),
        title=raw.get("position"),
        company=raw.get("company"),
        location=raw.get("location") or None,
        remote_type="remote",
        posted_date=raw.get("date"),
        retrieved_at=retrieved_at,
        url=raw.get("url") or raw.get("apply_url"),
        salary_min=raw.get("salary_min") or None,
        salary_max=raw.get("salary_max") or None,
        description_raw=raw.get("description"),
        tags_raw=raw.get("tags"),
    )
