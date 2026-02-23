"""Batch executor for concurrent job searches with role-based support.

This module handles concurrent execution of job searches across multiple locations
and roles, with proper rate limiting and error handling.
"""

import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd

from jobx import scrape_jobs
from jobx.market_analysis.config_loader import Center, Config, Location, Role
from jobx.market_analysis.logger import MarketAnalysisLogger
from jobx.market_analysis.anti_detection_utils import (
    SmartScheduler, SearchMonitor, SafetyManager
)
from jobx.market_analysis.location_filter import (
    LocationFilter,
    filter_jobs_by_location
)


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
    
    def __init__(self, config: Config, logger: MarketAnalysisLogger,
                 output_dir: str = ".", enable_safety: bool = True,
                 max_retries: Optional[int] = None):
        """Initialize batch executor with anti-detection features.

        Args:
            config: Configuration with locations and settings
            logger: Logger instance
            output_dir: Output directory for monitoring files
            enable_safety: Enable anti-detection safety features
            max_retries: Max retry attempts per task (default: from config)
        """
        self.config = config
        self.logger = logger
        self.output_dir = output_dir
        self.enable_safety = enable_safety
        self.max_retries = max_retries if max_retries is not None else config.search.max_retries

        # Initialize anti-detection components
        if self.enable_safety:
            self.scheduler = SmartScheduler()
            self.monitor = SearchMonitor(output_dir)
            self.safety = SafetyManager(output_dir)
        else:
            self.scheduler = None
            self.monitor = None
            self.safety = None
        self.results: List[LocationResult] = []
        self._shutdown_event = threading.Event()
        self.shutdown_requested = False
    
    def search_location(self, task: RoleSearchTask) -> LocationResult:
        """Search jobs for a specific role at a specific location.
        
        Args:
            task: Search task containing role and location details
            
        Returns:
            LocationResult with search results or error
        """
        # Check if center already completed (when using safety features)
        if self.safety and self.safety.is_center_complete(task.center.code):
            self.logger.info(f"Skipping {task.center.name} - already completed")
            return LocationResult(
                center=task.center,
                role=task.role,
                success=True,
                jobs_df=pd.DataFrame(),
                jobs_found=0,
                jobs_with_salary=0,
                market_name=task.market_name,
                region_name=task.region_name
            )
        
        # Check if we should pause based on failure patterns
        if self.monitor:
            should_pause, reason = self.monitor.should_pause()
            if should_pause:
                self.logger.warning(f"Pausing searches: {reason}")
                # Wait with smart scheduling
                if self.scheduler:
                    delay = self.scheduler.get_human_like_delay(60)
                    self.logger.info(f"Waiting {delay:.0f} seconds before resuming...")
                    time.sleep(delay)
        
        try:
            self.logger.debug(
                f"Searching {task.center.name} ({task.center.zip_code}) "
                f"for role: {task.role.name}"
            )
            
            # Use smart scheduling delay before search
            if self.scheduler:
                delay = self.scheduler.get_human_like_delay()
                time.sleep(delay)
            
            # Randomly select search terms to use for this location
            min_terms = self.config.search.min_search_terms
            max_terms = self.config.search.max_search_terms
            if len(task.role.search_terms) >= min_terms:
                num_terms = random.randint(min_terms, min(max_terms, len(task.role.search_terms)))
                selected_terms = random.sample(task.role.search_terms, num_terms)
            else:
                # Use all available search terms if fewer than min_search_terms
                selected_terms = task.role.search_terms
                num_terms = len(selected_terms)
            
            self.logger.info(
                f"Using {num_terms} search terms for {task.center.name}: {', '.join(selected_terms[:2])}..."
            )
            
            # Search for selected search terms and combine results
            all_dfs = []
            for i, search_term in enumerate(selected_terms):
                try:
                    # Add random delay between searches to avoid rate limiting
                    if i > 0:
                        delay = random.uniform(
                            self.config.search.inter_search_delay_min,
                            self.config.search.inter_search_delay_max,
                        )
                        time.sleep(delay)
                    
                    df_term = scrape_jobs(
                        site_name=self.config.search.site_names,
                        search_term=search_term,
                        location=task.center.search_location,
                        distance=self.config.search.radius_miles,
                        results_wanted=self.config.search.results_per_location,
                        is_remote=False,  # Only include jobs within the specified radius
                        country_indeed=self.config.search.country_indeed,
                        linkedin_fetch_description=True,  # CRITICAL: Fetch full job details from LinkedIn
                        verbose=0  # Suppress jobx output
                    )
                    if not df_term.empty:
                        # Add search term used for this result
                        df_term['search_term_used'] = search_term
                        all_dfs.append(df_term)
                except Exception as e:
                    import traceback
                    self.logger.error(f"Error searching for '{search_term}': {str(e)}")
                    self.logger.error(f"Traceback: {traceback.format_exc()}")
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

            # Apply title keyword filtering if configured for this role
            if task.role.excluded_title_keywords:
                original_title_count = len(df)

                title_mask = ~df['title'].str.lower().str.contains(
                    '|'.join(task.role.excluded_title_keywords),
                    case=False,
                    na=False,
                    regex=True,
                )
                df = df[title_mask].copy()

                excluded_count = original_title_count - len(df)
                if excluded_count > 0:
                    self.logger.info(
                        f"Title filtering for {task.role.name} at {task.center.name}: "
                        f"excluded {excluded_count} jobs with unwanted titles "
                        f"({excluded_count/original_title_count*100:.1f}% filtered)"
                    )

            # Apply location filtering to remove remote/distant jobs
            original_count = len(df)
            if len(df) > 0:
                location_filter = LocationFilter(
                    center_city=task.center.city,
                    center_state=task.center.state,
                    center_zip=task.center.zip_code,
                    radius_miles=self.config.search.radius_miles
                )
                df_filtered, df_excluded, filter_stats = filter_jobs_by_location(
                    df, location_filter
                )
                
                # Log filtering statistics
                self.logger.debug(f"Location filtering for {task.center.name}:")
                self.logger.debug(f"  - Original jobs: {original_count}")
                self.logger.debug(f"  - Local jobs: {len(df_filtered)} ({filter_stats['local_percentage']:.1f}%)")
                self.logger.debug(f"  - Excluded (remote/distant): {len(df_excluded)} ({filter_stats['excluded_percentage']:.1f}%)")
                
                # Use filtered DataFrame for all subsequent operations
                df = df_filtered
            
            # Count jobs with salary data (after filtering)
            salary_mask = df['min_amount'].notna() | df['max_amount'].notna()
            jobs_with_salary = salary_mask.sum()
            
            # Debug: Log salary data stats (after filtering)
            self.logger.debug(f"Salary data analysis for {task.center.name} (after location filtering):")
            self.logger.debug(f"  - Total jobs: {len(df)}")
            self.logger.debug(f"  - Jobs with min_amount: {df['min_amount'].notna().sum()}")
            self.logger.debug(f"  - Jobs with max_amount: {df['max_amount'].notna().sum()}")
            self.logger.debug(f"  - Jobs with any salary: {jobs_with_salary}")
            if len(df) > 0:
                self.logger.debug(f"  - Salary coverage: {jobs_with_salary/len(df)*100:.1f}%")
            
            # Add location and role metadata to dataframe
            df['search_location'] = task.center.name
            df['search_zip'] = task.center.zip_code
            df['search_code'] = task.center.code
            df['market'] = task.market_name
            df['region'] = task.region_name
            df['role_id'] = task.role.id
            df['role_name'] = task.role.name
            df['role_pay_type'] = task.role.pay_type.value
            
            # Save raw data for debugging (if output_dir is set)
            if self.output_dir:
                raw_file = os.path.join(self.output_dir, f"raw_jobs_{task.center.code}_{task.role.id}.csv")
                df.to_csv(raw_file, index=False)
                self.logger.debug(f"Saved raw job data to {raw_file}")
            
            self.logger.success(
                task.center.name,
                task.center.zip_code,
                len(df),
                jobs_with_salary
            )
            
            # Record success in monitor
            if self.monitor:
                self.monitor.record_search(
                    f"{task.center.name} ({task.center.zip_code})",
                    True,
                    len(df),
                    None
                )
            
            # Mark center as complete
            if self.safety:
                self.safety.mark_center_complete(task.center.code)
            
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
            
            # Record failure in monitor
            if self.monitor:
                self.monitor.record_search(
                    f"{task.center.name} ({task.center.zip_code})",
                    False,
                    0,
                    error_msg
                )
            
            return LocationResult(
                center=task.center,
                role=task.role,
                success=False,
                error=error_msg,
                market_name=task.market_name,
                region_name=task.region_name
            )
    
    def _retry_search(self, task: RoleSearchTask,
                      base_backoff: Optional[float] = None) -> LocationResult:
        """Search with automatic retries and exponential backoff.

        Does NOT retry "No jobs found" errors (data condition, not transient).
        """
        if base_backoff is None:
            base_backoff = self.config.search.retry_backoff_base
        last_result: Optional[LocationResult] = None
        for attempt in range(1, self.max_retries + 1):
            result = self.search_location(task)
            last_result = result

            if result.success:
                return result

            # "No jobs found" is not a transient failure — don't retry
            if result.error and "No jobs found" in result.error:
                return result

            if attempt < self.max_retries:
                delay = base_backoff * (2 ** (attempt - 1)) + random.uniform(0, 10)
                self.logger.warning(
                    f"Attempt {attempt}/{self.max_retries} failed for "
                    f"{task.center.code}:{task.role.id} — "
                    f"retrying in {delay:.0f}s: {result.error}"
                )
                time.sleep(delay)

        self.logger.error(
            f"All {self.max_retries} attempts exhausted for "
            f"{task.center.code}:{task.role.id}: {last_result.error}"
        )
        return last_result

    def _checkpoint_result(self, task: RoleSearchTask, result: LocationResult):
        """Persist a task result to the checkpoint file."""
        if not self.safety:
            return

        if result.success:
            csv_file = os.path.join(
                self.output_dir,
                f"raw_jobs_{task.center.code}_{task.role.id}.csv",
            )
            self.safety.mark_task_complete(
                task.center.code, task.role.id,
                result.jobs_found, result.jobs_with_salary, csv_file,
            )
        else:
            self.safety.mark_task_failed(
                task.center.code, task.role.id,
                result.error or "Unknown error", self.max_retries,
            )

    def request_shutdown(self):
        """Request a graceful shutdown. In-flight tasks finish, no new batches start."""
        self._shutdown_event.set()
        self.shutdown_requested = True

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
                executor.submit(self._retry_search, task): task
                for task in tasks
            }

            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                except Exception as e:
                    result = LocationResult(
                        center=task.center,
                        role=task.role,
                        success=False,
                        error=f"Uncaught exception: {e}",
                        market_name=task.market_name,
                        region_name=task.region_name,
                    )
                results.append(result)
                self.results.append(result)
                self._checkpoint_result(task, result)

                # Small delay between completions to avoid rate limiting
                time.sleep(self.config.search.delay_between_completions)

        return results
    
    def _build_all_tasks(self) -> List[RoleSearchTask]:
        """Build the full list of search tasks from config.

        Randomizes ordering when safety features are enabled.
        """
        all_tasks: List[RoleSearchTask] = []

        regions = list(self.config.regions)
        if self.safety:
            random.shuffle(regions)
            self.logger.info("Randomized region order for anti-detection")

        for region in regions:
            markets = list(region.markets)
            if self.safety:
                random.shuffle(markets)

            for market in markets:
                if self.safety:
                    centers = self.safety.get_randomized_centers(market.centers)
                else:
                    centers = market.centers

                for center in centers:
                    roles = list(self.config.roles)
                    if self.safety:
                        random.shuffle(roles)

                    for role in roles:
                        center_payband = center.get_payband(role.id) if hasattr(center, 'get_payband') else None
                        market_payband = market.get_payband(role.id)

                        if center_payband or market_payband:
                            task = RoleSearchTask(
                                role=role,
                                center=center,
                                market_name=market.name,
                                region_name=region.name,
                            )
                            all_tasks.append(task)

        return all_tasks

    def _reload_completed_tasks(self, all_tasks: List[RoleSearchTask]) -> List[LocationResult]:
        """Reload results from a previous checkpoint's CSVs.

        Returns LocationResult objects for tasks that completed previously.
        Tasks whose CSV is missing are silently skipped (they'll re-run).
        """
        reloaded: List[LocationResult] = []
        if not self.safety:
            return reloaded

        for task in all_tasks:
            csv_path = self.safety.get_completed_task_csv(task.center.code, task.role.id)
            if csv_path is None:
                continue

            full_path = os.path.join(self.output_dir, os.path.basename(csv_path))
            if not os.path.exists(full_path):
                self.logger.warning(
                    f"CSV missing for {task.center.code}:{task.role.id} "
                    f"({full_path}) — task will re-run"
                )
                # Remove stale entry so the task is re-executed
                key = self.safety._task_key(task.center.code, task.role.id)
                self.safety.progress["completed_tasks"].pop(key, None)
                continue

            try:
                df = pd.read_csv(full_path)
                salary_mask = df['min_amount'].notna() | df['max_amount'].notna()
                reloaded.append(LocationResult(
                    center=task.center,
                    role=task.role,
                    success=True,
                    jobs_df=df,
                    jobs_found=len(df),
                    jobs_with_salary=int(salary_mask.sum()),
                    market_name=task.market_name,
                    region_name=task.region_name,
                ))
            except Exception as e:
                self.logger.warning(
                    f"Failed to reload CSV for {task.center.code}:{task.role.id}: {e}"
                )

        return reloaded

    def execute_all(self, resume: bool = False) -> Dict[str, List[LocationResult]]:
        """Execute all searches for all roles and locations.

        Args:
            resume: If True, reload completed tasks from checkpoint and skip them.

        Returns:
            Dictionary mapping market names to their results
        """
        # Check if good time to search (when using safety features)
        if self.scheduler:
            self.scheduler.wait_for_good_time(self.logger)

        all_tasks = self._build_all_tasks()

        if self.safety:
            self.safety.set_total_tasks(len(all_tasks))

        # Resume: reload previous results and filter out done tasks
        if resume and self.safety:
            reloaded = self._reload_completed_tasks(all_tasks)
            if reloaded:
                self.results.extend(reloaded)
                self.logger.info(f"Resumed {len(reloaded)} tasks from checkpoint")

            remaining_tasks = [
                t for t in all_tasks
                if not self.safety.is_task_done(t.center.code, t.role.id)
            ]
            self.logger.info(
                f"Total tasks: {len(all_tasks)}, "
                f"already done: {len(all_tasks) - len(remaining_tasks)}, "
                f"remaining: {len(remaining_tasks)}"
            )
            all_tasks = remaining_tasks

            if not all_tasks:
                self.logger.info("All tasks already completed — nothing to do")
        else:
            self.logger.info(f"Total search tasks: {len(all_tasks)}")
            self.logger.info(
                f"Centers: {len(self.config.all_centers)}, "
                f"Roles: {len(self.config.roles)}"
            )

        # Execute in batches (with shutdown support)
        batch_size = self.config.search.batch_size
        for i in range(0, len(all_tasks), batch_size):
            if self._shutdown_event.is_set():
                self.logger.warning("Shutdown requested — stopping after current batch")
                break

            batch = all_tasks[i:i + batch_size]
            self.logger.info(
                f"Executing batch {i // batch_size + 1} of "
                f"{(len(all_tasks) + batch_size - 1) // batch_size}"
            )
            self.execute_batch(batch)

            # Delay between batches
            if i + batch_size < len(all_tasks):
                time.sleep(self.config.search.delay_between_batches)

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
                time.sleep(self.config.search.delay_between_batches)

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