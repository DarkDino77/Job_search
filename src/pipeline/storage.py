"""
pipeline/storage.py
Persists JobListings to a local SQLite database and exports batches to JSON.
"""

import csv
import json
import os
import sqlite3
from datetime import datetime, timezone

from models.job_listing import JobListing
from config import EXPORT_MIN_SCORE
from constants import (
    DB_PATH, EXPORT_MAX_LISTINGS,
    EXPORT_PATH, EXPORT_ALL_PATH,
    EXPORT_CSV_PATH, EXPORT_ALL_CSV_PATH,
)


def _ensure_output_dir(path: str) -> None:
    """Create the output directory for a given file path if it doesn't exist."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)


# ── Schema ────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id                    TEXT PRIMARY KEY,
    title                 TEXT,
    company               TEXT,
    location              TEXT,
    municipality          TEXT,
    date_published        TEXT,
    last_date_application TEXT,
    description_text      TEXT,
    description_html      TEXT,
    required_skills       TEXT,   -- JSON array stored as string
    employment_type       TEXT,
    duration              TEXT,
    scope                 TEXT,
    url                   TEXT,
    source_api            TEXT,
    relevance_score       REAL DEFAULT 0.0,
    fetched_at            TEXT
);

CREATE INDEX IF NOT EXISTS idx_score      ON jobs(relevance_score DESC);
CREATE INDEX IF NOT EXISTS idx_date       ON jobs(date_published DESC);
CREATE INDEX IF NOT EXISTS idx_source     ON jobs(source_api);

-- Full-text search virtual table (SQLite FTS5)
CREATE VIRTUAL TABLE IF NOT EXISTS jobs_fts USING fts5(
    id UNINDEXED,
    title,
    company,
    description_text,
    required_skills,
    content='jobs',
    content_rowid='rowid'
);

-- Keep FTS index in sync
CREATE TRIGGER IF NOT EXISTS jobs_ai AFTER INSERT ON jobs BEGIN
    INSERT INTO jobs_fts(rowid, id, title, company, description_text, required_skills)
    VALUES (new.rowid, new.id, new.title, new.company, new.description_text, new.required_skills);
END;

CREATE TRIGGER IF NOT EXISTS jobs_ad AFTER DELETE ON jobs BEGIN
    INSERT INTO jobs_fts(jobs_fts, rowid, id, title, company, description_text, required_skills)
    VALUES ('delete', old.rowid, old.id, old.title, old.company, old.description_text, old.required_skills);
END;

CREATE TRIGGER IF NOT EXISTS jobs_au AFTER UPDATE ON jobs BEGIN
    INSERT INTO jobs_fts(jobs_fts, rowid, id, title, company, description_text, required_skills)
    VALUES ('delete', old.rowid, old.id, old.title, old.company, old.description_text, old.required_skills);
    INSERT INTO jobs_fts(rowid, id, title, company, description_text, required_skills)
    VALUES (new.rowid, new.id, new.title, new.company, new.description_text, new.required_skills);
END;
"""


