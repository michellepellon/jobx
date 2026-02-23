#!/usr/bin/env python3
"""Command-line interface for jobx job scraper."""

import argparse
import json
import os
import sys

import pandas as pd

from jobx import __version__, scrape_jobs


def _df_to_json(df: pd.DataFrame) -> str:
    """Convert a DataFrame of job results to well-structured JSON."""
    jobs = []
    for _, row in df.iterrows():
        record = row.to_dict()

        # Nest compensation fields
        compensation = {
            "interval": record.pop("interval", None),
            "min": record.pop("min_amount", None),
            "max": record.pop("max_amount", None),
            "currency": record.pop("currency", None),
        }
        if any(v is not None for v in compensation.values()):
            record["compensation"] = compensation
        else:
            record["compensation"] = None

        # Convert emails from comma-separated string to list
        emails = record.get("emails")
        if isinstance(emails, str):
            record["emails"] = [e.strip() for e in emails.split(",")]
        elif pd.isna(emails) if isinstance(emails, float) else not emails:
            record["emails"] = []

        # Convert NaN/NaT to None for clean JSON
        jobs.append({
            k: (None if isinstance(v, float) and pd.isna(v) else v)
            for k, v in record.items()
        })

    return json.dumps({"jobs": jobs}, indent=2, default=str)


def main() -> None:
    """Main CLI entry point for jobx."""
    parser = argparse.ArgumentParser(
        prog="jobx",
        description="Scrape job listings from LinkedIn and Indeed",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  jobx -s linkedin -q "python developer" -l "New York" -n 50
  jobx -s indeed -q "data scientist" -l "San Francisco"
  jobx -s linkedin indeed -q "software engineer" -l "Remote" -n 100
  jobx -q "backend engineer" -l "Seattle" -o jobs.json
  jobx -q "ML engineer" -l "Austin" -o results.csv -f csv
  jobx -q "python developer" -l "New York" -c 0.7  # Only show jobs with 70%+ confidence
        """,
    )

    parser.add_argument(
        "-s",
        "--sites",
        nargs="+",
        choices=["linkedin", "indeed"],
        default=["linkedin", "indeed"],
        help="Job sites to scrape (default: both)",
    )

    parser.add_argument(
        "-q",
        "--query",
        required=True,
        help="Search term/job title to look for",
    )

    parser.add_argument(
        "-l",
        "--location",
        required=True,
        help="Location to search in",
    )

    parser.add_argument(
        "-n",
        "--number",
        type=int,
        default=50,
        help="Number of results to fetch (default: 50)",
    )

    parser.add_argument(
        "-o",
        "--output",
        help="Output file path (default: print to stdout)",
    )

    parser.add_argument(
        "-f",
        "--format",
        choices=["json", "csv", "parquet"],
        default="json",
        help="Output format (default: json)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    parser.add_argument(
        "-c",
        "--min-confidence",
        type=float,
        default=0.0,
        help="Minimum confidence score (0.0-1.0) to include results (default: 0.0)",
    )

    parser.add_argument(
        "--track-serp",
        action="store_true",
        help="Track SERP position (page index, rank) for each posting",
    )

    parser.add_argument(
        "--my-company",
        nargs="+",
        help="Company name(s) to track as 'my company' (can specify multiple)",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program version and exit",
    )

    args = parser.parse_args()

    # Support environment variable for my-company names
    if not args.my_company:
        env_companies = os.getenv("JOBX_MY_COMPANY")
        if env_companies:
            # Split by comma for multiple companies
            args.my_company = [c.strip() for c in env_companies.split(",")]

    try:
        if args.verbose:
            print(f"Scraping {args.sites} for '{args.query}' in '{args.location}'...")

        df = scrape_jobs(
            site_name=args.sites,
            search_term=args.query,
            location=args.location,
            results_wanted=args.number,
            track_serp=args.track_serp,
            my_company_names=args.my_company,
        )

        if df.empty:
            print("No jobs found matching your criteria.", file=sys.stderr)
            sys.exit(1)

        # Filter by minimum confidence score if specified
        if args.min_confidence > 0:
            original_count = len(df)
            df = df[df['confidence_score'] >= args.min_confidence]
            if args.verbose:
                filtered_count = original_count - len(df)
                print(f"Filtered out {filtered_count} jobs below confidence score {args.min_confidence}")

        if args.format == "json":
            output_str = _df_to_json(df)
            if args.output:
                with open(args.output, "w") as f:
                    f.write(output_str)
            else:
                print(output_str)
        elif args.format == "parquet":
            if not args.output:
                print("Error: Parquet format requires an output file (-o/--output)", file=sys.stderr)
                sys.exit(1)
            df.to_parquet(args.output, index=False)
        else:
            if args.output:
                df.to_csv(args.output, index=False)
            else:
                print(df.to_csv(index=False))

        if args.verbose and args.output:
            print(f"Saved {len(df)} jobs to {args.output} in {args.format} format")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
