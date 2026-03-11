"""
pipeline/scorer.py
Scores each JobListing for relevance to a CS graduate job search.
Scores are 0.0–1.0.  Edit keywords in config.py to tune results.
"""

import re

from models.job_listing import JobListing
from config import SCORE_HIGH, SCORE_MEDIUM, SCORE_PENALTY


def _hit_count(text: str, keywords: list[str]) -> int:
    """Count how many keywords from the list appear in the text."""
    text_lower = text.lower()
    return sum(1 for kw in keywords if re.search(r"\b" + re.escape(kw.lower()) + r"\b", text_lower))


def score_listing(listing: JobListing) -> float:
    """
    Compute a relevance score between 0.0 and 1.0.

    Scoring logic:
      - Each HIGH keyword hit  →  +0.15  (capped)
      - Each MEDIUM keyword hit →  +0.07  (capped)
      - Title matches weigh double
      - Each PENALTY keyword hit →  -0.20
      - Skills list contribution →  small bonus
      - Final score is clamped to [0.0, 1.0]
    """
    # Combine title (weighted x2) + description
    search_text = (listing.title + " " + listing.title + " " + listing.description_text)
    skills_text = " ".join(listing.required_skills)

    high_hits   = _hit_count(search_text, SCORE_HIGH)
    medium_hits = _hit_count(search_text, SCORE_MEDIUM)
    penalty_hits = _hit_count(search_text + " " + listing.title, SCORE_PENALTY)

    # Skills bonus — pre-enriched skills from the API
    skill_bonus = min(len(listing.required_skills) * 0.02, 0.10)

    score = (
        min(high_hits   * 0.15, 0.60)   # max 0.60 from high keywords
      + min(medium_hits * 0.07, 0.25)   # max 0.25 from medium keywords
      + skill_bonus
      - penalty_hits * 0.20
    )

    return round(max(0.0, min(1.0, score)), 4)


def score_all(listings: list[JobListing]) -> list[JobListing]:
    """Score every listing in the batch and return them sorted best-first."""
    for listing in listings:
        listing.relevance_score = score_listing(listing)
    return sorted(listings, key=lambda l: l.relevance_score, reverse=True)
