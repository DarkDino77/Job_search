from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class JobListing:
    id: str                              # Arbetsförmedlingen ad ID — primary key
    title: str                           # e.g. "Junior Backend Developer"
    company: str                         # employer name
    location: str                        # city or "Distansarbete"
    municipality: str                    # Swedish municipality name
    date_published: str                  # ISO date string
    last_date_application: str           # ISO date string or ""
    description_text: str                # cleaned plain text
    description_html: str                # raw HTML for re-processing
    required_skills: list[str]           # extracted skills
    employment_type: str                 # e.g. "Vanlig anställning"
    duration: str                        # e.g. "Tillsvidareanställd"
    scope: str                           # e.g. "Heltid"
    url: str                             # link to ad
    source_api: str                      # "jobsearch" or "jobadlinks"
    relevance_score: float = 0.0         # computed by scorer
    fetched_at: str = ""                 # ISO timestamp when stored
