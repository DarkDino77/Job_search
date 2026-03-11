"""
fetchers/jobsearch_client.py
Fetches job ads from Arbetsförmedlingen's Platsbanken via the JobSearch API.
"""

import time
import os
import requests
from dotenv import load_dotenv

from constants import FETCH_LIMIT_PER_PAGE, POLITE_DELAY_SECONDS
from config import OCCUPATION_FIELD_DATA_IT, REGION_CODES

load_dotenv()

JOBSEARCH_BASE = "https://jobsearch.api.jobtechdev.se"

def _get_headers() -> dict:
    api_key = os.getenv("JOBTECHDEV_API_KEY", "")
    headers = {"accept": "application/json"}
    if api_key:
        headers["api-key"] = api_key
    return headers


def search_jobs(
    query: str,
    offset: int = 0,
    limit: int = FETCH_LIMIT_PER_PAGE,
    occupation_field: str = OCCUPATION_FIELD_DATA_IT,
    region_codes: list[str] = None,
) -> dict:
    """
    Search Platsbanken for job ads matching `query`.
    Returns the raw JSON response dict.
    """
    params: dict = {
        "q": query,
        "offset": offset,
        "limit": limit,
    }
    if occupation_field:
        params["occupation-field"] = occupation_field
    if region_codes:
        # API accepts multiple region params
        params["region"] = region_codes

    response = requests.get(
        f"{JOBSEARCH_BASE}/search",
        headers=_get_headers(),
        params=params,
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def fetch_all_jobs(
    query: str,
    occupation_field: str = OCCUPATION_FIELD_DATA_IT,
    region_codes: list[str] = None,
) -> list[dict]:
    """
    Paginate through all results for a query and return every hit as a list.
    """
    if region_codes is None:
        region_codes = REGION_CODES

    results = []
    offset = 0
    limit = FETCH_LIMIT_PER_PAGE

    print(f"  [JobSearch] Querying: '{query}' ...", end=" ", flush=True)

    while True:
        page = search_jobs(query, offset=offset, limit=limit,
                           occupation_field=occupation_field,
                           region_codes=region_codes)
        hits = page.get("hits", [])
        total = page.get("total", {}).get("value", 0)

        results.extend(hits)

        if offset == 0:
            print(f"{total} total results")

        if offset + limit >= total or not hits:
            break

        offset += limit
        time.sleep(POLITE_DELAY_SECONDS)

    return results


def fetch_ad_detail(ad_id: str) -> dict:
    """
    Fetch the full metadata for a single ad by its Arbetsförmedlingen ID.
    """
    response = requests.get(
        f"{JOBSEARCH_BASE}/ad/{ad_id}",
        headers=_get_headers(),
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def get_total_count(query: str, occupation_field: str = OCCUPATION_FIELD_DATA_IT) -> int:
    """
    Quick check — how many results does this query return?
    Used to decide whether to also query JobAd Links.
    """
    page = search_jobs(query, offset=0, limit=1, occupation_field=occupation_field)
    return page.get("total", {}).get("value", 0)
