CREATE TABLE IF NOT EXISTS sources (
    source_id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    base_url TEXT,
    access_type TEXT
);

CREATE TABLE IF NOT EXISTS companies (
    company_id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(source_id),
    external_id TEXT NOT NULL,
    company_id INTEGER REFERENCES companies(company_id),
    title TEXT,
    location TEXT,
    remote_type TEXT,
    posted_date TEXT,
    retrieved_at TEXT NOT NULL,
    url TEXT,
    salary_min INTEGER,
    salary_max INTEGER,
    description_raw TEXT,
    UNIQUE(source_id, external_id)
);

CREATE TABLE IF NOT EXISTS tags (
    tag_id SERIAL PRIMARY KEY,
    tag_name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS job_tags (
    job_id INTEGER NOT NULL REFERENCES jobs(job_id),
    tag_id INTEGER NOT NULL REFERENCES tags(tag_id),
    PRIMARY KEY (job_id, tag_id)
);
