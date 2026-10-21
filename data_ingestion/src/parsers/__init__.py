"""Raw record -> common row schema. Field renaming/type coercion only --
no keyword matching, tagging, or other interpretation (see PLAN.md s2-3)."""
from urllib.parse import urlparse

ROW_FIELDS = (
    "source", "external_id", "title", "company", "location", "remote_type",
    "posted_date", "retrieved_at", "url", "salary_min", "salary_max",
    "description_raw", "tags_raw",
)


def empty_row(**overrides) -> dict:
    row = dict.fromkeys(ROW_FIELDS, None)
    row.update(overrides)
    return row


def validate_row(row: dict) -> list[str]:
    """Minimal pre-load schema check: required fields non-null, URL well-formed."""
    errors = []
    for field in ("source", "external_id", "retrieved_at"):
        if not row.get(field):
            errors.append(f"missing required field: {field}")
    url = row.get("url")
    if url:
        parsed = urlparse(url)
        if not (parsed.scheme and parsed.netloc):
            errors.append(f"malformed url: {url!r}")
    return errors
