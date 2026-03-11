# Job Web Crawler — Project Plan
> Built for a final-year CS student targeting Swedish tech roles via Arbetsförmedlingen.

---

## ⚠️ Important Discovery: Official Open API Available

After inspecting the target site, **scraping `arbetsformedlingen.se` directly is unnecessary**.
Arbetsförmedlingen publishes all their job data through **JobTech Dev** — a suite of free, open, government-provided APIs that return clean JSON directly. This is exactly the "undocumented API" scenario described in Step 2 of the guide, except here it's fully documented and officially supported.

**You should use the API, not HTML scraping.** This is faster, more stable, and legally unambiguous.

---

## The JobTech Dev API Ecosystem

All APIs are free and open. The public JobSearch and JobAd Links APIs appear to require no registration — try making a request first before signing up at `apirequest.jobtechdev.se`.

| API | Base URL | Purpose |
|---|---|---|
| **JobSearch** | `jobsearch.api.jobtechdev.se` | Search Platsbanken ads by keyword, occupation, region |
| **JobAd Links** | `links.api.jobtechdev.se` | Broader market — search across *all* Swedish job ads, not just Platsbanken |
| **JobStream** | `jobstream.api.jobtechdev.se` | Real-time feed of new/updated/removed ads |
| **Taxonomy** | `taxonomy.api.jobtechdev.se` | Get structured occupation & skill concept IDs |
| **JobAd Enrichments** | *(Swagger UI via jobtechdev.se)* | AI extraction of skills from ad text |
| **Historical Ads** | *(via jobtechdev.se)* | Archived ads back to 2016, all AI-enriched with skills |

All requests return JSON. Where an `api-key` header is required, store it in `.env` — never hardcode it.

---

## Phase 1: Setup & Data Model
*Based on Step 1 — plan your schema before writing code.*

### Step 1a: API Access
The public APIs (JobSearch, JobAd Links, Taxonomy) appear to be freely accessible without registration. Start by making a test request immediately:

```bash
curl "https://jobsearch.api.jobtechdev.se/search?q=python&limit=1"
```

If you get a `401 Unauthorized`, register for a free key at `apirequest.jobtechdev.se`, then store it:

```bash
# .env
JOBTECHDEV_API_KEY=your_key_here
```

### Step 1b: Data Model

```python
@dataclass
class JobListing:
    id: str                  # Arbetsförmedlingen's own ad ID (use as primary key)
    title: str               # e.g. "Junior Backend Developer"
    company: str
    location: str            # city or "Distansarbete" (remote)
    municipality: str        # Swedish municipality name
    date_published: datetime
    last_date_application: datetime | None
    description_text: str    # cleaned plain text
    description_html: str    # raw HTML for re-processing
    required_skills: list[str]   # extracted from Enrichments API
    employment_type: str     # e.g. "Vanlig anställning"
    duration: str            # e.g. "Tillsvidareanställd"
    scope: str               # e.g. "Heltid"
    url: str                 # direct link to the ad on Platsbanken or original site
    source_api: str          # "jobsearch" or "jobadlinks"
    relevance_score: float   # computed locally
```

### Step 1c: Ethics & Legal Checklist
- [x] Official open data — no `robots.txt` issues
- [x] No throttling needed beyond reasonable rate limits
- [x] No personal data collected (job ads are public postings)
- [ ] Still review the JobTech Dev terms of use at `jobtechdev.se`

---

## Phase 2: Understand the API Endpoints
*Based on Step 2 — inspect before you fetch.*

### Primary Endpoint: JobSearch `/search`

```
GET https://jobsearch.api.jobtechdev.se/search
    ?q=python developer
    &municipality=0180          # Stockholm
    &offset=0
    &limit=100
```

