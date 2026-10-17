from . import empty_row


def _salary_bound(remuneration: list, key: str):
    if not remuneration:
        return None
    value = remuneration[0].get(key)
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def parse_record(raw: dict, retrieved_at: str) -> dict:
    remuneration = raw.get("PositionRemuneration") or []
    categories = raw.get("JobCategory") or []

    return empty_row(
        source="usajobs",
        external_id=raw["PositionID"],
        title=raw.get("PositionTitle"),
        company=raw.get("OrganizationName"),
        location=raw.get("PositionLocationDisplay"),
        remote_type="unspecified",
        posted_date=raw.get("PublicationStartDate"),
        retrieved_at=retrieved_at,
        url=raw.get("PositionURI"),
        salary_min=_salary_bound(remuneration, "MinimumRange"),
        salary_max=_salary_bound(remuneration, "MaximumRange"),
        description_raw=raw.get("QualificationSummary"),
        tags_raw=[c["Name"] for c in categories if c.get("Name")] or None,
    )
