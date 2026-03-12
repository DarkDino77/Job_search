#!/usr/bin/env python3
"""
main.py — Job Crawler CLI
Usage:
    python main.py fetch          # fetch + clean + score + store
    python main.py show           # print top results from DB
    python main.py search <query> # full-text search stored listings
    python main.py export         # export top listings to job_listings.json
    python main.py stats          # show DB statistics
"""

import sys
import os
# Ensure the src directory is on the path so subpackages are always found
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import textwrap

# ── Local imports ─────────────────────────────────────────────────────────────
from config import (
    SEARCH_QUERIES, OCCUPATION_FIELD_DATA_IT, REGION_CODES, EXPORT_MIN_SCORE,
)
from constants import JOBSEARCH_FALLBACK_THRESHOLD, EXPORT_MAX_LISTINGS
from fetchers.jobsearch_client import fetch_all_jobs, get_total_count
from fetchers.jobadlinks_client import fetch_all_jobad_links, merge_and_deduplicate
from parsers.ad_parser import parse_ads
from pipeline.cleaner import clean_all
from pipeline.scorer import score_all
from pipeline.storage import save_listings, query_top, full_text_search, export_top_listings, export_all_listings, export_top_csv, export_all_csv, export_location_csv, export_location_json, get_stats


# ─────────────────────────────────────────────────────────────────────────────
#  FETCH
# ─────────────────────────────────────────────────────────────────────────────

def cmd_fetch(args) -> None:
    """Fetch jobs from all configured queries, clean, score, and save."""
    all_raw: list[dict] = []

    for query in SEARCH_QUERIES:
        print(f"\n── Query: '{query}' ──")

        # Always fetch from JobSearch (Platsbanken)
        js_hits = fetch_all_jobs(
            query,
            occupation_field=OCCUPATION_FIELD_DATA_IT,
            region_codes=REGION_CODES,
        )

        # If results are thin, supplement with JobAd Links (whole market)
        jal_hits: list[dict] = []
        if len(js_hits) < JOBSEARCH_FALLBACK_THRESHOLD:
            print(f"  [main] Only {len(js_hits)} results from JobSearch — querying JobAd Links too")
            jal_hits = fetch_all_jobad_links(query)

        combined = merge_and_deduplicate(js_hits, jal_hits)
        print(f"  [main] {len(combined)} unique hits after merge")
        all_raw.extend(combined)

    # ── Parse ──────────────────────────────────────────────────────────────
    print(f"\n── Parsing {len(all_raw)} raw hits ──")
    listings = parse_ads(all_raw)
    print(f"  Parsed: {len(listings)} listings")

    # ── Clean ──────────────────────────────────────────────────────────────
    print("\n── Cleaning ──")
    listings = clean_all(listings)

    # ── Score ──────────────────────────────────────────────────────────────
    print("\n── Scoring ──")
    listings = score_all(listings)
    high = sum(1 for l in listings if l.relevance_score >= 0.5)
    print(f"  Scored {len(listings)} listings  ({high} with score ≥ 0.5)")

    # ── Store ──────────────────────────────────────────────────────────────
    print("\n── Saving to database ──")
    new_count = save_listings(listings)
    print(f"  {new_count} new listings saved  (existing ones updated)")

    print("\n✓ Fetch complete. Run 'python main.py show' to see top results.")


# ─────────────────────────────────────────────────────────────────────────────
#  SHOW
# ─────────────────────────────────────────────────────────────────────────────

def cmd_show(args) -> None:
    """Print top results from the database."""
    limit = args.limit
    min_score = args.min_score
    results = query_top(min_score=min_score, limit=limit)

    if not results:
        print(f"No results found with score ≥ {min_score}. Try lowering --min-score.")
        return

    print(f"\n{'─'*70}")
    print(f"  Top {len(results)} listings  (score ≥ {min_score})")
    print(f"{'─'*70}")

    for i, r in enumerate(results, 1):
        deadline = r.get("last_date_application") or "no deadline"
        print(f"\n{i:>3}.  [{r['relevance_score']:.2f}]  {r['title']}")
        print(f"       {r['company']}  —  {r['location'] or 'location unknown'}")
        print(f"       Published: {r['date_published']}  |  Deadline: {deadline}")
        print(f"       Source: {r['source_api']}  |  {r['url']}")

    print(f"\n{'─'*70}")
    print("Tip: run 'python main.py export' to save these for AI evaluation.")


