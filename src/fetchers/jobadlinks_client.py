"""
fetchers/jobadlinks_client.py
Fetches job ads from the broader Swedish market via the JobAd Links API.
Used as a fallback / supplement when JobSearch returns few results.
"""

import time
import os
import requests
from dotenv import load_dotenv

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import FETCH_LIMIT_PER_PAGE, POLITE_DELAY_SECONDS

load_dotenv()

JOBADLINKS_BASE = "https://links.api.jobtechdev.se"


def _get_headers() -> dict:
    api_key = os.getenv("JOBTECHDEV_API_KEY", "")
    headers = {"accept": "application/json"}
    if api_key:
        headers["api-key"] = api_key
    return headers


def search_jobad_links(
    query: str,
    offset: int = 0,
    limit: int = FETCH_LIMIT_PER_PAGE,
) -> dict:
    """
    Search the full Swedish job market via JobAd Links.
    Returns leaner results than JobSearch (title, employer, URL).
    """
    params = {
        "q": query,
        "offset": offset,
        "limit": limit,
    }
    response = requests.get(
        f"{JOBADLINKS_BASE}/joblinks",
        headers=_get_headers(),
        params=params,
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def fetch_all_jobad_links(query: str) -> list[dict]:
    """
    Paginate through all JobAd Links results for a query.
    Tags each hit with source_api = "jobadlinks" for later deduplication.
    """
    results = []
    offset = 0
    limit = FETCH_LIMIT_PER_PAGE

    print(f"  [JobAdLinks] Querying: '{query}' ...", end=" ", flush=True)

    while True:
        page = search_jobad_links(query, offset=offset, limit=limit)

        # JobAd Links may return hits under different keys — handle both
        hits = page.get("hits", page.get("ads", []))
        total = page.get("total", {}).get("value", len(hits))

        if offset == 0:
            print(f"{total} total results")

        # Tag source so the parser knows which schema to expect
        for hit in hits:
            hit["_source_api"] = "jobadlinks"

        results.extend(hits)

        if offset + limit >= total or not hits:
            break

        offset += limit
        time.sleep(POLITE_DELAY_SECONDS)

    return results


def merge_and_deduplicate(
    jobsearch_hits: list[dict],
    jobadlinks_hits: list[dict],
) -> list[dict]:
    """
    Combine hits from both APIs and remove duplicates.
    Deduplication key: webpage URL (prefers JobSearch entries when both exist).
    """
    seen_urls: set[str] = set()
    merged: list[dict] = []

    for hit in jobsearch_hits + jobadlinks_hits:
        # JobSearch uses 'webpage_url', JobAd Links may use 'url' or 'application_url'
        url = (
            hit.get("webpage_url")
            or hit.get("url")
            or hit.get("application_url")
            or hit.get("id", "")       # fall back to ID if no URL
        )
        url = str(url).strip()
        if url and url not in seen_urls:
            seen_urls.add(url)
            merged.append(hit)

    return merged
