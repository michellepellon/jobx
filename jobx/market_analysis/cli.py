#!/usr/bin/env python3
"""Command-line interface for jobx market analysis tool with role-based support."""

import argparse
import json
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

# Exit codes
EXIT_SUCCESS = 0       # All tasks completed successfully
EXIT_FAILURE = 1       # No tasks succeeded or config error
EXIT_PARTIAL = 2       # Some tasks succeeded, some failed
EXIT_INTERRUPTED = 130 # SIGTERM/SIGINT, progress checkpointed

from jobx.market_analysis.batch_executor import BatchExecutor, ErrorCategory
from jobx.market_analysis.config_loader import Config, load_config, validate_config
from jobx.market_analysis.data_aggregator import DataAggregator
from jobx.market_analysis.logger import setup_logger
from jobx.market_analysis.report_generator import ReportGenerator
from jobx.market_analysis.visualization import CompensationBandVisualizer


def _format_duration(seconds: float) -> str:
    """Format seconds into a human-readable string like '2h 27m 33s'."""
    h, remainder = divmod(int(seconds), 3600)
    m, s = divmod(remainder, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m or h:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


def _generate_recommendation(
    total: int,
    failed: int,
    error_summary: Dict[str, Any],
    shutdown_requested: bool,
) -> str:
    """Generate a one-line operational recommendation based on run outcome."""
    if shutdown_requested:
        return "Run was interrupted. Resume with --resume flag."

    if total == 0:
        return "No tasks were executed. Check configuration."

    if failed == 0:
        return "All tasks succeeded. No re-run needed."

    by_cat = error_summary.get("by_category", {})
    failure_pct = (failed / total * 100) if total else 0

    # All failures are structural no-data
    if list(by_cat.keys()) == [ErrorCategory.NO_DATA.value]:
        return (
            f"{failed} failures ({failure_pct:.0f}%), all 'no_data' (structural). "
            "Re-run will not help."
        )

    parts = []
    if by_cat.get(ErrorCategory.RATE_LIMIT.value):
        parts.append("Consider increasing delays or using --safe-mode.")

    network_count = by_cat.get(ErrorCategory.NETWORK.value, 0)
    if network_count > failed / 2:
        parts.append("Majority network errors — check connectivity and retry with --resume.")

    if failure_pct >= 30:
        parts.append("High failure rate — investigate before re-running.")

    if not parts:
        parts.append(f"{failed} failures ({failure_pct:.1f}%). Review errors and consider --resume.")

    return " ".join(parts)


def _build_run_summary(
    *,
    start_time: float,
    end_time: float,
    config: Config,
    config_file: str,
    executor: BatchExecutor,
    exec_stats: Dict[str, Any],
    aggregated_markets: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the structured run summary dict written to ``run_summary.json``."""
    duration = round(end_time - start_time, 1)
    total = exec_stats.get("total_tasks", 0)
    successful = exec_stats.get("successful_tasks", 0)
    failed = total - successful
    total_jobs = exec_stats.get("total_jobs", 0)
    jobs_with_salary = exec_stats.get("jobs_with_salary", 0)

    timing = executor.get_timing_stats()
    error_summary = executor.get_error_summary()
    slowest = executor.get_slowest_searches(5)

    # Exit status
    if executor.shutdown_requested:
        exit_status = "interrupted"
    elif total == 0 or successful == 0:
        exit_status = "failure"
    elif failed > 0:
        exit_status = "partial"
    else:
        exit_status = "success"

    markets_with_data = sum(1 for m in aggregated_markets.values() if m.has_sufficient_data)

    # Per-role breakdown
    per_role: Dict[str, Any] = {}
    for role in config.roles:
        role_stats = executor.get_role_stats(role.id)
        role_results = [r for r in executor.results if r.role.id == role.id]
        role_durations = [r.duration_seconds for r in role_results if r.duration_seconds is not None]
        role_durations.sort()
        n = len(role_durations)
        per_role[role.id] = {
            "tasks": role_stats["total_tasks"],
            "successful": role_stats["successful_tasks"],
            "failed": role_stats["total_tasks"] - role_stats["successful_tasks"],
            "jobs_found": role_stats["total_jobs"],
            "search_duration_p50_seconds": round(role_durations[int(n * 0.50)], 2) if n else 0,
            "search_duration_p95_seconds": round(role_durations[min(int(n * 0.95), n - 1)], 2) if n else 0,
        }

    # Per-market breakdown
    per_market: Dict[str, Any] = {}
    for market_name, market_data in aggregated_markets.items():
        market_results = [r for r in executor.results if r.market_name == market_name]
        m_total = len(market_results)
        m_success = sum(1 for r in market_results if r.success)
        per_market[market_name] = {
            "tasks": m_total,
            "successful": m_success,
            "failed": m_total - m_success,
            "jobs_found": sum(r.jobs_found for r in market_results),
            "with_sufficient_data": market_data.has_sufficient_data,
        }

    recommendation = _generate_recommendation(total, failed, error_summary, executor.shutdown_requested)

    started_at = datetime.fromtimestamp(start_time, tz=timezone.utc).isoformat()
    finished_at = datetime.fromtimestamp(end_time, tz=timezone.utc).isoformat()

    return {
        "schema_version": 1,
        "run_started_at": started_at,
        "run_finished_at": finished_at,
        "duration_seconds": duration,
        "duration_human": _format_duration(duration),
        "exit_status": exit_status,
        "shutdown_requested": executor.shutdown_requested,
        "config_file": config_file,
        "config_summary": {
            "roles": [r.id for r in config.roles],
            "regions": len(config.regions),
            "markets": len(config.all_markets),
            "centers": config.total_locations,
            "search_radius_miles": config.search.radius_miles,
            "batch_size": config.search.batch_size,
        },
        "tasks": {
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate_pct": round(successful / total * 100, 1) if total else 0,
        },
        "jobs": {
            "total_found": total_jobs,
            "with_salary": jobs_with_salary,
            "salary_rate_pct": round(jobs_with_salary / total_jobs * 100, 1) if total_jobs else 0,
        },
        "markets": {
            "total": len(aggregated_markets),
            "with_sufficient_data": markets_with_data,
        },
        "timing": {
            "search_duration_p50_seconds": timing["p50"],
            "search_duration_p95_seconds": timing["p95"],
            "search_duration_max_seconds": timing["max"],
            "slowest_searches": slowest,
        },
        "errors": error_summary,
        "per_role": per_role,
        "per_market": per_market,
        "recommendation": recommendation,
    }


def main():
    """Main CLI entry point for market analysis."""
    parser = argparse.ArgumentParser(
        prog="jobx-market",
        description="Analyze job market compensation across multiple locations and roles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  jobx-market config.yaml                      # Run full analysis
  jobx-market config.yaml -v                   # Verbose output
  jobx-market config.yaml -o results/Q1_2024   # Custom output directory
  jobx-market config.yaml --role rbt           # Analyze specific role
  jobx-market config.yaml --min-sample 50      # Lower sample size threshold
  jobx-market config.yaml --dry-run            # Validate config only
        """,
    )
    
    parser.add_argument(
        "config",
        help="Path to YAML configuration file",
    )
    
    parser.add_argument(
        "-o", "--output",
        help="Output directory for results (default: YYYY-MM-DD_Analysis)",
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    
    parser.add_argument(
        "--role",
        help="Analyze specific role by ID (e.g., 'rbt', 'bcba')",
    )
    
    parser.add_argument(
        "--min-sample",
        type=int,
        default=None,
        help="Minimum sample size for sufficient data (default: from config, typically 100)",
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without executing searches",
    )
    
    parser.add_argument(
        "--migrate",
        help="Migrate old config format to new format (provide output path)",
    )
    
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="Generate compensation band visualization charts",
    )
    
    parser.add_argument(
        "--visualize-only",
        action="store_true",
        help="Only generate visualizations without running job searches",
    )
    
    parser.add_argument(
        "--safe-mode",
        action="store_true",
        help="Enable anti-detection features (smart scheduling, monitoring, progress tracking)",
    )
    
    parser.add_argument(
        "--no-safety",
        action="store_true",
        help="Disable all anti-detection safety features (not recommended)",
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint in existing output directory",
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=None,
        help="Max retry attempts per task on transient failure (default: from config, typically 3)",
    )

    args = parser.parse_args()
    
    # Handle migration
    if args.migrate:
        try:
            from jobx.market_analysis.config_loader import migrate_config
            migrate_config(args.config, args.migrate)
            print(f"Successfully migrated config to: {args.migrate}")
            return 0
        except Exception as e:
            print(f"Migration failed: {e}")
            return 1
    
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
        
        # Display configuration summary
        print(f"\nConfiguration loaded:")
        print(f"  Version: {config.meta.version}")
        print(f"  Roles: {len(config.roles)}")
        for role in config.roles:
            print(f"    - {role.id}: {role.name} ({role.pay_type.value})")
        print(f"  Regions: {len(config.regions)}")
        print(f"  Markets: {len(config.all_markets)}")
        print(f"  Total Centers: {config.total_locations}")
        print(f"  Search Radius: {config.search.radius_miles} miles")
        print(f"  Results per Location: {config.search.results_per_location}")
        print(f"  Batch Size: {config.search.batch_size}")
        
        # Show legacy config warning if applicable
        if config.job_title:
            print("\n⚠️  Legacy configuration detected. Consider migrating to new format.")
            print(f"   Use: jobx-market {args.config} --migrate new_config.yaml")
        
        if args.dry_run:
            print("\nDry run complete. Configuration is valid.")
            return 0
        
        # Handle visualize-only mode
        if args.visualize_only:
            # Create minimal output directory for charts
            if args.output:
                output_dir = Path(args.output)
            else:
                date_str = datetime.now().strftime("%Y-%m-%d")
                output_dir = Path(f"{date_str}_Compensation_Charts")
            
            output_dir.mkdir(parents=True, exist_ok=True)
            print(f"\nOutput directory: {output_dir}")
            
            # Generate visualizations
            print("\nGenerating compensation band charts...")
            visualizer = CompensationBandVisualizer(output_dir)
            
            # Load config as dict for visualization
            import yaml
            with open(args.config, 'r') as f:
                config_dict = yaml.safe_load(f)
            
            generated_charts = visualizer.generate_all_charts(config_dict, aggregated_markets)
            
            print(f"\nGenerated {len(generated_charts)} charts:")
            for chart_path in generated_charts:
                print(f"  - {chart_path}")
            
            return 0
        
        # Create output directory
        if args.output:
            output_dir = Path(args.output)
        else:
            date_str = datetime.now().strftime("%Y-%m-%d")
            if args.role:
                role = config.get_role(args.role)
                if role:
                    role_safe = role.name.replace(' ', '_').replace('/', '-')
                    output_dir = Path(f"{date_str}_{role_safe}_Analysis")
                else:
                    print(f"Error: Role '{args.role}' not found in configuration")
                    return 1
            else:
                output_dir = Path(f"{date_str}_Market_Analysis")
        
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"\nOutput directory: {output_dir}")
        
        # Setup logger
        logger = setup_logger(output_dir, args.verbose)
        logger.info("=" * 60)
        if args.role:
            role = config.get_role(args.role)
            logger.info(f"Starting market analysis for role: {role.name}")
        else:
            logger.info(f"Starting market analysis for {len(config.roles)} roles")
        logger.info("=" * 60)
        
        # Execute searches
        print("\nStarting job searches...")
        # Determine safety mode (default is enabled unless explicitly disabled)
        enable_safety = not args.no_safety
        if args.safe_mode:
            enable_safety = True
            print("✓ Anti-detection safety features enabled")
        elif args.no_safety:
            print("⚠️  Warning: Anti-detection safety features disabled")
        
        executor = BatchExecutor(
            config, logger, output_dir=str(output_dir),
            enable_safety=enable_safety, max_retries=args.max_retries,
        )

        # Register signal handlers for graceful shutdown
        def _handle_signal(signum, frame):
            sig_name = signal.Signals(signum).name
            print(f"\n{sig_name} received — finishing in-flight tasks and checkpointing...")
            executor.request_shutdown()

        signal.signal(signal.SIGTERM, _handle_signal)
        signal.signal(signal.SIGINT, _handle_signal)

        if args.role:
            # Search for specific role
            market_results = executor.execute_for_role(args.role)
            exec_stats = executor.get_role_stats(args.role)
        else:
            # Search for all roles
            market_results = executor.execute_all(resume=args.resume)
            exec_stats = executor.get_summary_stats()
        
        # Aggregate data by market
        print("\nAggregating market data...")
        aggregator = DataAggregator(config, logger, args.min_sample)
        aggregated_markets = aggregator.aggregate_all_markets(market_results)
        
        # Generate reports
        print("\nGenerating reports...")
        if args.role:
            role = config.get_role(args.role)
            report_title = f"{role.name} Market Analysis"
        else:
            report_title = "Multi-Role Market Analysis"
        
        # ReportGenerator expects 4 args: output_dir, job_title, logger, location_results
        report_gen = ReportGenerator(output_dir, report_title, logger, market_results)
        generated_files = report_gen.generate_all_reports(aggregated_markets)
        
        # Generate visualizations if requested
        if args.visualize:
            print("\nGenerating compensation band charts...")
            visualizer = CompensationBandVisualizer(output_dir)
            
            # Load config as dict for visualization
            import yaml
            with open(args.config, 'r') as f:
                config_dict = yaml.safe_load(f)
            
            generated_charts = visualizer.generate_all_charts(config_dict, aggregated_markets)
            generated_files.extend(generated_charts)
            
            print(f"Generated {len(generated_charts)} visualization charts")
            logger.info(f"Generated {len(generated_charts)} compensation band charts")
        
        # Generate role comparison if multiple roles
        if not args.role and len(config.roles) > 1:
            for role in config.roles:
                comparison_df = aggregator.get_role_comparison(role.id, aggregated_markets)
                if not comparison_df.empty:
                    comparison_file = output_dir / f"role_comparison_{role.id}.csv"
                    comparison_df.to_csv(comparison_file, index=False)
                    generated_files.append(comparison_file)
                    logger.info(f"Generated role comparison: {comparison_file}")
        
        # Calculate execution time
        elapsed_time = time.time() - start_time  # also used by run_summary via end_time
        
        # Log execution summary
        markets_with_data = sum(1 for m in aggregated_markets.values() if m.has_sufficient_data)
        
        if args.role:
            logger.info("=" * 60)
            logger.info(f"ROLE ANALYSIS COMPLETE: {role.name}")
            logger.info("=" * 60)
            logger.info(f"Tasks Executed: {exec_stats['total_tasks']}")
            logger.info(f"Successful Tasks: {exec_stats['successful_tasks']}")
            logger.info(f"Total Jobs Found: {exec_stats['total_jobs']:,}")
            logger.info(f"Jobs with Salary: {exec_stats['jobs_with_salary']:,}")
            logger.info(f"Success Rate: {exec_stats['success_rate']:.1f}%")
            logger.info(f"Elapsed Time: {elapsed_time:.1f} seconds")
        else:
            logger.execution_summary(
                total_locations=exec_stats['total_locations'],
                successful_locations=exec_stats['successful_locations'],
                total_jobs=exec_stats['total_jobs'],
                jobs_with_salary=exec_stats['jobs_with_salary'],
                markets_with_data=markets_with_data,
                total_markets=len(aggregated_markets),
                elapsed_time=elapsed_time
            )
        
        # Show safety report if enabled
        if enable_safety and hasattr(executor, 'monitor') and executor.monitor:
            print("\n" + "=" * 60)
            print("ANTI-DETECTION REPORT")
            print("=" * 60)
            print(executor.monitor.get_summary())
        
        # Write structured run summary
        end_time = time.time()
        run_summary = _build_run_summary(
            start_time=start_time,
            end_time=end_time,
            config=config,
            config_file=args.config,
            executor=executor,
            exec_stats=exec_stats,
            aggregated_markets=aggregated_markets,
        )
        summary_path = output_dir / "run_summary.json"
        summary_path.write_text(json.dumps(run_summary, indent=2))
        logger.info(f"Run summary written to {summary_path}")

        # Print summary to console
        print("\n" + "=" * 60)
        print("ANALYSIS COMPLETE")
        print("=" * 60)
        
        if args.role:
            print(f"Role: {role.name}")
            print(f"Tasks Executed: {exec_stats['total_tasks']}")
            print(f"Success Rate: {exec_stats['success_rate']:.1f}%")
        else:
            print(f"Roles Analyzed: {exec_stats.get('total_roles', len(config.roles))}")
            print(f"Locations Searched: {exec_stats['successful_locations']}/{exec_stats['total_locations']}")
        
        print(f"Total Jobs Found: {exec_stats['total_jobs']:,}")
        print(f"Jobs with Salary: {exec_stats['jobs_with_salary']:,}")
        print(f"Markets with Data: {markets_with_data}/{len(aggregated_markets)}")
        print(f"Reports Generated: {len(generated_files)}")
        print(f"Output Directory: {output_dir}")
        print(f"Elapsed Time: {elapsed_time:.1f} seconds")
        
        # Print payband comparison summary if available
        if not args.role and config.roles:
            print("\nPayband Comparison Summary:")
            for market_data in aggregated_markets.values():
                if market_data.role_data:
                    for role_id, role_data in market_data.role_data.items():
                        if role_data.payband and role_data.has_sufficient_data:
                            within = role_data.is_within_payband()
                            if within is not None:
                                status = "✓" if within else "✗"
                                print(
                                    f"  {status} {market_data.market_name} - {role_data.role.name}: "
                                    f"${role_data.median_salary:,.0f} "
                                    f"(band: ${role_data.payband.min:,.0f}-${role_data.payband.max:,.0f})"
                                )
        
        # Determine exit code
        if executor.shutdown_requested:
            print("\nProgress checkpointed. Resume with --resume flag.")
            return EXIT_INTERRUPTED
        total = exec_stats.get('total_tasks', 0)
        successful = exec_stats.get('successful_tasks', 0)
        if total == 0 or successful == 0:
            return EXIT_FAILURE
        if successful < total:
            return EXIT_PARTIAL
        return EXIT_SUCCESS

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return EXIT_FAILURE

    except ValueError as e:
        print(f"Configuration error: {e}")
        return EXIT_FAILURE

    except KeyboardInterrupt:
        print("\n\nAnalysis interrupted by user")
        return EXIT_INTERRUPTED
        
    except Exception as e:
        print(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return EXIT_FAILURE


if __name__ == "__main__":
    sys.exit(main())