Key query parameters:
| Parameter | Description |
|---|---|
| `q` | Free-text search (title, description, employer) |
| `occupation-name` | Structured occupation concept ID (from Taxonomy API) |
| `occupation-field` | Broad field ID, e.g. "Data/IT" (concept ID: `apaJ_2ja_LuF`) |
| `municipality` | Filter by Swedish municipality code |
| `region` | Filter by county (e.g. Östergötland = `05`) |
| `remote` | `true` to filter for remote-only roles |
| `offset` + `limit` | Pagination (max 100 per page) |

### Finding the Right Occupation IDs (Taxonomy API)

Before searching for "software engineer", look up the structured concept ID:

```python
# Step 1: Query Taxonomy API for occupation field "Data/IT"
GET https://taxonomy.api.jobtechdev.se/v1/taxonomy/concepts?type=occupation-field&preferred-label=data

# Step 2: Use returned conceptId in JobSearch
GET https://jobsearch.api.jobtechdev.se/search?occupation-field=apaJ_2ja_LuF
```

### Fetching Full Ad Detail

```
GET https://jobsearch.api.jobtechdev.se/ad/{ad_id}
```

Returns the complete ad with all metadata. Use the `id` field from search results.

### Secondary Source: JobAd Links `/search`

JobAd Links covers the **entire Swedish job market** — not just Arbetsförmedlingen's own Platsbanken, but ads from private job boards and employer sites too. Use it as a fallback when JobSearch returns too few results, or to cross-check coverage.

```
GET https://links.api.jobtechdev.se/joblinks
    ?q=mjukvaruutvecklare
    &offset=0
    &limit=100
```

Key differences from JobSearch:

| | JobSearch | JobAd Links |
|---|---|---|
| Coverage | Platsbanken only | Whole Swedish market |
| Response | Full ad content | Title, employer, URL + link to original |
| Skills enrichment | Via Enrichments API | Pre-enriched in response |
| Best used for | Deep ad content + full metadata | Discovering ads not on Platsbanken |

**Recommended strategy:** run JobSearch first for full content. If `total.value` is under ~50 results for your query, also query JobAd Links and merge results by deduplicating on `url`.

---

## Phase 3: Fetch Layer
*Based on Step 3 — `requests` is sufficient here, no Selenium needed.*

Since the API returns clean JSON, the entire fetch layer is just:

```python
import requests
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("JOBTECHDEV_API_KEY")

HEADERS = {
    "accept": "application/json",
    "api-key": API_KEY
}

def search_jobs(query: str, offset: int = 0, limit: int = 100) -> dict:
    url = "https://jobsearch.api.jobtechdev.se/search"
    params = {
        "q": query,
        "occupation-field": "apaJ_2ja_LuF",  # Data/IT
        "offset": offset,
        "limit": limit
    }
    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    return response.json()

def fetch_ad_detail(ad_id: str) -> dict:
    url = f"https://jobsearch.api.jobtechdev.se/ad/{ad_id}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()
```

### Pagination Strategy

The API returns a `total.value` field. Paginate with `offset` until all results are fetched:

```python
def fetch_all_jobs(query: str) -> list[dict]:
    results = []
    offset = 0
    limit = 100
    while True:
        page = search_jobs(query, offset, limit)
        hits = page.get("hits", [])
        results.extend(hits)
        if offset + limit >= page["total"]["value"]:
            break
        offset += limit
        time.sleep(1)   # polite delay even on open APIs
    return results
```

### JobAd Links Fetcher — `jobadlinks_client.py`

Use this when JobSearch alone returns too few results. JobAd Links returns a `url` pointing to the original ad on an external site, so the response shape is leaner than JobSearch.

```python
def search_jobad_links(query: str, offset: int = 0, limit: int = 100) -> dict:
    url = "https://links.api.jobtechdev.se/joblinks"
    params = {"q": query, "offset": offset, "limit": limit}
    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    return response.json()
```

### Merging Results from Both Sources

Deduplicate across sources using the ad URL as the common key:

