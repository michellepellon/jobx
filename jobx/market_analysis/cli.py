#!/usr/bin/env python3
"""Command-line interface for jobx market analysis tool."""

import argparse
import sys
import time
from pathlib import Path
from datetime import datetime

from jobx.market_analysis.config_loader import load_config, validate_config
from jobx.market_analysis.batch_executor import BatchExecutor
from jobx.market_analysis.data_aggregator import DataAggregator
from jobx.market_analysis.report_generator import ReportGenerator
from jobx.market_analysis.logger import setup_logger


def main():
    """Main CLI entry point for market analysis."""
    parser = argparse.ArgumentParser(
        prog="jobx-market",
        description="Analyze job market compensation across multiple locations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  jobx-market config.yaml
  jobx-market config.yaml -v                   # Verbose output
  jobx-market config.yaml -o results/Q1_2024   # Custom output directory
  jobx-market config.yaml --min-sample 50      # Lower sample size threshold
        """,
    )
    
    parser.add_argument(
        "config",
        help="Path to YAML configuration file",
    )
    
    parser.add_argument(
        "-o", "--output",
        help="Output directory for results (default: YYYY-MM-DD_JobTitle_Analysis)",
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    
    parser.add_argument(
        "--min-sample",
        type=int,
        default=100,
        help="Minimum sample size for sufficient data (default: 100)",
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without executing searches",
    )
    
    args = parser.parse_args()
    
    # Start timer
    start_time = time.time()
    
    try:
        # Load configuration
        print(f"Loading configuration from: {args.config}")
        config = load_config(args.config)
        
        # Validate configuration
        warnings = validate_config(config)
        if warnings:
            print("\nConfiguration warnings:")
            for warning in warnings:
                print(f"  - {warning}")
        
        print(f"\nConfiguration loaded:")
        print(f"  Job Title: {config.job_title}")
        print(f"  Markets: {len(config.markets)}")
        print(f"  Total Locations: {config.total_locations}")
        print(f"  Search Radius: {config.search_radius} miles")
        print(f"  Results per Location: {config.results_per_location}")
        print(f"  Batch Size: {config.batch_size}")
        
        if args.dry_run:
            print("\nDry run complete. Configuration is valid.")
            return 0
        
        # Create output directory
        if args.output:
            output_dir = Path(args.output)
        else:
            date_str = datetime.now().strftime("%Y-%m-%d")
            job_title_safe = config.job_title.replace(' ', '_').replace('/', '-')
            output_dir = Path(f"{date_str}_{job_title_safe}_Analysis")
        
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"\nOutput directory: {output_dir}")
        
        # Setup logger
        logger = setup_logger(output_dir, args.verbose)
        logger.info("=" * 60)
        logger.info(f"Starting market analysis for: {config.job_title}")
        logger.info("=" * 60)
        
        # Execute searches
        print("\nStarting job searches...")
        executor = BatchExecutor(config, logger)
        market_results = executor.execute_all()
        
        # Get execution statistics
        exec_stats = executor.get_summary_stats()
        
        # Aggregate data by market
        print("\nAggregating market data...")
        aggregator = DataAggregator(logger, args.min_sample)
        aggregated_markets = aggregator.aggregate_all_markets(market_results)
        
        # Generate reports
        print("\nGenerating reports...")
        report_gen = ReportGenerator(output_dir, config.job_title, logger)
        generated_files = report_gen.generate_all_reports(aggregated_markets)
        
        # Calculate execution time
        elapsed_time = time.time() - start_time
        
        # Log execution summary
        markets_with_data = sum(1 for m in aggregated_markets.values() if m.has_sufficient_data)
        logger.execution_summary(
            total_locations=exec_stats['total_locations'],
            successful_locations=exec_stats['successful_locations'],
            total_jobs=exec_stats['total_jobs'],
            jobs_with_salary=exec_stats['jobs_with_salary'],
            markets_with_data=markets_with_data,
            total_markets=len(aggregated_markets),
            elapsed_time=elapsed_time
        )
        
        # Print summary to console
        print("\n" + "=" * 60)
        print("ANALYSIS COMPLETE")
        print("=" * 60)
        print(f"Locations Searched: {exec_stats['successful_locations']}/{exec_stats['total_locations']}")
        print(f"Total Jobs Found: {exec_stats['total_jobs']:,}")
        print(f"Jobs with Salary: {exec_stats['jobs_with_salary']:,}")
        print(f"Markets with Data: {markets_with_data}/{len(aggregated_markets)}")
        print(f"Reports Generated: {len(generated_files)}")
        print(f"Output Directory: {output_dir}")
        
        hours = int(elapsed_time // 3600)
        minutes = int((elapsed_time % 3600) // 60)
        seconds = int(elapsed_time % 60)
        print(f"Execution Time: {hours:02d}:{minutes:02d}:{seconds:02d}")
        print("=" * 60)
        
        return 0
        
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())