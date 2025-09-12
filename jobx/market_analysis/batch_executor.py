"""Batch executor for concurrent job searches with role-based support.

This module handles concurrent execution of job searches across multiple locations
and roles, with proper rate limiting and error handling.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd

from jobx import scrape_jobs
from jobx.market_analysis.config_loader import Center, Config, Location, Role
from jobx.market_analysis.logger import MarketAnalysisLogger


@dataclass
class LocationResult:
    """Result from searching a single location for a specific role."""
    center: Center
    role: Role
    success: bool
    jobs_df: Optional[pd.DataFrame] = None
    error: Optional[str] = None
    jobs_found: int = 0
    jobs_with_salary: int = 0
    market_name: str = ""
    region_name: str = ""
    
    @property
    def location(self) -> Location:
        """Get legacy Location object for backward compatibility."""
        return Location.from_center(
            self.center,
            self.market_name,
            self.region_name
        )


@dataclass
class RoleSearchTask:
    """Represents a search task for a specific role at a specific center."""
    role: Role
    center: Center
    market_name: str
    region_name: str


class BatchExecutor:
    """Executes job searches in batches with concurrency control."""
    
    def __init__(self, config: Config, logger: MarketAnalysisLogger):
        """Initialize batch executor.
        
        Args:
            config: Configuration with locations and settings
            logger: Logger instance
        """
        self.config = config
        self.logger = logger
        self.results: List[LocationResult] = []
    
    def search_location(self, task: RoleSearchTask) -> LocationResult:
        """Search jobs for a specific role at a specific location.
        
        Args:
            task: Search task containing role and location details
            
        Returns:
            LocationResult with search results or error
        """
        try:
            self.logger.debug(
                f"Searching {task.center.name} ({task.center.zip_code}) "
                f"for role: {task.role.name}"
            )
            
            # Search for all search terms and combine results
            all_dfs = []
            for search_term in task.role.search_terms:
                try:
                    df_term = scrape_jobs(
                        site_name=["linkedin", "indeed"],
                        search_term=search_term,
                        location=task.center.search_location,
                        distance=self.config.search.radius_miles,
                        results_wanted=self.config.search.results_per_location,
                        is_remote=True,  # Include all positions
                        country_indeed="usa",
                        verbose=0  # Suppress jobx output
                    )
                    if not df_term.empty:
                        # Add search term used for this result
                        df_term['search_term_used'] = search_term
                        all_dfs.append(df_term)
                except Exception as e:
                    self.logger.error(f"Error searching for '{search_term}': {str(e)}")
                    continue
            
            # Combine all results and remove duplicates based on job URL
            if all_dfs:
                df = pd.concat(all_dfs, ignore_index=True)
                # Remove duplicates based on job_url, keeping first occurrence
                df = df.drop_duplicates(subset=['job_url'], keep='first')
            else:
                df = pd.DataFrame()
            
            if df.empty:
                return LocationResult(
                    center=task.center,
                    role=task.role,
                    success=False,
                    error="No jobs found",
                    market_name=task.market_name,
                    region_name=task.region_name
                )
            
            # Count jobs with salary data
            salary_mask = df['min_amount'].notna() | df['max_amount'].notna()
            jobs_with_salary = salary_mask.sum()
            
            # Add location and role metadata to dataframe
            df['search_location'] = task.center.name
            df['search_zip'] = task.center.zip_code
            df['search_code'] = task.center.code
            df['market'] = task.market_name
            df['region'] = task.region_name
            df['role_id'] = task.role.id
            df['role_name'] = task.role.name
            df['role_pay_type'] = task.role.pay_type.value
            
            self.logger.success(
                task.center.name,
                task.center.zip_code,
                len(df),
                jobs_with_salary
            )
            
            return LocationResult(
                center=task.center,
                role=task.role,
                success=True,
                jobs_df=df,
                jobs_found=len(df),
                jobs_with_salary=jobs_with_salary,
                market_name=task.market_name,
                region_name=task.region_name
            )
            
        except Exception as e:
            error_msg = str(e)
            self.logger.failure(task.center.name, task.center.zip_code, error_msg)
            return LocationResult(
                center=task.center,
                role=task.role,
                success=False,
                error=error_msg,
                market_name=task.market_name,
                region_name=task.region_name
            )
    
    def execute_batch(self, tasks: List[RoleSearchTask]) -> List[LocationResult]:
        """Execute a batch of searches concurrently.
        
        Args:
            tasks: List of search tasks to execute
            
        Returns:
            List of results from all searches
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=self.config.search.batch_size) as executor:
            future_to_task = {
                executor.submit(self.search_location, task): task
                for task in tasks
            }
            
            for future in as_completed(future_to_task):
                result = future.result()
                results.append(result)
                self.results.append(result)
                
                # Small delay between completions to avoid rate limiting
                time.sleep(0.5)
        
        return results
    
    def execute_all(self) -> Dict[str, List[LocationResult]]:
        """Execute all searches for all roles and locations.
        
        Returns:
            Dictionary mapping market names to their results
        """
        # Build list of all search tasks
        all_tasks = []
        
        for region in self.config.regions:
            for market in region.markets:
                for center in market.centers:
                    for role in self.config.roles:
                        # Check if center has payband for this role
                        center_payband = center.get_payband(role.id) if hasattr(center, 'get_payband') else None
                        # Fall back to market payband if center doesn't have one
                        market_payband = market.get_payband(role.id)
                        
                        # Only search if either center or market has payband for this role
                        if center_payband or market_payband:
                            task = RoleSearchTask(
                                role=role,
                                center=center,
                                market_name=market.name,
                                region_name=region.name
                            )
                            all_tasks.append(task)
        
        self.logger.info(f"Total search tasks: {len(all_tasks)}")
        self.logger.info(
            f"Centers: {len(self.config.all_centers)}, "
            f"Roles: {len(self.config.roles)}"
        )
        
        # Execute in batches
        batch_size = self.config.search.batch_size
        for i in range(0, len(all_tasks), batch_size):
            batch = all_tasks[i:i + batch_size]
            self.logger.info(
                f"Executing batch {i // batch_size + 1} of "
                f"{(len(all_tasks) + batch_size - 1) // batch_size}"
            )
            self.execute_batch(batch)
            
            # Delay between batches
            if i + batch_size < len(all_tasks):
                time.sleep(2)
        
        # Group results by market
        market_results: Dict[str, List[LocationResult]] = {}
        for result in self.results:
            if result.market_name not in market_results:
                market_results[result.market_name] = []
            market_results[result.market_name].append(result)
        
        return market_results
    
    def execute_for_role(self, role_id: str) -> Dict[str, List[LocationResult]]:
        """Execute searches for a specific role across all locations.
        
        Args:
            role_id: ID of the role to search for
            
        Returns:
            Dictionary mapping market names to their results
        """
        role = self.config.get_role(role_id)
        if not role:
            raise ValueError(f"Role not found: {role_id}")
        
        # Build list of search tasks for this role
        tasks = []
        
        for region in self.config.regions:
            for market in region.markets:
                # Only search if market has payband for this role
                if market.get_payband(role_id):
                    for center in market.centers:
                        task = RoleSearchTask(
                            role=role,
                            center=center,
                            market_name=market.name,
                            region_name=region.name
                        )
                        tasks.append(task)
        
        self.logger.info(f"Searching for role '{role.name}' at {len(tasks)} centers")
        
        # Execute in batches
        batch_size = self.config.search.batch_size
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            self.execute_batch(batch)
            
            # Delay between batches
            if i + batch_size < len(tasks):
                time.sleep(2)
        
        # Group results by market
        market_results: Dict[str, List[LocationResult]] = {}
        for result in self.results:
            if result.role.id == role_id:
                if result.market_name not in market_results:
                    market_results[result.market_name] = []
                market_results[result.market_name].append(result)
        
        return market_results
    
    def get_summary_stats(self) -> Dict[str, int]:
        """Get summary statistics from all executed searches.
        
        Returns:
            Dictionary with summary statistics
        """
        total_tasks = len(self.results)
        successful_tasks = sum(1 for r in self.results if r.success)
        total_jobs = sum(r.jobs_found for r in self.results)
        jobs_with_salary = sum(r.jobs_with_salary for r in self.results)
        
        # Count unique locations and roles
        unique_centers = len(set(r.center.code for r in self.results))
        unique_roles = len(set(r.role.id for r in self.results))
        
        return {
            'total_tasks': total_tasks,
            'successful_tasks': successful_tasks,
            'total_locations': unique_centers,
            'successful_locations': unique_centers,  # For backward compat
            'total_roles': unique_roles,
            'total_jobs': total_jobs,
            'jobs_with_salary': jobs_with_salary,
            'success_rate': (successful_tasks / total_tasks * 100) if total_tasks > 0 else 0
        }
    
    def get_role_stats(self, role_id: str) -> Dict[str, int]:
        """Get statistics for a specific role.
        
        Args:
            role_id: ID of the role
            
        Returns:
            Dictionary with role-specific statistics
        """
        role_results = [r for r in self.results if r.role.id == role_id]
        
        if not role_results:
            return {
                'total_tasks': 0,
                'successful_tasks': 0,
                'total_jobs': 0,
                'jobs_with_salary': 0,
                'success_rate': 0
            }
        
        successful = sum(1 for r in role_results if r.success)
        total = len(role_results)
        
        return {
            'total_tasks': total,
            'successful_tasks': successful,
            'total_jobs': sum(r.jobs_found for r in role_results),
            'jobs_with_salary': sum(r.jobs_with_salary for r in role_results),
            'success_rate': (successful / total * 100) if total > 0 else 0
        }


