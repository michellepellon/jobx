"""Logging configuration for market analysis tool."""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


class MarketAnalysisLogger:
    """Logger for market analysis operations."""
    
    def __init__(self, log_file: Optional[str] = None, verbose: bool = False):
        """Initialize logger.
        
        Args:
            log_file: Path to log file (if None, creates in output directory)
            verbose: Whether to show detailed console output
        """
        self.logger = logging.getLogger("jobx.market_analysis")
        self.logger.setLevel(logging.DEBUG)
        
        # Remove any existing handlers
        self.logger.handlers = []
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_level = logging.DEBUG if verbose else logging.INFO
        console_handler.setLevel(console_level)
        console_format = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)
        
        # File handler (if log file specified)
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter(
                '%(asctime)s | %(levelname)-7s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_format)
            self.logger.addHandler(file_handler)
    
    def info(self, message: str):
        """Log info message."""
        self.logger.info(message)
    
    def debug(self, message: str):
        """Log debug message."""
        self.logger.debug(message)
    
    def warning(self, message: str):
        """Log warning message."""
        self.logger.warning(message)
    
    def error(self, message: str):
        """Log error message."""
        self.logger.error(message)
    
    def success(self, location_name: str, zip_code: str, jobs_found: int, jobs_with_salary: int):
        """Log successful location search.
        
        Args:
            location_name: Name of the location
            zip_code: Zip code searched
            jobs_found: Total jobs found
            jobs_with_salary: Jobs with salary data
        """
        message = f"SUCCESS | {location_name} ({zip_code}) - {jobs_found} jobs found, {jobs_with_salary} with salary"
        self.logger.info(message)
    
    def failure(self, location_name: str, zip_code: str, error: str):
        """Log failed location search.
        
        Args:
            location_name: Name of the location
            zip_code: Zip code searched
            error: Error message
        """
        message = f"ERROR | {location_name} ({zip_code}) - {error}"
        self.logger.error(message)
    
    def batch_start(self, batch_num: int, total_batches: int, locations: int):
        """Log batch start.
        
        Args:
            batch_num: Current batch number
            total_batches: Total number of batches
            locations: Number of locations in this batch
        """
        message = f"Starting batch {batch_num}/{total_batches} ({locations} locations)"
        self.logger.info(message)
    
    def batch_complete(self, batch_num: int, total_batches: int, successful: int, total: int):
        """Log batch completion.
        
        Args:
            batch_num: Current batch number
            total_batches: Total number of batches
            successful: Number of successful locations
            total: Total locations in batch
        """
        message = f"Batch {batch_num}/{total_batches} completed - {successful}/{total} successful"
        self.logger.info(message)
    
    def market_summary(self, market_name: str, locations: int, total_jobs: int, 
                      jobs_with_salary: int, sufficient_data: bool):
        """Log market summary.
        
        Args:
            market_name: Name of the market
            locations: Number of locations searched
            total_jobs: Total jobs found
            jobs_with_salary: Jobs with salary data
            sufficient_data: Whether market has sufficient data
        """
        status = "SUFFICIENT" if sufficient_data else "INSUFFICIENT"
        message = (f"Market Summary | {market_name}: {locations} locations, "
                  f"{total_jobs} jobs, {jobs_with_salary} with salary - {status}")
        self.logger.info(message)
    
    def execution_summary(self, total_locations: int, successful_locations: int,
                         total_jobs: int, jobs_with_salary: int, 
                         markets_with_data: int, total_markets: int,
                         elapsed_time: float):
        """Log execution summary.
        
        Args:
            total_locations: Total locations attempted
            successful_locations: Successful location searches
            total_jobs: Total jobs found
            jobs_with_salary: Jobs with salary data
            markets_with_data: Markets with sufficient data
            total_markets: Total markets processed
            elapsed_time: Total execution time in seconds
        """
        hours = int(elapsed_time // 3600)
        minutes = int((elapsed_time % 3600) // 60)
        seconds = int(elapsed_time % 60)
        
        self.logger.info("=" * 60)
        self.logger.info("EXECUTION SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"Locations: {successful_locations}/{total_locations} successful")
        self.logger.info(f"Jobs Found: {total_jobs:,}")
        self.logger.info(f"Jobs with Salary: {jobs_with_salary:,}")
        self.logger.info(f"Markets with Data: {markets_with_data}/{total_markets}")
        self.logger.info(f"Execution Time: {hours:02d}:{minutes:02d}:{seconds:02d}")
        self.logger.info("=" * 60)


def setup_logger(output_dir: Path, verbose: bool = False) -> MarketAnalysisLogger:
    """Set up logger for market analysis.
    
    Args:
        output_dir: Directory for output files
        verbose: Whether to show detailed console output
        
    Returns:
        Configured logger instance
    """
    log_file = output_dir / "execution_log.txt"
    return MarketAnalysisLogger(str(log_file), verbose)