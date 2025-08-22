# Copyright (c) 2025 Michelle Pellon. MIT License

"""Tests for SERP tracking functionality."""

import pytest
from bs4 import BeautifulSoup

from jobx.serp import (
    SerpItem,
    LinkedInSerpParser,
    IndeedSerpParser,
    normalize_company_name,
    is_my_company,
)


class TestSerpItem:
    """Test SerpItem dataclass."""
    
    def test_absolute_rank_calculation(self):
        """Test absolute rank calculation."""
        item = SerpItem(
            job_id="123",
            page_index=0,
            index_on_page=5
        )
        # First page (0), 6th position (index 5) = rank 6
        assert item.absolute_rank_with_page_size(25) == 6
        
        item = SerpItem(
            job_id="456",
            page_index=2,
            index_on_page=10
        )
        # Third page (2), 11th position (index 10) = 2*25 + 10 + 1 = 61
        assert item.absolute_rank_with_page_size(25) == 61
        
    def test_serp_item_with_sponsorship(self):
        """Test SerpItem with sponsorship flag."""
        item = SerpItem(
            job_id="789",
            page_index=0,
            index_on_page=0,
            is_sponsored=True,
            company_name="Acme Corp"
        )
        assert item.is_sponsored is True
        assert item.company_name == "Acme Corp"


class TestLinkedInSerpParser:
    """Test LinkedIn SERP parser."""
    
    @pytest.fixture
    def parser(self):
        """Create LinkedIn SERP parser."""
        return LinkedInSerpParser()
        
    @pytest.fixture
    def linkedin_html(self):
        """Sample LinkedIn search results HTML."""
        return """
        <div>
            <div class="base-search-card">
                <a class="base-card__full-link" href="/jobs/view/123456789">
                    Job Title 1
                </a>
                <h4 class="base-search-card__subtitle">
                    <a>Company ABC</a>
                </h4>
            </div>
            <div class="base-search-card">
                <a class="base-card__full-link" href="/jobs/view/987654321">
                    Job Title 2
                </a>
                <h4 class="base-search-card__subtitle">
                    <a>Company XYZ</a>
                </h4>
                <span>Promoted</span>
            </div>
        </div>
        """
        
    def test_parse_serp_items(self, parser, linkedin_html):
        """Test parsing LinkedIn SERP items."""
        soup = BeautifulSoup(linkedin_html, "html.parser")
        items = parser.parse_serp_items(soup, page_index=0)
        
        assert len(items) == 2
        assert items[0].job_id == "/jobs/view/123456789"  # LinkedIn parser doesn't extract just the ID
        assert items[0].page_index == 0
        assert items[0].index_on_page == 0
        assert items[0].company_name == "Company ABC"
        assert items[0].is_sponsored is False
        
        assert items[1].job_id == "/jobs/view/987654321"  # LinkedIn parser doesn't extract just the ID
        assert items[1].page_index == 0
        assert items[1].index_on_page == 1
        assert items[1].company_name == "Company XYZ"
        assert items[1].is_sponsored is True  # Contains "Promoted"
        
    def test_detect_sponsored(self, parser):
        """Test sponsored detection."""
        html = '<div class="job-card">Regular job</div>'
        element = BeautifulSoup(html, "html.parser").find("div")
        assert parser.detect_sponsored(element) is False
        
        html = '<div class="job-card">Promoted position available</div>'
        element = BeautifulSoup(html, "html.parser").find("div")
        assert parser.detect_sponsored(element) is True
        
        html = '<div class="job-card sponsored">Job listing</div>'
        element = BeautifulSoup(html, "html.parser").find("div")
        assert parser.detect_sponsored(element) is True