# Backward compatibility function
def search_location_legacy(
    config: Config,
    location: Location,
    logger: MarketAnalysisLogger
) -> LocationResult:
    """Legacy function for searching a single location.
    
    Deprecated: Use BatchExecutor.search_location() instead.
    
    Args:
        config: Configuration object
        location: Location to search
        logger: Logger instance
        
    Returns:
        LocationResult
    """
    import warnings
    warnings.warn(
        "search_location_legacy is deprecated. Use BatchExecutor.search_location() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    # Create executor and search with first role (backward compat)
    executor = BatchExecutor(config, logger)
    
    # Find matching center
    for center in config.all_centers:
        if center.zip_code == location.zip_code:
            # Use first role for backward compatibility
            if config.roles:
                task = RoleSearchTask(
                    role=config.roles[0],
                    center=center,
                    market_name=location.market,
                    region_name=location.region
                )
                return executor.search_location(task)
    
    # No matching center found
    return LocationResult(
        center=Center(
            code="unknown",
            name=location.name,
            address_1=location.address,
            city="",
            state="",
            zip_code=location.zip_code
        ),
        role=config.roles[0] if config.roles else Role(
            id="unknown",
            name="Unknown",
            pay_type="salary",
            default_unit="USD/year"
        ),
        success=False,
        error="Location not found in configuration",
        market_name=location.market,
        region_name=location.region
    )