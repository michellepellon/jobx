"""Data aggregator for market-level analysis."""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
import numpy as np

from jobx.market_analysis.batch_executor import LocationResult
from jobx.market_analysis.logger import MarketAnalysisLogger


@dataclass
class MarketData:
    """Aggregated data for a market."""
    market_name: str
    total_locations: int
    successful_locations: int
    total_jobs: int
    jobs_with_salary: int
    salary_data: pd.DataFrame
    has_sufficient_data: bool
    
    @property
    def salary_count(self) -> int:
        """Number of jobs with salary data."""
        return len(self.salary_data)


class DataAggregator:
    """Aggregates location results by market."""
    
    def __init__(self, logger: MarketAnalysisLogger, min_sample_size: int = 100):
        """Initialize data aggregator.
        
        Args:
            logger: Logger instance
            min_sample_size: Minimum jobs with salary for sufficient data
        """
        self.logger = logger
        self.min_sample_size = min_sample_size
    
    def extract_salary_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract and clean salary data from jobs dataframe.
        
        Args:
            df: Jobs dataframe
            
        Returns:
            DataFrame with clean salary data
        """
        # Filter for jobs with salary data
        salary_mask = df['min_amount'].notna() | df['max_amount'].notna()
        salary_df = df[salary_mask].copy()
        
        if salary_df.empty:
            return salary_df
        
        # Calculate average salary for each job (midpoint of range)
        salary_df['salary'] = salary_df.apply(
            lambda row: self._calculate_salary(row), axis=1
        )
        
        # Remove invalid salaries
        salary_df = salary_df[salary_df['salary'] > 0]
        
        # Ensure all salaries are annualized
        salary_df = self._annualize_salaries(salary_df)
        
        # Remove outliers (using IQR method)
        salary_df = self._remove_outliers(salary_df)
        
        return salary_df
    
    def _calculate_salary(self, row) -> float:
        """Calculate salary from min/max amounts.
        
        Args:
            row: DataFrame row with salary data
            
        Returns:
            Calculated salary value
        """
        min_amt = row.get('min_amount', 0) or 0
        max_amt = row.get('max_amount', 0) or 0
        
        if min_amt > 0 and max_amt > 0:
            return (min_amt + max_amt) / 2
        elif min_amt > 0:
            return min_amt
        elif max_amt > 0:
            return max_amt
        else:
            return 0
    
    def _annualize_salaries(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure all salaries are annualized.
        
        Args:
            df: DataFrame with salary data
            
        Returns:
            DataFrame with annualized salaries
        """
        df = df.copy()
        
        # Define conversion factors
        conversions = {
            'hourly': 2080,  # 40 hours/week * 52 weeks
            'weekly': 52,
            'monthly': 12,
            'yearly': 1
        }
        
        # Apply conversions based on interval
        for interval, factor in conversions.items():
            mask = df['interval'] == interval
            if mask.any():
                df.loc[mask, 'salary'] *= factor
        
        return df
    
    def _remove_outliers(self, df: pd.DataFrame, iqr_multiplier: float = 1.5) -> pd.DataFrame:
        """Remove salary outliers using IQR method.
        
        Args:
            df: DataFrame with salary data
            iqr_multiplier: Multiplier for IQR to determine outliers
            
        Returns:
            DataFrame with outliers removed
        """
        if len(df) < 4:  # Need at least 4 points for IQR
            return df
        
        q1 = df['salary'].quantile(0.25)
        q3 = df['salary'].quantile(0.75)
        iqr = q3 - q1
        
        lower_bound = q1 - (iqr_multiplier * iqr)
        upper_bound = q3 + (iqr_multiplier * iqr)
        
        # Keep reasonable minimums (e.g., $20k/year)
        lower_bound = max(lower_bound, 20000)
        
        # Keep reasonable maximums (e.g., $500k/year for most roles)
        upper_bound = min(upper_bound, 500000)
        
        return df[(df['salary'] >= lower_bound) & (df['salary'] <= upper_bound)]
    
    def aggregate_market(self, market_name: str, 
                        location_results: List[LocationResult]) -> MarketData:
        """Aggregate data for a single market.
        
        Args:
            market_name: Name of the market
            location_results: List of location search results
            
        Returns:
            MarketData with aggregated information
        """
        # Count locations
        total_locations = len(location_results)
        successful_locations = sum(1 for r in location_results if r.success)
        
        # Combine all job dataframes
        job_dfs = [r.jobs_df for r in location_results if r.success and r.jobs_df is not None]
        
        if not job_dfs:
            # No data for this market
            return MarketData(
                market_name=market_name,
                total_locations=total_locations,
                successful_locations=successful_locations,
                total_jobs=0,
                jobs_with_salary=0,
                salary_data=pd.DataFrame(),
                has_sufficient_data=False
            )
        
        # Concatenate all job data
        combined_df = pd.concat(job_dfs, ignore_index=True)
        
        # Remove duplicates based on job URL
        if 'job_url' in combined_df.columns:
            combined_df = combined_df.drop_duplicates(subset=['job_url'])
        
        # Extract salary data
        salary_df = self.extract_salary_data(combined_df)
        
        # Determine if we have sufficient data
        has_sufficient_data = len(salary_df) >= self.min_sample_size
        
        # Create market data
        market_data = MarketData(
            market_name=market_name,
            total_locations=total_locations,
            successful_locations=successful_locations,
            total_jobs=len(combined_df),
            jobs_with_salary=len(salary_df),
            salary_data=salary_df,
            has_sufficient_data=has_sufficient_data
        )
        
        # Log market summary
        self.logger.market_summary(
            market_name,
            successful_locations,
            market_data.total_jobs,
            market_data.jobs_with_salary,
            has_sufficient_data
        )
        
        return market_data
    
    def aggregate_all_markets(self, 
                            market_results: Dict[str, List[LocationResult]]) -> Dict[str, MarketData]:
        """Aggregate data for all markets.
        
        Args:
            market_results: Dictionary mapping market names to location results
            
        Returns:
            Dictionary mapping market names to MarketData
        """
        aggregated_markets = {}
        
        for market_name, location_results in market_results.items():
            market_data = self.aggregate_market(market_name, location_results)
            aggregated_markets[market_name] = market_data
        
        return aggregated_markets