"""Market analysis module for jobx.

This module provides tools for analyzing job market compensation data
across multiple geographic locations, organized by markets and regions.
"""

from jobx.market_analysis.config_loader import load_config
from jobx.market_analysis.batch_executor import BatchExecutor
from jobx.market_analysis.data_aggregator import DataAggregator
from jobx.market_analysis.statistics_calculator import StatisticsCalculator
from jobx.market_analysis.report_generator import ReportGenerator

__all__ = [
    "load_config",
    "BatchExecutor",
    "DataAggregator", 
    "StatisticsCalculator",
    "ReportGenerator"
]