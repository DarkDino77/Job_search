"""
fetchers/taxonomy_client.py
Queries the JobTech Taxonomy API to look up occupation field/name concept IDs.
Use this to find the right IDs to plug into config.py.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

TAXONOMY_BASE = "https://taxonomy.api.jobtechdev.se/v1/taxonomy"


def _get_headers() -> dict:
    api_key = os.getenv("JOBTECHDEV_API_KEY", "")
    headers = {"accept": "application/json"}
    if api_key:
        headers["api-key"] = api_key
    return headers


def search_occupation_fields(label: str) -> list[dict]:
    """
    Search for occupation-field concepts matching a label.
    Example: search_occupation_fields("data") → finds "Data/IT"
    """
    params = {
        "type": "occupation-field",
        "preferred-label": label,
    }
    response = requests.get(
        f"{TAXONOMY_BASE}/concepts",
        headers=_get_headers(),
        params=params,
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("data", data) if isinstance(data, dict) else data


def search_occupation_names(label: str) -> list[dict]:
    """
    Search for specific occupation-name concepts.
    Example: search_occupation_names("mjukvaruutvecklare")
    Returns a list of concepts with their conceptId to use in JobSearch.
    """
    params = {
        "type": "occupation-name",
        "preferred-label": label,
    }
    response = requests.get(
        f"{TAXONOMY_BASE}/concepts",
        headers=_get_headers(),
        params=params,
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("data", data) if isinstance(data, dict) else data


def print_occupation_fields(label: str = "data") -> None:
    """
    Convenience helper — prints concept IDs for occupation fields.
    Run this interactively to discover IDs for config.py.

    Usage:
        python -c "from fetchers.taxonomy_client import print_occupation_fields; print_occupation_fields('data')"
    """
    results = search_occupation_fields(label)
    if not results:
        print(f"No occupation fields found for '{label}'")
        return
    print(f"\nOccupation fields matching '{label}':")
    for r in results:
        concept_id = r.get("conceptId") or r.get("id", "?")
        preferred = r.get("preferredLabel") or r.get("preferred_label", "?")
        print(f"  {concept_id}  →  {preferred}")
