#!/usr/bin/env python3
"""Command-line interface for jobx market analysis tool with role-based support."""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from jobx.market_analysis.batch_executor import BatchExecutor
from jobx.market_analysis.config_loader import Config, load_config, validate_config
from jobx.market_analysis.data_aggregator import DataAggregator
from jobx.market_analysis.logger import setup_logger
from jobx.market_analysis.report_generator import ReportGenerator
from jobx.market_analysis.visualization import CompensationBandVisualizer


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
        default=100,
        help="Minimum sample size for sufficient data (default: 100)",
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
        
        executor = BatchExecutor(config, logger, output_dir=str(output_dir), enable_safety=enable_safety)
        
        if args.role:
            # Search for specific role
            market_results = executor.execute_for_role(args.role)
            exec_stats = executor.get_role_stats(args.role)
        else:
            # Search for all roles
            market_results = executor.execute_all()
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
        
        # ReportGenerator expects 3 args: output_dir, job_title, logger
        report_gen = ReportGenerator(output_dir, report_title, logger)
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
        elapsed_time = time.time() - start_time
        
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
        
        return 0
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
        
    except ValueError as e:
        print(f"Configuration error: {e}")
        return 1
        
    except KeyboardInterrupt:
        print("\n\nAnalysis interrupted by user")
        return 130
        
    except Exception as e:
        print(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())