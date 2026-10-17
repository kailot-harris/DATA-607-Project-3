from . import empty_row


def parse_record(raw: dict, retrieved_at: str) -> dict:
    return empty_row(
        source="jobicy",
        external_id=str(raw["id"]),
        title=raw.get("jobTitle"),
        company=raw.get("companyName"),
        location=raw.get("jobGeo") or None,
        remote_type="remote",
        posted_date=raw.get("pubDate"),
        retrieved_at=retrieved_at,
        url=raw.get("url"),
        salary_min=raw.get("salaryMin") or None,
        salary_max=raw.get("salaryMax") or None,
        description_raw=raw.get("jobDescription") or raw.get("jobExcerpt"),
        tags_raw=raw.get("jobIndustry"),
    )
