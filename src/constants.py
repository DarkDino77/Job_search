# ─────────────────────────────────────────────
#  constants.py  —  DO NOT EDIT
#  Fixed values used by the crawler internals.
#  To personalise the crawler, edit config.py.
# ─────────────────────────────────────────────

# ── Storage ───────────────────────────────────
DB_PATH = "output/jobs.db"

# ── Export paths ──────────────────────────────
EXPORT_PATH         = "output/job_listings.json"      # top-scored, for AI evaluation
EXPORT_ALL_PATH     = "output/job_listings_all.json"  # every job in the database
EXPORT_CSV_PATH     = "output/job_listings.csv"       # top-scored as CSV
EXPORT_ALL_CSV_PATH = "output/job_listings_all.csv"   # every job as CSV

# ── Export limits ─────────────────────────────
EXPORT_MAX_LISTINGS = 30    # max listings per top export batch

# ── Fetch settings ────────────────────────────
FETCH_LIMIT_PER_PAGE         = 100   # max results per API page (API hard limit)
JOBSEARCH_FALLBACK_THRESHOLD = 50    # if JobSearch returns fewer than this,
                                     # also query JobAd Links
POLITE_DELAY_SECONDS         = 1.0   # sleep between paginated requests