class TestIndeedSerpParser:
    """Test Indeed SERP parser."""
    
    @pytest.fixture
    def parser(self):
        """Create Indeed SERP parser."""
        return IndeedSerpParser()
        
    @pytest.fixture
    def indeed_api_results(self):
        """Sample Indeed API job results."""
        return [
            {
                "job": {
                    "key": "abc123",
                    "employer": {"name": "Tech Corp"},
                    "sponsored": False
                }
            },
            {
                "job": {
                    "key": "def456",
                    "employer": {"name": "Data Inc"},
                    "sponsored": True
                }
            },
            {
                "job": {
                    "key": "ghi789",
                    "employer": {"name": "AI Solutions"},
                    "attributes": [
                        {"label": "Full-time"},
                        {"label": "Promoted"}
                    ]
                }
            }
        ]
        
    def test_parse_serp_items(self, parser, indeed_api_results):
        """Test parsing Indeed SERP items from API response."""
        items = parser.parse_serp_items(indeed_api_results, page_index=1)
        
        assert len(items) == 3
        
        assert items[0].job_id == "abc123"
        assert items[0].page_index == 1
        assert items[0].index_on_page == 0
        assert items[0].company_name == "Tech Corp"
        assert items[0].is_sponsored is False
        
        assert items[1].job_id == "def456"
        assert items[1].page_index == 1
        assert items[1].index_on_page == 1
        assert items[1].company_name == "Data Inc"
        assert items[1].is_sponsored is True
        
        assert items[2].job_id == "ghi789"
        assert items[2].page_index == 1
        assert items[2].index_on_page == 2
        assert items[2].company_name == "AI Solutions"
        assert items[2].is_sponsored is True  # Has "Promoted" in attributes
        
    def test_detect_sponsored_from_api(self, parser):
        """Test sponsored detection from API response."""
        # Direct sponsored flag
        job_result = {"job": {"sponsored": True}}
        assert parser.detect_sponsored_from_api(job_result) is True
        
        # No sponsored indicators
        job_result = {"job": {"sponsored": False}}
        assert parser.detect_sponsored_from_api(job_result) is False
        
        # Sponsored in attributes
        job_result = {
            "job": {
                "attributes": [
                    {"label": "Remote"},
                    {"label": "Sponsored"}
                ]
            }
        }
        assert parser.detect_sponsored_from_api(job_result) is True
        
        # Promoted in listing type
        job_result = {"job": {"listingType": "promoted"}}
        assert parser.detect_sponsored_from_api(job_result) is True


class TestCompanyNormalization:
    """Test company name normalization."""
    
    def test_normalize_company_name(self):
        """Test company name normalization."""
        assert normalize_company_name("Apple Inc.") == "apple"
        assert normalize_company_name("Microsoft Corporation") == "microsoft"
        assert normalize_company_name("Google LLC") == "google"
        assert normalize_company_name("Amazon.com, Inc.") == "amazon.com"
        assert normalize_company_name("Meta Platforms, Inc.") == "meta platforms"
        assert normalize_company_name("OpenAI") == "openai"
        assert normalize_company_name("NVIDIA Corporation") == "nvidia"
        assert normalize_company_name("Tesla, Inc.") == "tesla"
        assert normalize_company_name("  Spaces  Company  ") == "spaces"
        assert normalize_company_name("") == ""
        assert normalize_company_name("IBM") == "ibm"
        
    def test_is_my_company(self):
        """Test company matching."""
        my_companies = {
            normalize_company_name("Apple Inc."),
            normalize_company_name("Apple"),
            normalize_company_name("Apple Computer")
        }
        
        assert is_my_company("Apple Inc.", my_companies) is True
        assert is_my_company("Apple", my_companies) is True
        assert is_my_company("Apple Corporation", my_companies) is True  # "Apple Corporation" normalizes to "apple"
        assert is_my_company("Microsoft", my_companies) is False
        assert is_my_company("", my_companies) is False
        assert is_my_company("Apple Inc.", set()) is False
        
    def test_case_insensitive_matching(self):
        """Test case-insensitive company matching."""
        my_companies = {normalize_company_name("TechCorp")}
        
        assert is_my_company("TECHCORP", my_companies) is True
        assert is_my_company("techcorp", my_companies) is True
        assert is_my_company("TechCorp", my_companies) is True
        assert is_my_company("Tech Corp", my_companies) is False  # Space difference