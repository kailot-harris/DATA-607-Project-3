from src.db import load


def _sample_row(**overrides):
    row = dict(
        source="remoteok", external_id="123", title="Data Scientist",
        company="Acme", location="Remote", remote_type="remote",
        posted_date="2026-10-01", retrieved_at="2026-10-12T00:00:00+00:00",
        url="https://remoteok.com/remote-jobs/123", salary_min=90000, salary_max=120000,
        description_raw="desc", tags_raw=["python", "sql"],
    )
    row.update(overrides)
    return row


def test_load_row_creates_source_company_job_and_tags(tmp_path):
    conn = load.connect(str(tmp_path / "test.db"))
    row = _sample_row()

    job_id = load.load_row(conn, row, access_type="api_json", base_url="https://remoteok.com/api")

    job = conn.execute("SELECT title, company_id FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    assert job[0] == "Data Scientist"

    tags = conn.execute(
        "SELECT tag_name FROM tags JOIN job_tags USING (tag_id) WHERE job_id = ?", (job_id,)
    ).fetchall()
    assert {t[0] for t in tags} == {"python", "sql"}


def test_rerun_on_same_external_id_does_not_duplicate(tmp_path):
    conn = load.connect(str(tmp_path / "test.db"))
    row = _sample_row()

    id1 = load.load_row(conn, row, access_type="api_json", base_url="https://remoteok.com/api")
    id2 = load.load_row(conn, row, access_type="api_json", base_url="https://remoteok.com/api")

    assert id1 == id2
    count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    assert count == 1


def test_rerun_with_updated_tags_replaces_old_tags(tmp_path):
    conn = load.connect(str(tmp_path / "test.db"))
    row = _sample_row()
    job_id = load.load_row(conn, row, access_type="api_json", base_url="https://remoteok.com/api")

    row2 = _sample_row(tags_raw=["rust"])
    load.load_row(conn, row2, access_type="api_json", base_url="https://remoteok.com/api")

    tags = conn.execute(
        "SELECT tag_name FROM tags JOIN job_tags USING (tag_id) WHERE job_id = ?", (job_id,)
    ).fetchall()
    assert {t[0] for t in tags} == {"rust"}
