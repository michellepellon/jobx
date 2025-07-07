# Copyright (c) 2025 Michelle Pellon. MIT License..

"""
Unit tests for jobx.model module.
"""

from datetime import date

import pytest
from pydantic import ValidationError

from jobx.model import (
    JobPost,
    JobResponse,
    Location,
    Compensation,
    CompensationInterval,
    Country,
    JobType,
    Site,
    ScraperInput,
)


class TestLocation:
    """Test Location model."""
    
    def test_location_display_basic(self):
        """Test basic location display."""
        location = Location(city="New York", state="NY", country=Country.USA)
        display = location.display_location()
        assert "New York" in display
        assert "NY" in display
    
    def test_location_display_worldwide(self):
        """Test worldwide location display."""
        location = Location(city="Remote", country=Country.WORLDWIDE)
        display = location.display_location()
        assert "Remote" in display
    
    def test_location_display_string_country(self):
        """Test location with string country."""
        location = Location(city="London", country="UK")
        display = location.display_location()
        assert "London" in display
        assert "UK" in display


class TestCompensation:
    """Test Compensation model."""
    
    def test_compensation_basic(self):
        """Test basic compensation creation."""
        comp = Compensation(
            interval=CompensationInterval.YEARLY,
            min_amount=80000,
            max_amount=120000,
            currency="USD"
        )
        assert comp.interval == CompensationInterval.YEARLY
        assert comp.min_amount == 80000
        assert comp.max_amount == 120000
        assert comp.currency == "USD"
    
    def test_compensation_optional_fields(self):
        """Test compensation with optional fields."""
        comp = Compensation()
        assert comp.interval is None
        assert comp.min_amount is None
        assert comp.max_amount is None
        assert comp.currency == "USD"  # Default value


class TestJobPost:
    """Test JobPost model."""
    
    def test_job_post_minimal(self):
        """Test JobPost with minimal required fields."""
        job = JobPost(
            title="Software Engineer",
            company_name="Test Company",
            job_url="https://example.com/job/123",
            location=None
        )
        assert job.title == "Software Engineer"
        assert job.company_name == "Test Company"
        assert job.job_url == "https://example.com/job/123"
    
    def test_job_post_complete(self):
        """Test JobPost with all fields."""
        location = Location(city="New York", state="NY", country=Country.USA)
        compensation = Compensation(
            interval=CompensationInterval.YEARLY,
            min_amount=80000,
            max_amount=120000
        )
        
        job = JobPost(
            id="job-123",
            title="Senior Software Engineer",
            company_name="Tech Corp",
            job_url="https://example.com/job/123",
            location=location,
            description="Great opportunity...",
            compensation=compensation,
            date_posted=date(2025, 1, 1),
            job_type=[JobType.FULL_TIME],
            is_remote=True
        )
        
        assert job.id == "job-123"
        assert job.title == "Senior Software Engineer"
        assert job.is_remote is True
        assert len(job.job_type) == 1
        assert job.job_type[0] == JobType.FULL_TIME


class TestJobResponse:
    """Test JobResponse model."""
    
    def test_job_response_empty(self):
        """Test empty JobResponse."""
        response = JobResponse()
        assert len(response.jobs) == 0
    
    def test_job_response_with_jobs(self):
        """Test JobResponse with jobs."""
        job1 = JobPost(
            title="Engineer 1",
            company_name="Company 1",
            job_url="https://example.com/job/1",
            location=None
        )
        job2 = JobPost(
            title="Engineer 2",
            company_name="Company 2", 
            job_url="https://example.com/job/2",
            location=None
        )
        
        response = JobResponse(jobs=[job1, job2])
        assert len(response.jobs) == 2
        assert response.jobs[0].title == "Engineer 1"
        assert response.jobs[1].title == "Engineer 2"


class TestCountry:
    """Test Country enum."""
    
    def test_country_from_string(self):
        """Test Country.from_string method."""
        assert Country.from_string("usa") == Country.USA
        assert Country.from_string("US") == Country.USA
        assert Country.from_string("united states") == Country.USA
        assert Country.from_string("worldwide") == Country.WORLDWIDE
    
    def test_country_from_string_invalid(self):
        """Test Country.from_string with invalid input."""
        with pytest.raises(ValueError):
            Country.from_string("invalid_country")
    
    def test_indeed_domain_value(self):
        """Test indeed_domain_value property."""
        domain, code = Country.USA.indeed_domain_value
        assert domain == "www"
        assert code == "US"


class TestScraperInput:
    """Test ScraperInput model."""
    
    def test_scraper_input_minimal(self):
        """Test ScraperInput with minimal fields."""
        scraper_input = ScraperInput(site_type=[Site.LINKEDIN])
        assert len(scraper_input.site_type) == 1
        assert scraper_input.site_type[0] == Site.LINKEDIN
        assert scraper_input.country == Country.USA  # Default
        assert scraper_input.results_wanted == 15  # Default
    
    def test_scraper_input_complete(self):
        """Test ScraperInput with all fields."""
        scraper_input = ScraperInput(
            site_type=[Site.LINKEDIN, Site.INDEED],
            search_term="python developer",
            location="New York, NY",
            country=Country.USA,
            distance=25,
            is_remote=True,
            job_type=JobType.FULL_TIME,
            results_wanted=50
        )
        
        assert len(scraper_input.site_type) == 2
        assert scraper_input.search_term == "python developer"
        assert scraper_input.location == "New York, NY"
        assert scraper_input.distance == 25
        assert scraper_input.is_remote is True
        assert scraper_input.job_type == JobType.FULL_TIME
        assert scraper_input.results_wanted == 50