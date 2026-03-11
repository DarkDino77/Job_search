"""
pipeline/cleaner.py
Normalises and deduplicates a list of JobListings.
"""

import re
import unicodedata
from datetime import datetime

from models.job_listing import JobListing


def _clean_text(text: str) -> str:
    """Strip excess whitespace and normalise unicode."""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _normalise_date(date_str: str) -> str:
    """
    Accept various ISO-ish date formats and return a clean YYYY-MM-DD string.
    Returns the original string if parsing fails.
    """
    if not date_str:
        return ""
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str[:19], fmt[:len(fmt)]).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str[:10]   # best-effort: take first 10 chars


def clean_listing(listing: JobListing) -> JobListing:
    """Apply all cleaning steps to a single JobListing in-place."""
    listing.title            = _clean_text(listing.title)
    listing.company          = _clean_text(listing.company)
    listing.location         = _clean_text(listing.location)
    listing.municipality     = _clean_text(listing.municipality)
    listing.description_text = _clean_text(listing.description_text)
    listing.employment_type  = _clean_text(listing.employment_type)
    listing.duration         = _clean_text(listing.duration)
    listing.scope            = _clean_text(listing.scope)
    listing.date_published       = _normalise_date(listing.date_published)
    listing.last_date_application = _normalise_date(listing.last_date_application)
    listing.required_skills  = [_clean_text(s) for s in listing.required_skills if s]
    return listing


def deduplicate(listings: list[JobListing]) -> list[JobListing]:
    """
    Remove duplicate listings.
    Deduplication priority:  ad ID  >  URL  >  (title + company) pair.
    Keeps the first occurrence.
    """
    seen_ids:    set[str] = set()
    seen_urls:   set[str] = set()
    seen_titles: set[str] = set()
    unique: list[JobListing] = []

    for listing in listings:
        # 1. Deduplicate by ID
        if listing.id and listing.id in seen_ids:
            continue
        # 2. Deduplicate by URL
        url_key = listing.url.strip().rstrip("/")
        if url_key and url_key in seen_urls:
            continue
        # 3. Deduplicate by title+company (catches same ad on two platforms)
        title_key = f"{listing.title.lower()}|{listing.company.lower()}"
        if title_key and title_key in seen_titles:
            continue

        if listing.id:
            seen_ids.add(listing.id)
        if url_key:
            seen_urls.add(url_key)
        if title_key:
            seen_titles.add(title_key)

        unique.append(listing)

    return unique


def clean_all(listings: list[JobListing]) -> list[JobListing]:
    """Clean and deduplicate an entire batch of listings."""
    cleaned = [clean_listing(l) for l in listings]
    before = len(cleaned)
    cleaned = deduplicate(cleaned)
    removed = before - len(cleaned)
    if removed:
        print(f"  [cleaner] Removed {removed} duplicates ({len(cleaned)} remaining)")
    return cleaned