# ── Connection helper ─────────────────────────────────────────────────────────

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    _ensure_output_dir(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """Create tables and indexes if they don't exist."""
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


# ── Write ─────────────────────────────────────────────────────────────────────

def _listing_to_row(listing: JobListing) -> dict:
    return {
        "id":                    listing.id,
        "title":                 listing.title,
        "company":               listing.company,
        "location":              listing.location,
        "municipality":          listing.municipality,
        "date_published":        listing.date_published,
        "last_date_application": listing.last_date_application,
        "description_text":      listing.description_text,
        "description_html":      listing.description_html,
        "required_skills":       json.dumps(listing.required_skills, ensure_ascii=False),
        "employment_type":       listing.employment_type,
        "duration":              listing.duration,
        "scope":                 listing.scope,
        "url":                   listing.url,
        "source_api":            listing.source_api,
        "relevance_score":       listing.relevance_score,
        "fetched_at":            datetime.now(timezone.utc).isoformat(),
    }


def save_listings(listings: list[JobListing], db_path: str = DB_PATH) -> int:
    """
    Upsert listings into the database.
    Returns the number of new rows inserted (not counting updates).
    """
    init_db(db_path)
    conn = get_connection(db_path)
    inserted = 0
    try:
        for listing in listings:
            row = _listing_to_row(listing)
            cursor = conn.execute(
                """
                INSERT INTO jobs (
                    id, title, company, location, municipality,
                    date_published, last_date_application,
                    description_text, description_html, required_skills,
                    employment_type, duration, scope,
                    url, source_api, relevance_score, fetched_at
                ) VALUES (
                    :id, :title, :company, :location, :municipality,
                    :date_published, :last_date_application,
                    :description_text, :description_html, :required_skills,
                    :employment_type, :duration, :scope,
                    :url, :source_api, :relevance_score, :fetched_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    relevance_score       = excluded.relevance_score,
                    last_date_application = excluded.last_date_application,
                    fetched_at            = excluded.fetched_at
                """,
                row,
            )
            if cursor.lastrowid and cursor.rowcount == 1:
                inserted += 1
        conn.commit()
    finally:
        conn.close()
    return inserted


# ── Read ──────────────────────────────────────────────────────────────────────

def query_top(
    min_score: float = 0.0,
    limit: int = 20,
    db_path: str = DB_PATH,
) -> list[dict]:
    """Return top listings sorted by relevance score."""
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT id, title, company, location, date_published,
                   last_date_application, url, relevance_score, source_api
            FROM jobs
            WHERE relevance_score >= ?
            ORDER BY relevance_score DESC
            LIMIT ?
            """,
            (min_score, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def full_text_search(query: str, limit: int = 20, db_path: str = DB_PATH) -> list[dict]:
    """
    Full-text search across title, company, description, and skills.
    Uses SQLite FTS5 — no extra dependencies needed.
    """
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT j.id, j.title, j.company, j.location,
                   j.date_published, j.url, j.relevance_score
            FROM jobs j
            JOIN jobs_fts ON j.id = jobs_fts.id
            WHERE jobs_fts MATCH ?
            ORDER BY j.relevance_score DESC
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_stats(db_path: str = DB_PATH) -> dict:
    """Return basic stats about the database."""
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        total   = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        sources = conn.execute(
            "SELECT source_api, COUNT(*) as n FROM jobs GROUP BY source_api"
        ).fetchall()
        avg_score = conn.execute(
            "SELECT AVG(relevance_score) FROM jobs WHERE relevance_score > 0"
        ).fetchone()[0]
        return {
            "total": total,
            "by_source": {r["source_api"]: r["n"] for r in sources},
            "avg_score": round(avg_score or 0, 3),
        }
    finally:
        conn.close()


# ── Export for AI evaluation ──────────────────────────────────────────────────

def export_top_listings(
    min_score: float = EXPORT_MIN_SCORE,
    limit: int = EXPORT_MAX_LISTINGS,
    output_path: str = EXPORT_PATH,
    db_path: str = DB_PATH,
) -> int:
    """
    Export top-scored listings to a JSON file for AI evaluation.
    Attach this file alongside prompttemplate.md and your CV.
    """
    _ensure_output_dir(output_path)
    listings = query_top(min_score=min_score, limit=limit, db_path=db_path)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(listings, f, ensure_ascii=False, indent=2)
    print(f"  [export] {len(listings)} listings → {output_path}")
    return len(listings)


def export_all_listings(
    output_path: str = EXPORT_ALL_PATH,
    db_path: str = DB_PATH,
) -> int:
    """
    Export every job currently in the database to a JSON file, sorted by
    relevance score descending. No score threshold — includes everything.
    """
    _ensure_output_dir(output_path)
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT id, title, company, location, municipality,
                   date_published, last_date_application,
                   description_text, employment_type, duration, scope,
                   url, source_api, relevance_score, fetched_at
            FROM jobs
            ORDER BY relevance_score DESC
            """
        ).fetchall()
        listings = [dict(r) for r in rows]
    finally:
        conn.close()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(listings, f, ensure_ascii=False, indent=2)
    print(f"  [export-all] {len(listings)} listings → {output_path}")
    return len(listings)


# ── CSV exports ───────────────────────────────────────────────────────────────

