"""
parsers/ad_parser.py
Maps raw JSON responses from JobSearch and JobAd Links into JobListing dataclasses.
Also handles HTML stripping from description fields.
"""

import re
import unicodedata
from bs4 import BeautifulSoup

from models.job_listing import JobListing


# ── HTML stripping ────────────────────────────────────────────────────────────

def strip_html(html: str) -> str:
    """Convert HTML description to clean plain text."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    # Replace <br> and <p> with newlines before extracting text
    for tag in soup.find_all(["br", "p", "li"]):
        tag.insert_before("\n")
    text = soup.get_text(separator=" ")
    # Collapse multiple whitespace/newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def normalise_unicode(text: str) -> str:
    """Normalise unicode — keeps Swedish å ä ö intact. Safely handles None."""
    if not text:
        return ""
    return unicodedata.normalize("NFC", str(text))


# ── JobSearch parser ──────────────────────────────────────────────────────────

def parse_jobsearch_ad(raw: dict) -> JobListing:
    """
    Parse a single hit from the JobSearch API into a JobListing.
    """
    desc_html = raw.get("description", {}).get("text", "") or ""
    desc_text = normalise_unicode(strip_html(desc_html))

    workplace = raw.get("workplace_address", {}) or {}
    employer = raw.get("employer", {}) or {}

    # Skills from 'must_have' and 'nice_to_have' fields if present
    skills: list[str] = []
    for skill_group in ["must_have", "nice_to_have"]:
        group = raw.get(skill_group, {}) or {}
        for skill in group.get("skills", []):
            label = skill.get("label") or skill.get("concept_label", "")
            if label:
                skills.append(label)

    employment_type = ""
    if raw.get("employment_type"):
        employment_type = raw["employment_type"].get("label", "")

    duration = ""
    if raw.get("duration"):
        duration = raw["duration"].get("label", "")

    scope = ""
    if raw.get("working_hours_type"):
        scope = raw["working_hours_type"].get("label", "")

    webpage_url = raw.get("webpage_url", "") or ""

    return JobListing(
        id=str(raw.get("id", "")),
        title=normalise_unicode(raw.get("headline", "") or ""),
        company=normalise_unicode(employer.get("name", "") or ""),
        location=normalise_unicode(workplace.get("city", "") or ""),
        municipality=normalise_unicode(workplace.get("municipality", "") or ""),
        date_published=raw.get("publication_date", "") or "",
        last_date_application=raw.get("last_application_date", "") or "",
        description_text=desc_text,
        description_html=desc_html,
        required_skills=skills,
        employment_type=normalise_unicode(employment_type),
        duration=normalise_unicode(duration),
        scope=normalise_unicode(scope),
        url=webpage_url,
        source_api="jobsearch",
    )


# ── JobAd Links parser ────────────────────────────────────────────────────────

def parse_jobadlinks_ad(raw: dict) -> JobListing:
    """
    Parse a single hit from the JobAd Links API into a JobListing.
    JobAd Links returns leaner data — description may be absent.
    """
    desc_html = raw.get("description", "") or ""
    desc_text = normalise_unicode(strip_html(desc_html)) if desc_html else ""

    employer_name = (
        raw.get("employer", {}).get("name", "")
        or raw.get("employer_name", "")
        or ""
    )

    url = (
        raw.get("webpage_url")
        or raw.get("url")
        or raw.get("application_url")
        or ""
    )

    skills: list[str] = []
    for skill in raw.get("skills", []):
        label = skill.get("label") or skill.get("concept_label", "")
        if label:
            skills.append(label)

    return JobListing(
        id=str(raw.get("id", url)),   # use URL as fallback ID
        title=normalise_unicode(raw.get("headline", raw.get("title", "")) or ""),
        company=normalise_unicode(employer_name),
        location=normalise_unicode(
            raw.get("workplace_address", {}).get("city", "") or ""
        ),
        municipality=normalise_unicode(
            raw.get("workplace_address", {}).get("municipality", "") or ""
        ),
        date_published=raw.get("publication_date", raw.get("published_date", "")) or "",
        last_date_application=raw.get("last_application_date", "") or "",
        description_text=desc_text,
        description_html=desc_html,
        required_skills=skills,
        employment_type="",
        duration="",
        scope="",
        url=str(url),
        source_api="jobadlinks",
    )


# ── Dispatcher ────────────────────────────────────────────────────────────────

def parse_ad(raw: dict) -> JobListing | None:
    """
    Automatically choose the right parser based on the _source_api tag
    set by the fetcher, or default to JobSearch format.
    """
    try:
        source = raw.get("_source_api", "jobsearch")
        if source == "jobadlinks":
            return parse_jobadlinks_ad(raw)
        return parse_jobsearch_ad(raw)
    except Exception as e:
        ad_id = raw.get("id", "unknown")
        print(f"  [parser] Warning: failed to parse ad {ad_id}: {e}")
        return None


def parse_ads(raw_list: list[dict]) -> list[JobListing]:
    """
    Deduplicate raw hits by ID, then parse each one.
    Deduplicating here means a broken ad only produces one warning even if
    it appeared in results for multiple search queries.
    """
    seen_ids: set[str] = set()
    unique_raw: list[dict] = []
    for raw in raw_list:
        raw_id = str(raw.get("id", ""))
        if raw_id and raw_id in seen_ids:
            continue
        if raw_id:
            seen_ids.add(raw_id)
        unique_raw.append(raw)

    listings = []
    for raw in unique_raw:
        listing = parse_ad(raw)
        if listing:
            listings.append(listing)
    return listings
