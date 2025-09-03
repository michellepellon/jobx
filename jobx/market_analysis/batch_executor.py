"""Batch executor for concurrent job searches."""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pandas as pd

from jobx import scrape_jobs
from jobx.market_analysis.config_loader import Config, Location
from jobx.market_analysis.logger import MarketAnalysisLogger


@dataclass
class LocationResult:
    """Result from searching a single location."""
    location: Location
    success: bool
    jobs_df: Optional[pd.DataFrame] = None
    error: Optional[str] = None
    jobs_found: int = 0
    jobs_with_salary: int = 0


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
    
    def search_location(self, location: Location) -> LocationResult:
        """Search jobs for a single location.
        
        Args:
            location: Location to search
            
        Returns:
            LocationResult with search results or error
        """
        try:
            self.logger.debug(f"Searching {location.name} ({location.zip_code})")
            
            # Use jobx scrape_jobs function
            df = scrape_jobs(
                site_name=["linkedin", "indeed"],
                search_term=self.config.job_title,
                location=location.zip_code,
                distance=self.config.search_radius,
                results_wanted=self.config.results_per_location,
                is_remote=True,  # Include all positions
                country_indeed="usa",
                verbose=0  # Suppress jobx output
            )
            
            if df.empty:
                return LocationResult(
                    location=location,
                    success=False,
                    error="No jobs found"
                )
            
            # Count jobs with salary data
            salary_mask = df['min_amount'].notna() | df['max_amount'].notna()
            jobs_with_salary = salary_mask.sum()
            
            # Add location metadata to dataframe
            df['search_location'] = location.name
            df['search_zip'] = location.zip_code
            df['market'] = location.market
            df['region'] = location.region
            
            self.logger.success(
                location.name, 
                location.zip_code, 
                len(df), 
                jobs_with_salary
            )
            
            return LocationResult(
                location=location,
                success=True,
                jobs_df=df,
                jobs_found=len(df),
                jobs_with_salary=jobs_with_salary
            )
            
        except Exception as e:
            error_msg = str(e)
            self.logger.failure(location.name, location.zip_code, error_msg)
            return LocationResult(
                location=location,
                success=False,
                error=error_msg
            )
    
    def execute_batch(self, locations: List[Location]) -> List[LocationResult]:
        """Execute searches for a batch of locations concurrently.
        
        Args:
            locations: List of locations to search
            
        Returns:
            List of LocationResults
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=self.config.batch_size) as executor:
            # Submit all tasks
            future_to_location = {
                executor.submit(self.search_location, loc): loc 
                for loc in locations
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_location):
                location = future_to_location[future]
                try:
                    result = future.result(timeout=300)  # 5 minute timeout per location
                    results.append(result)
                except Exception as e:
                    # Handle timeout or other executor errors
                    results.append(LocationResult(
                        location=location,
                        success=False,
                        error=f"Executor error: {str(e)}"
                    ))
                    self.logger.failure(location.name, location.zip_code, f"Executor error: {str(e)}")
        
        return results
    
    def execute_all(self) -> Dict[str, List[LocationResult]]:
        """Execute searches for all locations in configuration.
        
        Returns:
            Dictionary mapping market names to their location results
        """
        all_locations = self.config.all_locations
        total_locations = len(all_locations)
        
        # Calculate number of batches
        batch_size = self.config.batch_size
        total_batches = (total_locations + batch_size - 1) // batch_size
        
        self.logger.info(f"Starting search for {total_locations} locations in {total_batches} batches")
        
        # Process locations in batches
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, total_locations)
            batch_locations = all_locations[start_idx:end_idx]
            
            self.logger.batch_start(batch_num + 1, total_batches, len(batch_locations))
            
            # Execute batch
            batch_results = self.execute_batch(batch_locations)
            self.results.extend(batch_results)
            
            # Log batch completion
            successful = sum(1 for r in batch_results if r.success)
            self.logger.batch_complete(
                batch_num + 1, 
                total_batches, 
                successful, 
                len(batch_locations)
            )
            
            # Add delay between batches to avoid rate limiting
            if batch_num < total_batches - 1:
                time.sleep(5)  # 5 second delay between batches
        
        # Organize results by market
        market_results: Dict[str, List[LocationResult]] = {}
        for result in self.results:
            market = result.location.market
            if market not in market_results:
                market_results[market] = []
            market_results[market].append(result)
        
        return market_results
    
    def get_summary_stats(self) -> Dict[str, int]:
        """Get summary statistics for execution.
        
        Returns:
            Dictionary with summary statistics
        """
        successful = sum(1 for r in self.results if r.success)
        total_jobs = sum(r.jobs_found for r in self.results if r.success)
        jobs_with_salary = sum(r.jobs_with_salary for r in self.results if r.success)
        
        return {
            'total_locations': len(self.results),
            'successful_locations': successful,
            'failed_locations': len(self.results) - successful,
            'total_jobs': total_jobs,
            'jobs_with_salary': jobs_with_salary
        }