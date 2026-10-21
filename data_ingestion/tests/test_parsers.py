import datetime
import json
from pathlib import Path

import pytest

from src.parsers import remoteok, arbeitnow, jobicy, himalayas, wwr, hn_hiring, validate_row

FIXTURES = Path(__file__).parent / "fixtures"
RETRIEVED_AT = datetime.datetime.now(datetime.timezone.utc).isoformat()


def _load(name):
    return json.loads((FIXTURES / name).read_text())


@pytest.mark.parametrize("parser,fixture_file,records_key", [
    (remoteok, "remoteok_sample.json", None),       # raw itself is the list
    (arbeitnow, "arbeitnow_sample.json", "data"),
    (jobicy, "jobicy_sample.json", "jobs"),
    (himalayas, "himalayas_sample.json", "jobs"),
    (wwr, "wwr_sample.json", "entries"),
    (hn_hiring, "hn_hiring_sample.json", "hits"),
])
def test_parser_produces_valid_rows_from_real_fixture(parser, fixture_file, records_key):
    raw = _load(fixture_file)
    records = raw if records_key is None else raw[records_key]
    if records_key is None:
        records = [r for r in records if isinstance(r, dict) and "id" in r]

    assert records, f"fixture {fixture_file} has no sample records"

    for record in records:
        row = parser.parse_record(record, RETRIEVED_AT)
        errors = validate_row(row)
        assert errors == [], f"{fixture_file}: {errors} for row {row}"


def test_wwr_splits_company_from_title():
    raw = _load("wwr_sample.json")
    record = raw["entries"][0]
    row = wwr.parse_record(record, RETRIEVED_AT)
    assert row["company"]
    assert row["title"]
    assert ":" not in row["title"] or row["title"] != record["title"]


def test_hn_hiring_has_no_inferred_structured_fields():
    raw = _load("hn_hiring_sample.json")
    record = raw["hits"][0]
    row = hn_hiring.parse_record(record, RETRIEVED_AT)
    assert row["title"] is None
    assert row["company"] is None
    assert row["description_raw"] == record.get("comment_text")