def _write_csv(listings: list[dict], output_path: str) -> int:
    """
    Write a list of job dicts to a CSV file.
    Uses utf-8-sig encoding so Excel on Windows opens Swedish characters correctly.
    """
    _ensure_output_dir(output_path)
    if not listings:
        print(f"  [csv] Nothing to write → {output_path}")
        return 0
    headers = listings[0].keys()
    with open(output_path, "w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(listings)
    print(f"  [csv] {len(listings)} listings → {output_path}")
    return len(listings)


def export_top_csv(
    min_score: float = EXPORT_MIN_SCORE,
    limit: int = EXPORT_MAX_LISTINGS,
    output_path: str = EXPORT_CSV_PATH,
    db_path: str = DB_PATH,
) -> int:
    """Export top-scored listings to a CSV file."""
    listings = query_top(min_score=min_score, limit=limit, db_path=db_path)
    return _write_csv(listings, output_path)


def export_all_csv(
    output_path: str = EXPORT_ALL_CSV_PATH,
    db_path: str = DB_PATH,
) -> int:
    """Export every job in the database to a CSV file."""
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT id, title, company, location, municipality,
                   date_published, last_date_application,
                   description_text, employment_type, duration, scope,
                   url, source_api, relevance_score, fetched_at
            FROM jobs
            ORDER BY relevance_score DESC
            """
        ).fetchall()
        listings = [dict(r) for r in rows]
    finally:
        conn.close()
    return _write_csv(listings, output_path)


# ── Location-filtered exports ─────────────────────────────────────────────────

def _apply_location_filter(
    listings: list[dict],
    terms: list[str],
    exclude: bool = False,
) -> list[dict]:
    """
    Filter listings by location terms.

    Each term is matched (case-insensitive) against both the `location`
    (city) and `municipality` columns — a listing matches if EITHER field
    contains the term as a substring.  Multiple terms are OR-ed together,
    so a listing only needs to match one term to be included/excluded.

    Args:
        listings: raw dicts from the database.
        terms:    list of location strings, e.g. ["linköping", "norrköping"].
        exclude:  False → keep only matching listings (include mode).
                  True  → remove matching listings (exclude mode, -E flag).
    """
    if not terms:
        return listings

    # Each term may contain multiple words (e.g. "Solna Stockholm").
    # Split every term into individual words so each word is checked
    # independently against both city and municipality.
    # A listing matches if ANY word from ANY term hits either field.
    words = [word.lower().strip() for term in terms for word in term.split()]

    def matches(row: dict) -> bool:
        city = (row.get("location") or "").lower()
        muni = (row.get("municipality") or "").lower()
        return any(word in city or word in muni for word in words)

    if exclude:
        return [r for r in listings if not matches(r)]
    else:
        return [r for r in listings if matches(r)]


def _fetch_all_rows(db_path: str = DB_PATH) -> list[dict]:
    """Return every job from the database sorted by relevance score desc."""
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT id, title, company, location, municipality,
                   date_published, last_date_application,
                   description_text, employment_type, duration, scope,
                   url, source_api, relevance_score, fetched_at
            FROM jobs
            ORDER BY relevance_score DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def export_location_csv(
    terms: list[str],
    exclude: bool = False,
    output_path: str = "output/job_listings_location.csv",
    db_path: str = DB_PATH,
) -> int:
    """
    Export jobs filtered by location to a CSV file.

    Args:
        terms:   location strings matched against city and municipality.
        exclude: if True, matching jobs are removed instead of kept.
    """
    listings = _apply_location_filter(_fetch_all_rows(db_path), terms, exclude)
    mode = "excluded" if exclude else "matching"
    print(f"  [location-csv] {len(listings)} listings ({mode} {terms})")
    return _write_csv(listings, output_path)


def export_location_json(
    terms: list[str],
    exclude: bool = False,
    output_path: str = "output/job_listings_location.json",
    db_path: str = DB_PATH,
) -> int:
    """
    Export jobs filtered by location to a JSON file.

    Args:
        terms:   location strings matched against city and municipality.
        exclude: if True, matching jobs are removed instead of kept.
    """
    listings = _apply_location_filter(_fetch_all_rows(db_path), terms, exclude)
    _ensure_output_dir(output_path)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(listings, f, ensure_ascii=False, indent=2)
    mode = "excluded" if exclude else "matching"
    print(f"  [location-json] {len(listings)} listings ({mode} {terms}) → {output_path}")
    return len(listings)