# ─────────────────────────────────────────────────────────────────────────────
#  SEARCH
# ─────────────────────────────────────────────────────────────────────────────

def cmd_search(args) -> None:
    """Full-text search across stored listings."""
    query = " ".join(args.query)
    results = full_text_search(query, limit=args.limit)

    if not results:
        print(f"No results found for '{query}'.")
        return

    print(f"\nSearch results for '{query}':")
    print(f"{'─'*70}")
    for i, r in enumerate(results, 1):
        print(f"\n{i:>3}.  [{r['relevance_score']:.2f}]  {r['title']}")
        print(f"       {r['company']}  —  {r['location'] or '?'}")
        print(f"       {r['url']}")


# ─────────────────────────────────────────────────────────────────────────────
#  EXPORT
# ─────────────────────────────────────────────────────────────────────────────

def cmd_export(args) -> None:
    """Export top-scored listings to job_listings.json for AI evaluation."""
    count = export_top_listings(
        min_score=args.min_score,
        limit=args.limit,
    )
    if count == 0:
        print("Nothing to export. Run 'python main.py fetch' first.")
    else:
        print(f"\n✓ Exported {count} listings to job_listings.json")
        print("  Attach this file + your CV + prompttemplate.md to Claude for evaluation.")


# ─────────────────────────────────────────────────────────────────────────────
#  EXPORT ALL
# ─────────────────────────────────────────────────────────────────────────────

def cmd_export_all(args) -> None:
    """Export every job in the database to output/job_listings_all.json."""
    count = export_all_listings()
    if count == 0:
        print("Nothing to export. Run 'python main.py fetch' first.")
    else:
        print(f"\n✓ Exported all {count} listings to output/job_listings_all.json")


# ─────────────────────────────────────────────────────────────────────────────
#  EXPORT CSV
# ─────────────────────────────────────────────────────────────────────────────

def cmd_export_csv(args) -> None:
    """Export top-scored listings to output/job_listings.csv."""
    count = export_top_csv(min_score=args.min_score, limit=args.limit)
    if count == 0:
        print("Nothing to export. Run 'python main.py fetch' first, or lower --min-score.")
    else:
        print(f"\n✓ Exported {count} listings to output/job_listings.csv")
        print("  Open in Excel — Swedish characters (å ä ö) are encoded correctly.")


def cmd_export_all_csv(args) -> None:
    """Export every job in the database to output/job_listings_all.csv."""
    count = export_all_csv()
    if count == 0:
        print("Nothing to export. Run 'python main.py fetch' first.")
    else:
        print(f"\n✓ Exported all {count} listings to output/job_listings_all.csv")


# ─────────────────────────────────────────────────────────────────────────────
#  EXPORT LOCATION
# ─────────────────────────────────────────────────────────────────────────────

def _location_summary(terms: list[str], exclude: bool) -> str:
    mode = "excluding" if exclude else "only"
    quoted = ", ".join(f'"{t}"' for t in terms)
    return f"{mode} locations: {quoted}"


def cmd_export_location_csv(args) -> None:
    """Export jobs filtered by location to output/job_listings_location.csv."""
    count = export_location_csv(terms=args.locations, exclude=args.exclude)
    if count == 0:
        hint = "Try different locations or run 'python main.py fetch' first."
        print(f"Nothing to export. {hint}")
    else:
        print(f"\n✓ Exported {count} listings ({_location_summary(args.locations, args.exclude)})")
        print("  → output/job_listings_location.csv")


def cmd_export_location_json(args) -> None:
    """Export jobs filtered by location to output/job_listings_location.json."""
    count = export_location_json(terms=args.locations, exclude=args.exclude)
    if count == 0:
        hint = "Try different locations or run 'python main.py fetch' first."
        print(f"Nothing to export. {hint}")
    else:
        print(f"\n✓ Exported {count} listings ({_location_summary(args.locations, args.exclude)})")
        print("  → output/job_listings_location.json")


# ─────────────────────────────────────────────────────────────────────────────
#  STATS
# ─────────────────────────────────────────────────────────────────────────────

def cmd_stats(args) -> None:
    """Show database statistics."""
    stats = get_stats()
    print(f"\nDatabase stats:")
    print(f"  Total listings : {stats['total']}")
    print(f"  By source      : {stats['by_source']}")
    print(f"  Avg score      : {stats['avg_score']}")


