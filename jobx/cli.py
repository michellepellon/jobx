#!/usr/bin/env python3
"""Command-line interface for jobx job scraper."""

import argparse
import sys

from jobx import scrape_jobs


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
  jobx -q "backend engineer" -l "Seattle" -o jobs.parquet -f parquet
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
        choices=["csv", "parquet"],
        default="csv",
        help="Output format (default: csv)",
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

    args = parser.parse_args()

    try:
        if args.verbose:
            print(f"Scraping {args.sites} for '{args.query}' in '{args.location}'...")

        df = scrape_jobs(
            site_name=args.sites,
            search_term=args.query,
            location=args.location,
            results_wanted=args.number,
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

        if args.output:
            if args.format == "parquet":
                df.to_parquet(args.output, index=False)
            else:
                df.to_csv(args.output, index=False)
            if args.verbose:
                print(f"Saved {len(df)} jobs to {args.output} in {args.format} format")
        else:
            if args.format == "parquet":
                print("Error: Parquet format requires an output file (-o/--output)", file=sys.stderr)
                sys.exit(1)
            print(df.to_csv(index=False))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
