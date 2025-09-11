"""Report generator for market analysis results."""

import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd

from jobx.market_analysis.data_aggregator import MarketData
from jobx.market_analysis.statistics_calculator import StatisticsCalculator, CompensationStatistics
from jobx.market_analysis.logger import MarketAnalysisLogger


class ReportGenerator:
    """Generates CSV reports for market analysis."""
    
    def __init__(self, output_dir: Path, job_title: str, logger: MarketAnalysisLogger):
        """Initialize report generator.
        
        Args:
            output_dir: Directory for output files
            job_title: Job title being analyzed
            logger: Logger instance
        """
        self.output_dir = output_dir
        self.job_title = job_title
        self.logger = logger
        self.stats_calculator = StatisticsCalculator()
        
        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
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