# ─────────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="job-crawler",
        description="Fetch Swedish tech jobs from Arbetsförmedlingen's open API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python main.py fetch
              python main.py show --limit 20 --min-score 0.4
              python main.py search python django
              python main.py export --min-score 0.5
              python main.py export-all
              python main.py export-csv
              python main.py export-all-csv
              python main.py export-location-csv linköping norrköping
              python main.py export-location-csv -E stockholm
              python main.py export-location-json linköping
              python main.py stats
        """),
    )
    sub = parser.add_subparsers(dest="command")

    # fetch
    sub.add_parser("fetch", help="Fetch, clean, score, and store job listings")

    # show
    show_p = sub.add_parser("show", help="Print top results from the database")
    show_p.add_argument("--limit",     type=int,   default=20,  help="Max results (default: 20)")
    show_p.add_argument("--min-score", type=float, default=0.3, dest="min_score",
                        help="Minimum relevance score (default: 0.3)")

    # search
    search_p = sub.add_parser("search", help="Full-text search stored listings")
    search_p.add_argument("query", nargs="+", help="Search terms")
    search_p.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")

    # export (JSON top)
    export_p = sub.add_parser("export", help="Export top listings to output/job_listings.json")
    export_p.add_argument("--min-score", type=float, default=EXPORT_MIN_SCORE, dest="min_score",
                          help=f"Min score to include (default: {EXPORT_MIN_SCORE})")
    export_p.add_argument("--limit",     type=int,   default=EXPORT_MAX_LISTINGS,
                          help=f"Max listings to export (default: {EXPORT_MAX_LISTINGS})")

    # export-all (JSON all)
    sub.add_parser("export-all", help="Export every job in the DB to output/job_listings_all.json")

    # export-csv (CSV top)
    csv_p = sub.add_parser("export-csv", help="Export top listings to output/job_listings.csv")
    csv_p.add_argument("--min-score", type=float, default=EXPORT_MIN_SCORE, dest="min_score",
                       help=f"Min score to include (default: {EXPORT_MIN_SCORE})")
    csv_p.add_argument("--limit",     type=int,   default=EXPORT_MAX_LISTINGS,
                       help=f"Max listings to export (default: {EXPORT_MAX_LISTINGS})")

    # export-all-csv (CSV all)
    sub.add_parser("export-all-csv", help="Export every job in the DB to output/job_listings_all.csv")

    # export-location-csv
    loc_csv_p = sub.add_parser(
        "export-location-csv",
        help="Export jobs filtered by location to output/job_listings_location.csv",
        description=(
            "Filter the database by city/municipality before exporting to CSV.\n"
            "Each LOCATION term is matched against both the city and municipality columns.\n\n"
            "Include mode (default): export only jobs that match at least one term.\n"
            "Exclude mode (-E):      export all jobs EXCEPT those matching a term."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    loc_csv_p.add_argument(
        "locations", nargs="+",
        help='Location terms to match, e.g. linköping norrköping stockholm',
    )
    loc_csv_p.add_argument(
        "-E", "--exclude", action="store_true", default=False,
        help="Exclude matching locations instead of keeping them",
    )

    # export-location-json
    loc_json_p = sub.add_parser(
        "export-location-json",
        help="Export jobs filtered by location to output/job_listings_location.json",
        description=(
            "Filter the database by city/municipality before exporting to JSON.\n"
            "Each LOCATION term is matched against both the city and municipality columns.\n\n"
            "Include mode (default): export only jobs that match at least one term.\n"
            "Exclude mode (-E):      export all jobs EXCEPT those matching a term."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    loc_json_p.add_argument(
        "locations", nargs="+",
        help='Location terms to match, e.g. linköping norrköping stockholm',
    )
    loc_json_p.add_argument(
        "-E", "--exclude", action="store_true", default=False,
        help="Exclude matching locations instead of keeping them",
    )

    # stats
    sub.add_parser("stats", help="Show database statistics")

    return parser


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    commands = {
        "fetch":                 cmd_fetch,
        "show":                  cmd_show,
        "search":                cmd_search,
        "export":                cmd_export,
        "export-all":            cmd_export_all,
        "export-csv":            cmd_export_csv,
        "export-all-csv":        cmd_export_all_csv,
        "export-location-csv":   cmd_export_location_csv,
        "export-location-json":  cmd_export_location_json,
        "stats":                 cmd_stats,
    }

    if args.command not in commands:
        parser.print_help()
        sys.exit(0)

    commands[args.command](args)


if __name__ == "__main__":
    main()
