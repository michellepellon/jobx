"""Report generator for market analysis results."""

import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd

from jobx.market_analysis.data_aggregator import MarketData
from jobx.market_analysis.statistics_calculator import StatisticsCalculator, CompensationStatistics
from jobx.market_analysis.logger import MarketAnalysisLogger
from jobx.market_analysis.batch_executor import LocationResult


class ReportGenerator:
    """Generates CSV reports for market analysis."""
    
    def __init__(self, output_dir: Path, job_title: str, logger: MarketAnalysisLogger,
                 location_results: Optional[Dict[str, List[LocationResult]]] = None):
        """Initialize report generator.

        Args:
            output_dir: Directory for output files
            job_title: Job title being analyzed
            logger: Logger instance
            location_results: Optional location results for center-level analysis
        """
        self.output_dir = output_dir
        self.job_title = job_title
        self.logger = logger
        self.stats_calculator = StatisticsCalculator()
        self.location_results = location_results or {}

        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def calculate_center_statistics(self, market_name: str) -> Dict[str, CompensationStatistics]:
        """Calculate statistics for each center within a market.

        Args:
            market_name: Name of the market

        Returns:
            Dictionary mapping center names to their statistics
        """
        center_stats = {}

        if market_name not in self.location_results:
            return center_stats

        # Group location results by center
        center_data = {}
        for location_result in self.location_results[market_name]:
            if location_result.success and location_result.jobs_df is not None:
                center_name = location_result.center.name
                if center_name not in center_data:
                    center_data[center_name] = []
                center_data[center_name].append(location_result.jobs_df)

        # Calculate statistics for each center
        from jobx.market_analysis.data_aggregator import DataAggregator
        aggregator = DataAggregator(None, self.logger, min_sample_size=10)

        for center_name, job_dfs in center_data.items():
            if job_dfs:
                # Combine all job data for this center
                combined_df = pd.concat(job_dfs, ignore_index=True)

                # Remove duplicates
                if 'job_url' in combined_df.columns:
                    combined_df = combined_df.drop_duplicates(subset=['job_url'])

                # Extract salary data
                salary_df = aggregator.extract_salary_data(combined_df)

                if not salary_df.empty:
                    # Calculate statistics
                    stats = self.stats_calculator.calculate_statistics(salary_df)
                    if stats:
                        center_stats[center_name] = stats

        return center_stats

    def generate_market_report(self, market_name: str, market_data: MarketData) -> Optional[Path]:
        """Generate CSV report for a single market.
        
        Args:
            market_name: Name of the market
            market_data: Aggregated market data
            
        Returns:
            Path to generated file or None if insufficient data
        """
        # Calculate statistics
        stats = self.stats_calculator.calculate_statistics(market_data.salary_data)
        
        if not stats:
            self.logger.warning(f"No salary data for market: {market_name}")
            return None
        
        # Create filename
        safe_market_name = market_name.replace(' ', '_').replace('/', '-')
        filename = f"{safe_market_name}_stats.csv"
        filepath = self.output_dir / filename
        
        # Prepare data for CSV
        csv_data = [
            ['Market Analysis Report'],
            ['Generated', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Job Title', self.job_title],
            ['Market', market_name],
            [],
            ['Data Collection Summary'],
            ['Total Locations', market_data.total_locations],
            ['Successful Locations', market_data.successful_locations],
            ['Total Jobs Found', market_data.total_jobs],
            ['Jobs with Salary Data', market_data.jobs_with_salary],
            ['Data Sufficiency', 'SUFFICIENT' if stats.sufficient_data else 'INSUFFICIENT'],
            [],
            ['Compensation Statistics'],
            ['Sample Size', stats.sample_size],
            [],
            ['Descriptive Statistics'],
            ['Mean', f'${stats.mean:,.2f}'],
            ['Median', f'${stats.median:,.2f}'],
            ['Mode', f'${stats.mode:,.2f}' if stats.mode else 'N/A'],
            ['Minimum', f'${stats.min_value:,.2f}'],
            ['Maximum', f'${stats.max_value:,.2f}'],
            ['Range', f'${stats.range_value:,.2f}'],
            ['Standard Deviation', f'${stats.std_dev:,.2f}'],
            ['Coefficient of Variation', f'{stats.coeff_variation:.4f}'],
            [],
            ['Percentiles'],
            ['10th Percentile (P10)', f'${stats.p10:,.2f}'],
            ['25th Percentile (P25)', f'${stats.p25:,.2f}'],
            ['50th Percentile (P50/Median)', f'${stats.p50:,.2f}'],
            ['75th Percentile (P75)', f'${stats.p75:,.2f}'],
            ['90th Percentile (P90)', f'${stats.p90:,.2f}'],
            ['Interquartile Range (IQR)', f'${stats.iqr:,.2f}'],
            [],
            ['Distribution Shape'],
            ['Skewness', f'{stats.skewness:.4f}'],
            ['Kurtosis', f'{stats.kurtosis:.4f}'],
            [],
            ['Interpretations'],
        ]
        
        # Add interpretations
        interpretations = self.stats_calculator.interpret_statistics(stats)
        for key, value in interpretations.items():
            csv_data.append([key.replace('_', ' ').title(), value])
        
        # Write to CSV
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(csv_data)
        
        self.logger.info(f"Generated market report: {filepath}")
        return filepath
    
    def generate_summary_report(self, all_markets: Dict[str, MarketData]) -> Path:
        """Generate summary report across all markets.

        Args:
            all_markets: Dictionary of all market data

        Returns:
            Path to generated summary file
        """
        filepath = self.output_dir / "summary_all_markets.csv"

        # Calculate statistics for each market
        market_stats = {}
        for market_name, market_data in all_markets.items():
            stats = self.stats_calculator.calculate_statistics(market_data.salary_data)
            if stats:
                market_stats[market_name] = stats

        # Create comparison DataFrame
        comparison_df = self.stats_calculator.calculate_market_comparison(market_stats)

        # Prepare summary data
        summary_data = []

        # Header section
        summary_data.append(['Market Analysis Summary Report'])
        summary_data.append(['Generated', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        summary_data.append(['Job Title', self.job_title])
        summary_data.append(['Total Markets', len(all_markets)])
        summary_data.append(['Markets with Sufficient Data',
                           sum(1 for m in all_markets.values() if m.has_sufficient_data)])
        summary_data.append([])

        # Overall statistics
        total_locations = sum(m.total_locations for m in all_markets.values())
        successful_locations = sum(m.successful_locations for m in all_markets.values())
        total_jobs = sum(m.total_jobs for m in all_markets.values())
        jobs_with_salary = sum(m.jobs_with_salary for m in all_markets.values())

        summary_data.append(['Overall Statistics'])
        summary_data.append(['Total Locations Searched', total_locations])
        summary_data.append(['Successful Location Searches', successful_locations])
        if total_locations > 0:
            summary_data.append(['Success Rate', f'{(successful_locations/total_locations)*100:.1f}%'])
        else:
            summary_data.append(['Success Rate', 'N/A'])
        summary_data.append(['Total Jobs Found', total_jobs])
        summary_data.append(['Jobs with Salary Data', jobs_with_salary])
        summary_data.append(['Salary Data Rate', f'{(jobs_with_salary/total_jobs)*100:.1f}%' if total_jobs > 0 else 'N/A'])
        summary_data.append([])

        # Market comparison table
        summary_data.append(['Market Comparison'])
        summary_data.append([])

        # Add comparison data if available
        if not comparison_df.empty:
            # Add headers
            headers = comparison_df.columns.tolist()
            summary_data.append(headers)

            # Add data rows
            for _, row in comparison_df.iterrows():
                row_data = []
                for col in headers:
                    val = row[col]
                    if col in ['Mean', 'Median', 'P25', 'P75', 'P90', 'IQR', 'Std Dev']:
                        row_data.append(f'${val:,.0f}')
                    elif col in ['Skewness']:
                        row_data.append(f'{val:.4f}')
                    elif col == 'Sufficient Data':
                        row_data.append('Yes' if val else 'No')
                    else:
                        row_data.append(str(val))
                summary_data.append(row_data)
        else:
            summary_data.append(['No markets with sufficient data for comparison'])

        summary_data.append([])

        # Market details
        summary_data.append(['Market Details'])
        summary_data.append(['Market', 'Locations', 'Successful', 'Jobs', 'With Salary', 'Sufficient Data'])

        for market_name, market_data in all_markets.items():
            summary_data.append([
                market_name,
                market_data.total_locations,
                market_data.successful_locations,
                market_data.total_jobs,
                market_data.jobs_with_salary,
                'Yes' if market_data.has_sufficient_data else 'No'
            ])

        summary_data.append([])

        # Center-level statistics for each market
        summary_data.append(['Center-Level Statistics by Market'])
        summary_data.append([])

        for market_name in all_markets.keys():
            center_stats = self.calculate_center_statistics(market_name)

            if center_stats:
                summary_data.append([f'Market: {market_name}'])
                summary_data.append(['Center', 'Sample Size', 'Mean', 'Median', 'P25', 'P75', 'P90', 'Std Dev'])

                for center_name, stats in sorted(center_stats.items()):
                    summary_data.append([
                        center_name,
                        stats.sample_size,
                        f'${stats.mean:,.0f}',
                        f'${stats.median:,.0f}',
                        f'${stats.p25:,.0f}',
                        f'${stats.p75:,.0f}',
                        f'${stats.p90:,.0f}',
                        f'${stats.std_dev:,.0f}'
                    ])

                summary_data.append([])

        # Write to CSV
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(summary_data)

        self.logger.info(f"Generated summary report: {filepath}")
        return filepath
    
    def generate_all_reports(self, all_markets: Dict[str, MarketData]) -> List[Path]:
        """Generate all reports for market analysis.
        
        Args:
            all_markets: Dictionary of all market data
            
        Returns:
            List of generated file paths
        """
        generated_files = []
        
        # Generate individual market reports
        for market_name, market_data in all_markets.items():
            filepath = self.generate_market_report(market_name, market_data)
            if filepath:
                generated_files.append(filepath)
        
        # Generate summary report
        summary_path = self.generate_summary_report(all_markets)
        generated_files.append(summary_path)
        
        self.logger.info(f"Generated {len(generated_files)} report files")
        
        return generated_files