```python
def merge_and_deduplicate(jobsearch_hits: list, jobadlinks_hits: list) -> list:
    seen_urls = set()
    merged = []
    for hit in jobsearch_hits + jobadlinks_hits:
        url = hit.get("webpage_url") or hit.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            merged.append(hit)
    return merged
```

### Project Structure

```
job-crawler/
├── fetchers/
│   ├── jobsearch_client.py    # JobSearch + JobStream API calls
│   ├── jobadlinks_client.py   # JobAd Links — broader market coverage
│   └── taxonomy_client.py     # Lookup occupation concept IDs
├── parsers/
│   └── ad_parser.py           # JSON → JobListing dataclass (handles both sources)
├── pipeline/
│   ├── cleaner.py             # text normalisation
│   ├── scorer.py              # relevance scoring
│   └── storage.py             # SQLite persistence
├── models/
│   └── job_listing.py
├── config.py                  # CS-relevant keywords, region codes
├── .env                       # API key (git-ignored)
├── .gitignore
├── main.py
└── plan.md
```

---

## Phase 4: Parse & Extract
*Based on Step 4 — JSON replaces BeautifulSoup here, but cleaning is still needed.*

The API returns structured JSON so there is no HTML to parse. However:

- Descriptions come back as **raw HTML strings** — use `BeautifulSoup` to strip tags cleanly
- Use Python's `json` library to map response fields directly onto the `JobListing` dataclass
- Use `re` (regex) to pull salary hints and experience requirements out of description text
- Use the **JobAd Enrichments API** to get AI-extracted required skills per ad (optional but powerful)

```python
from bs4 import BeautifulSoup

def parse_ad(raw: dict) -> JobListing:
    desc_html = raw.get("description", {}).get("text", "")
    desc_text = BeautifulSoup(desc_html, "html.parser").get_text(separator=" ").strip()
    return JobListing(
        id=raw["id"],
        title=raw.get("headline", ""),
        company=raw.get("employer", {}).get("name", ""),
        location=raw.get("workplace_address", {}).get("city", ""),
        ...
        description_text=desc_text,
        description_html=desc_html,
    )
```

---

## Phase 5: Anti-Scraping Countermeasures
*Based on Step 5 — largely not applicable, but good practice remains.*

Since this is an official API, you don't need to spoof headers, rotate IPs, or handle CAPTCHAs. However:

- Always include your real `api-key` header — do not try to scrape without it
- Add `time.sleep(1)` between paginated requests as a courtesy
- Do not hammer the API with parallel threads — it's a public service

---

## Phase 6: Clean & Score
*Based on Step 6 — still needed even with clean API data.*

### Cleaning
- Strip HTML from description fields using `BeautifulSoup`
- Normalise Unicode with Python's `unicodedata` module (Swedish characters like å, ä, ö)
- Parse date strings (`published_date`) into Python `datetime` objects
- Deduplicate by `id` field

### Relevance Scoring for a CS Graduate

```python
KEYWORDS = {
    "high":   [
        "python", "software engineer", "backend", "frontend", "fullstack",
        "machine learning", "data engineer", "cloud", "junior", "trainee",
        "nyexaminerad", "exjobb", "examensarbete"  # Swedish graduate terms
    ],
    "medium": ["javascript", "typescript", "java", "sql", "api", "git", "linux"],
    "penalty": ["10 år", "senior lead", "chef", "manager", "director"]
}
```

Score each listing 0.0–1.0 based on keyword hits in title + description, with penalties for experience thresholds you don't meet.

---

## Phase 7: Store
*Based on Step 7 — SQLite is ideal for a personal job search tool.*

```sql
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,             -- Arbetsförmedlingen ad ID
    title TEXT,
    company TEXT,
    location TEXT,
    date_published TEXT,
    last_date_application TEXT,
    description_text TEXT,
    description_html TEXT,
    employment_type TEXT,
    url TEXT,
    relevance_score REAL,
    fetched_at TEXT                  -- when we stored it
);

CREATE INDEX idx_score ON jobs(relevance_score DESC);
CREATE INDEX idx_date  ON jobs(date_published DESC);
```

