"""Data aggregator for market-level analysis with role-based support.

This module aggregates job search results by market and role, comparing actual
market compensation data against configured paybands.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from jobx.market_analysis.batch_executor import LocationResult
from jobx.market_analysis.config_loader import Config, Market, Payband, PayType, Role
from jobx.market_analysis.logger import MarketAnalysisLogger
from jobx.market_analysis.statistics_calculator import StatisticsCalculator


@dataclass
class RoleMarketData:
    """Aggregated data for a specific role in a market."""
    market_name: str
    role: Role
    payband: Optional[Payband]
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
    
    @property
    def median_salary(self) -> Optional[float]:
        """Get median salary if data available."""
        if not self.salary_data.empty:
            return self.salary_data['salary'].median()
        return None
    
    @property
    def mean_salary(self) -> Optional[float]:
        """Get mean salary if data available."""
        if not self.salary_data.empty:
            return self.salary_data['salary'].mean()
        return None
    
    def get_percentile(self, percentile: int) -> Optional[float]:
        """Get salary at specific percentile.
        
        Args:
            percentile: Percentile to calculate (0-100)
            
        Returns:
            Salary at percentile or None if no data
        """
        if not self.salary_data.empty:
            return self.salary_data['salary'].quantile(percentile / 100)
        return None
    
    def is_within_payband(self, percentile: int = 50) -> Optional[bool]:
        """Check if market salary is within configured payband.
        
        Args:
            percentile: Percentile to compare (default: 50 for median)
            
        Returns:
            True if within payband, False if outside, None if no data/payband
        """
        if not self.payband or self.salary_data.empty:
            return None
        
        salary = self.get_percentile(percentile)
        if salary is None:
            return None
        
        # Convert payband to annual if needed
        payband_min = self._annualize_pay(self.payband.min, self.payband.pay_type)
        payband_max = self._annualize_pay(self.payband.max, self.payband.pay_type)
        
        return payband_min <= salary <= payband_max
    
    def _annualize_pay(self, amount: float, pay_type: PayType) -> float:
        """Convert pay amount to annual salary.
        
        Args:
            amount: Pay amount
            pay_type: Type of pay (hourly/salary)
            
        Returns:
            Annualized amount
        """
        if pay_type == PayType.HOURLY:
            return amount * 2080  # 40 hours/week * 52 weeks
        return amount  # Already annual


@dataclass
class MarketData:
    """Aggregated data for a market (backward compatibility)."""
    market_name: str
    total_locations: int
    successful_locations: int
    total_jobs: int
    jobs_with_salary: int
    salary_data: pd.DataFrame
    has_sufficient_data: bool
    role_data: Dict[str, RoleMarketData] = None
    
    @property
    def salary_count(self) -> int:
        """Number of jobs with salary data."""
        return len(self.salary_data)
    
    @classmethod
    def from_role_data(cls, market_name: str, role_data: Dict[str, RoleMarketData]) -> 'MarketData':
        """Create MarketData from role-specific data.
        
        Args:
            market_name: Name of the market
            role_data: Dictionary of role ID to RoleMarketData
            
        Returns:
            MarketData instance
        """
        # Aggregate across all roles
        total_locations = max((r.total_locations for r in role_data.values()), default=0)
        successful_locations = max((r.successful_locations for r in role_data.values()), default=0)
        total_jobs = sum(r.total_jobs for r in role_data.values())
        jobs_with_salary = sum(r.jobs_with_salary for r in role_data.values())
        
        # Combine all salary data
        salary_dfs = [r.salary_data for r in role_data.values() if not r.salary_data.empty]
        if salary_dfs:
            combined_salary_data = pd.concat(salary_dfs, ignore_index=True)
        else:
            combined_salary_data = pd.DataFrame()
        
        # Has sufficient data if any role has sufficient data
        has_sufficient_data = any(r.has_sufficient_data for r in role_data.values())
        
        return cls(
            market_name=market_name,
            total_locations=total_locations,
            successful_locations=successful_locations,
            total_jobs=total_jobs,
            jobs_with_salary=jobs_with_salary,
            salary_data=combined_salary_data,
            has_sufficient_data=has_sufficient_data,
            role_data=role_data
        )


class DataAggregator:
    """Aggregates location results by market and role."""
    
    def __init__(self, config: Config, logger: MarketAnalysisLogger, min_sample_size: int = 100):
        """Initialize data aggregator.
        
        Args:
            config: Configuration with role and market definitions
            logger: Logger instance
            min_sample_size: Minimum jobs with salary for sufficient data
        """
        self.config = config
        self.logger = logger
        self.min_sample_size = min_sample_size
        self.stats_calc = StatisticsCalculator()
    
    def extract_salary_data(self, df: pd.DataFrame, role: Optional[Role] = None) -> pd.DataFrame:
        """Extract and clean salary data from jobs dataframe.
        
        Args:
            df: Jobs dataframe
            role: Optional role for pay type specific processing
            
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
        salary_df = self._annualize_salaries(salary_df, role)
        
        # Remove outliers (using IQR method)
        salary_df = self._remove_outliers(salary_df, role)
        
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
    
    def _annualize_salaries(self, df: pd.DataFrame, role: Optional[Role] = None) -> pd.DataFrame:
        """Ensure all salaries are annualized.
        
        Args:
            df: DataFrame with salary data
            role: Optional role for pay type context
            
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
        
        # If role specified and hourly, ensure hourly rates are annualized
        if role and role.pay_type == PayType.HOURLY:
            # Ensure any remaining hourly rates are converted
            hourly_mask = df['salary'] < 500  # Likely hourly if under $500
            if hourly_mask.any():
                df.loc[hourly_mask, 'salary'] *= 2080
        
        return df
    
    def _remove_outliers(self, df: pd.DataFrame, role: Optional[Role] = None, 
                        iqr_multiplier: float = 1.5) -> pd.DataFrame:
        """Remove salary outliers using IQR method.
        
        Args:
            df: DataFrame with salary data
            role: Optional role for context-specific bounds
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
        
        # Adjust bounds based on role if provided
        if role:
            if role.pay_type == PayType.HOURLY:
                # Hourly roles typically $15-60/hour ($31k-125k/year)
                lower_bound = max(lower_bound, 31000)
                upper_bound = min(upper_bound, 125000)
            else:
                # Salary roles typically $40k-300k/year
                lower_bound = max(lower_bound, 40000)
                upper_bound = min(upper_bound, 300000)
        else:
            # Default reasonable bounds
            lower_bound = max(lower_bound, 20000)
            upper_bound = min(upper_bound, 500000)
        
        return df[(df['salary'] >= lower_bound) & (df['salary'] <= upper_bound)]
    
    def aggregate_role_market(self, market: Market, role: Role, 
                             location_results: List[LocationResult]) -> RoleMarketData:
        """Aggregate data for a specific role in a market.
        
        Args:
            market: Market configuration
            role: Role to aggregate
            location_results: List of location search results for this role
            
        Returns:
            RoleMarketData with aggregated information
        """
        # Filter results for this role
        role_results = [r for r in location_results if r.role.id == role.id]
        
        # Count locations
        total_locations = len(role_results)
        successful_locations = sum(1 for r in role_results if r.success)
        
        # Get payband for this role in this market
        payband = market.get_payband(role.id)
        
        # Combine all job dataframes
        job_dfs = [r.jobs_df for r in role_results if r.success and r.jobs_df is not None]
        
        if not job_dfs:
            # No data for this role/market
            return RoleMarketData(
                market_name=market.name,
                role=role,
                payband=payband,
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
        
        # Extract salary data with role context
        salary_df = self.extract_salary_data(combined_df, role)
        
        # Determine if we have sufficient data
        has_sufficient_data = len(salary_df) >= self.min_sample_size
        
        # Create role market data
        role_data = RoleMarketData(
            market_name=market.name,
            role=role,
            payband=payband,
            total_locations=total_locations,
            successful_locations=successful_locations,
            total_jobs=len(combined_df),
            jobs_with_salary=len(salary_df),
            salary_data=salary_df,
            has_sufficient_data=has_sufficient_data
        )
        
        # Log role market summary
        self.logger.info(
            f"Market '{market.name}' - Role '{role.name}': "
            f"{successful_locations} locations, {role_data.total_jobs} jobs, "
            f"{role_data.jobs_with_salary} with salary"
        )
        
        if has_sufficient_data and payband:
            within_band = role_data.is_within_payband()
            if within_band is not None:
                status = "within" if within_band else "outside"
                self.logger.info(
                    f"  Median salary ${role_data.median_salary:,.0f} is {status} "
                    f"payband ${payband.min:,.0f}-${payband.max:,.0f}"
                )
        
        return role_data
    
    def aggregate_market(self, market_name: str, 
                        location_results: List[LocationResult]) -> MarketData:
        """Aggregate data for a single market across all roles.
        
        Args:
            market_name: Name of the market
            location_results: List of location search results
            
        Returns:
            MarketData with aggregated information
        """
        # Find market configuration
        market = None
        for m in self.config.all_markets:
            if m.name == market_name:
                market = m
                break
        
        if not market:
            # Fallback for backward compatibility
            return self._aggregate_market_legacy(market_name, location_results)
        
        # Aggregate by role
        role_data = {}
        for role in self.config.roles:
            if market.get_payband(role.id):
                role_market_data = self.aggregate_role_market(market, role, location_results)
                role_data[role.id] = role_market_data
        
        # Create combined market data
        market_data = MarketData.from_role_data(market_name, role_data)
        
        # Log market summary
        self.logger.market_summary(
            market_name,
            market_data.successful_locations,
            market_data.total_jobs,
            market_data.jobs_with_salary,
            market_data.has_sufficient_data
        )
        
        return market_data
    
    def _aggregate_market_legacy(self, market_name: str, 
                                location_results: List[LocationResult]) -> MarketData:
        """Legacy aggregation for backward compatibility.
        
        Args:
            market_name: Name of the market
            location_results: List of location search results
            
        Returns:
            MarketData with aggregated information
        """
        # Count locations
        total_locations = len(set(r.center.code for r in location_results))
        successful_locations = len(set(r.center.code for r in location_results if r.success))
        
        # Combine all job dataframes
        job_dfs = [r.jobs_df for r in location_results if r.success and r.jobs_df is not None]
        
        if not job_dfs:
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
        
        # Remove duplicates
        if 'job_url' in combined_df.columns:
            combined_df = combined_df.drop_duplicates(subset=['job_url'])
        
        # Extract salary data
        salary_df = self.extract_salary_data(combined_df)
        
        # Determine if we have sufficient data
        has_sufficient_data = len(salary_df) >= self.min_sample_size
        
        return MarketData(
            market_name=market_name,
            total_locations=total_locations,
            successful_locations=successful_locations,
            total_jobs=len(combined_df),
            jobs_with_salary=len(salary_df),
            salary_data=salary_df,
            has_sufficient_data=has_sufficient_data
        )
    
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
    
    def get_role_comparison(self, role_id: str, 
                           aggregated_markets: Dict[str, MarketData]) -> pd.DataFrame:
        """Compare a specific role across all markets.
        
        Args:
            role_id: ID of the role to compare
            aggregated_markets: Aggregated market data
            
        Returns:
            DataFrame with role comparison across markets
        """
        comparison_data = []
        
        for market_name, market_data in aggregated_markets.items():
            if market_data.role_data and role_id in market_data.role_data:
                role_data = market_data.role_data[role_id]
                
                row = {
                    'Market': market_name,
                    'Jobs Found': role_data.total_jobs,
                    'Jobs with Salary': role_data.jobs_with_salary,
                    'Median Salary': role_data.median_salary,
                    '25th Percentile': role_data.get_percentile(25),
                    '75th Percentile': role_data.get_percentile(75),
                    'Has Sufficient Data': role_data.has_sufficient_data
                }
                
                if role_data.payband:
                    row['Payband Min'] = role_data.payband.min
                    row['Payband Max'] = role_data.payband.max
                    row['Within Payband'] = role_data.is_within_payband()
                
                comparison_data.append(row)
        
        return pd.DataFrame(comparison_data)