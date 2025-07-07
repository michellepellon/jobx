# Copyright (c) 2025 Michelle Pellon. MIT License..

"""
Pytest configuration and fixtures.
"""

import logging
import os
from typing import Generator
from unittest.mock import Mock

import pytest


@pytest.fixture(autouse=True)
def setup_test_logging() -> Generator[None, None, None]:
    """Set up logging for tests."""
    # Disable logging during tests unless specifically enabled
    if not os.getenv("JOBX_TEST_LOGGING"):
        logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)


@pytest.fixture
def mock_session() -> Mock:
    """Mock HTTP session for testing."""
    session = Mock()
    session.get.return_value.status_code = 200
    session.get.return_value.ok = True
    session.post.return_value.status_code = 200
    session.post.return_value.ok = True
    return session


@pytest.fixture
def sample_job_data() -> dict:
    """Sample job data for testing."""
    return {
        "id": "test-job-123",
        "title": "Software Engineer",
        "company": "Test Company",
        "location": "Remote",
        "description": "A test job posting for software engineer position.",
        "salary_min": 80000,
        "salary_max": 120000,
        "currency": "USD",
        "date_posted": "2025-01-01",
        "is_remote": True,
    }


@pytest.fixture
def sample_scraper_input():
    """Sample scraper input for testing."""
    from jobx.model import ScraperInput, Site, Country
    
    return ScraperInput(
        site_type=[Site.LINKEDIN],
        search_term="python developer",
        location="New York, NY",
        country=Country.USA,
        results_wanted=10,
    )