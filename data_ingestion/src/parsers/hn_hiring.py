from . import empty_row


def parse_record(raw: dict, retrieved_at: str) -> dict:
    # HN "Who's hiring" comments are free-text, not structured postings --
    # store verbatim, don't infer title/company/location (PLAN.md s1).
    object_id = raw["objectID"]
    return empty_row(
        source="hn_hiring",
        external_id=object_id,
        title=None,
        company=None,
        location=None,
        remote_type=None,
        posted_date=raw.get("created_at"),
        retrieved_at=retrieved_at,
        url=f"https://news.ycombinator.com/item?id={object_id}",
        salary_min=None,
        salary_max=None,
        description_raw=raw.get("comment_text"),
        tags_raw=None,
    )
