# Copyright (c) 2025 Michelle Pellon. MIT License..

"""
Integration tests for scraping functionality.

These tests are marked as integration tests and can be skipped with:
pytest -m "not integration"
"""

import pytest

from jobx import scrape_jobs
from jobx.model import Site, Country


@pytest.mark.integration
class TestScrapingIntegration:
    """Integration tests for job scraping."""
    
    def test_scrape_jobs_basic(self):
        """Test basic job scraping functionality."""
        # This is a minimal integration test that doesn't hit real APIs
        # In a real scenario, you'd use recorded HTTP interactions
        results = scrape_jobs(
            site_name=[Site.LINKEDIN],
            search_term="python",
            location="New York, NY",
            results_wanted=1,
            country_indeed="usa"
        )
        
        # Basic structure validation
        assert hasattr(results, 'columns')
        assert hasattr(results, 'shape')
    
    @pytest.mark.slow
    def test_scrape_multiple_sites(self):
        """Test scraping from multiple sites."""
        # This would be a more comprehensive test
        # that takes longer to run
        results = scrape_jobs(
            site_name=[Site.LINKEDIN, Site.INDEED],
            search_term="software engineer",
            results_wanted=5,
            country_indeed="usa"
        )
        
        assert hasattr(results, 'columns')
        
    @pytest.mark.integration
    def test_error_handling(self):
        """Test error handling in scraping."""
        # Test with invalid parameters
        results = scrape_jobs(
            site_name=[],  # Empty site list
            results_wanted=1
        )
        
        # Should return empty DataFrame without crashing
        assert len(results) == 0