Use SQLite's built-in **FTS5** extension for full-text search across all descriptions — no extra dependencies needed.

---

## Phase 8: AI-Powered Evaluation via `prompttemplate.md`

A companion file `prompttemplate.md` pairs with the crawler output to enable AI-assisted job evaluation. The workflow is:

```
Crawler → job_listings.json → AI (prompttemplate.md + CV + listings) → ranked results + cover letter angles
```

### How It Works

1. After fetching and scoring, **export top listings** (`relevance_score > 0.6`) to `job_listings.json`
2. Fill in `prompttemplate.md` once with your skills, preferences, and deal-breakers
3. Submit the filled template + your CV PDF + `job_listings.json` together to an AI (e.g. Claude)
4. The AI returns a fit score (1–10), verdict, gaps, and cover letter angle per listing

### Export Function — add to `storage.py`

```python
import json, sqlite3

def export_top_listings(db_path: str, min_score: float = 0.6, limit: int = 20):
    conn = sqlite3.connect(db_path)
    cursor = conn.execute(
        "SELECT * FROM jobs WHERE relevance_score >= ? ORDER BY relevance_score DESC LIMIT ?",
        (min_score, limit)
    )
    cols = [d[0] for d in cursor.description]
    listings = [dict(zip(cols, row)) for row in cursor.fetchall()]
    conn.close()
    with open("job_listings.json", "w", encoding="utf-8") as f:
        json.dump(listings, f, ensure_ascii=False, indent=2)
    print(f"Exported {len(listings)} listings to job_listings.json")
```

### Files Overview

| File | Purpose |
|---|---|
| `prompttemplate.md` | Filled once by you — defines skills, preferences, deal-breakers, and AI instructions |
| `CV_[name].pdf` | Attached alongside the template when prompting the AI |
| `job_listings.json` | Exported from crawler — the batch of ads for the AI to evaluate |

---

## Phase 9: Stretch Goals
*Based on Step 8 — scale up once the core pipeline works.*

- [ ] **JobStream integration:** Subscribe to `jobstream.api.jobtechdev.se` for real-time new/removed/updated events — keeps your local DB always current without re-fetching everything
- [ ] **JobAd Enrichments API:** Feed raw description text to get AI-extracted skills list per ad
- [ ] **Scheduler:** Use `APScheduler` or a daily `cron` job to re-run and sync
- [ ] **Streamlit UI:** Build a simple local web dashboard to browse and filter stored results
- [ ] **Notifications:** Email or Telegram alert when a high-score listing appears

---

## Milestones

| # | Milestone | Est. Time |
|---|---|---|
| 1 | API key obtained, test query working in terminal | Day 1 |
| 2 | `JobListing` dataclass + `ad_parser.py` mapping all fields | Day 1–2 |
| 3 | Paginating fetcher + SQLite storage end-to-end | Day 2–3 |
| 4 | Cleaning pipeline (HTML strip, Unicode, date parsing) | Day 3–4 |
| 5 | Relevance scorer with CS-specific keywords (Swedish + English) | Day 4–5 |
| 6 | CLI to query and display top results + `export_top_listings()` | Day 5–6 |
| 7 | Fill `prompttemplate.md`, run first AI evaluation batch | Day 7 |
| 8 | JobStream real-time sync (stretch) | Week 2 |
| 9 | Streamlit dashboard (stretch) | Week 2–3 |

---

## Dependencies

```txt
requests          # HTTP calls to the API
python-dotenv     # load API key from .env
beautifulsoup4    # strip HTML from description fields
pandas            # bulk date/text cleaning
```

No Selenium, no Scrapy, no proxy libraries needed for this target.

---

*Reference: Ryan Mitchell, Web Scraping with Python: Data Extraction from the Modern Web (2024)*
*API Reference: jobtechdev.se — JobSearch, JobStream, Taxonomy APIs*
