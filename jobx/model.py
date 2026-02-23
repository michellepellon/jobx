# Copyright (c) 2025 Michelle Pellon. MIT License

"""jobx.model

This module contains the data models and base classes for the job scraping system.
It defines the core data structures for job postings, search inputs, and responses.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from enum import Enum
from typing import List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field


class JobType(Enum):
    """Enumeration of job types with international variants."""
    FULL_TIME = (
        "fulltime",
        "períodointegral",
        "estágio/trainee",
        "cunormăîntreagă",
        "tiempocompleto",
        "vollzeit",
        "voltijds",
        "tempointegral",
        "全职",
        "plnýúvazek",
        "fuldtid",
        "دوامكامل",
        "kokopäivätyö",
        "tempsplein",
        "vollzeit",
        "πλήρηςαπασχόληση",
        "teljesmunkaidő",
        "tempopieno",
        "tempsplein",
        "heltid",
        "jornadacompleta",
        "pełnyetat",
        "정규직",
        "100%",
        "全職",
        "งานประจำ",
        "tamzamanli",
        "повназайнятість",
        "toànthờigian",
    )
    PART_TIME = ("parttime", "teilzeit", "částečnýúvazek", "deltid")
    CONTRACT = ("contract", "contractor")
    TEMPORARY = ("temporary",)
    INTERNSHIP = (
        "internship",
        "prácticas",
        "ojt(onthejobtraining)",
        "praktikum",
        "praktik",
    )

    PER_DIEM = ("perdiem",)
    NIGHTS = ("nights",)
    OTHER = ("other",)
    SUMMER = ("summer",)
    VOLUNTEER = ("volunteer",)


class Country(Enum):
    """Gets the subdomain for Indeed and Glassdoor.

    The second item in the tuple is the subdomain (and API country code if there's a ':' separator) for Indeed
    The third item in the tuple is the subdomain (and tld if there's a ':' separator) for Glassdoor
    """

    USA = ("usa,us,united states", "www:us", "com")

    # internal for linkedin
    WORLDWIDE = ("worldwide", "www")

    @property
    def indeed_domain_value(self) -> tuple[str, str]:
        """Extract Indeed domain and API country code from enum value."""
        subdomain, _, api_country_code = self.value[1].partition(":")
        if subdomain and api_country_code:
            return subdomain, api_country_code.upper()
        return self.value[1], self.value[1].upper()

    @classmethod
    def from_string(cls, country_str: str) -> Country:
        """Convert a string to the corresponding Country enum."""
        country_str = country_str.strip().lower()
        for country in cls:
            country_names = country.value[0].split(",")
            if country_str in country_names:
                return country
        valid_countries = [country.value for country in cls]
        valid_country_names = [country[0] for country in valid_countries]
        raise ValueError(
            f"Invalid country string: '{country_str}'. Valid countries are: {', '.join(valid_country_names)}"
        )


class Location(BaseModel):
    """Represents a job location with city, state, and country."""
    country: Union[Country, str, None] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None

    def display_location(self) -> str:
        """Format location for display."""
        location_parts = []
        if self.city:
            location_parts.append(self.city)
        if self.state:
            location_parts.append(self.state)
        if isinstance(self.country, str):
            location_parts.append(self.country)
        elif self.country and self.country != Country.WORLDWIDE:
            country_name = self.country.value[0]
            if "," in country_name:
                country_name = country_name.split(",")[0]
            if country_name in ("usa", "uk"):
                location_parts.append(country_name.upper())
            else:
                location_parts.append(country_name.title())
        return ", ".join(location_parts)


class CompensationInterval(Enum):
    """Enumeration of compensation intervals."""
    YEARLY = "yearly"
    MONTHLY = "monthly"
    WEEKLY = "weekly"
    DAILY = "daily"
    HOURLY = "hourly"

    @classmethod
    def get_interval(cls, pay_period: str) -> Optional[str]:
        """Get interval value from pay period string."""
        interval_mapping = {
            "YEAR": cls.YEARLY,
            "HOUR": cls.HOURLY,
        }
        if pay_period in interval_mapping:
            return interval_mapping[pay_period].value
        else:
            return cls[pay_period].value if pay_period in cls.__members__ else None


class Compensation(BaseModel):
    """Represents job compensation information."""
    interval: Optional[CompensationInterval] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    currency: Optional[str] = "USD"


class DescriptionFormat(Enum):
    """Enumeration of description formats."""
    MARKDOWN = "markdown"
    HTML = "html"


class JobPost(BaseModel):
    """Represents a job posting with all relevant information."""
    uuid: str = Field(default_factory=lambda: str(uuid4()))
    id: Optional[str] = None
    title: str
    company_name: Optional[str]
    job_url: str
    job_url_direct: Optional[str] = None
    location: Optional[Location]

    description: Optional[str] = None
    company_url: Optional[str] = None
    company_url_direct: Optional[str] = None

    job_type: Optional[List[JobType]] = None
    compensation: Optional[Compensation] = None
    date_posted: Optional[date] = None
    emails: Optional[List[str]] = None
    is_remote: Optional[bool] = None
    listing_type: Optional[str] = None

    # LinkedIn specific
    job_level: Optional[str] = None

    # LinkedIn and Indeed specific
    company_industry: Optional[str] = None

    # Indeed specific
    company_addresses: Optional[str] = None
    company_num_employees: Optional[str] = None
    company_revenue: Optional[str] = None
    company_description: Optional[str] = None
    company_logo: Optional[str] = None
    banner_photo_url: Optional[str] = None

    # LinkedIn only atm
    job_function: Optional[str] = None

    # Confidence score for search relevance
    confidence_score: Optional[float] = None

    # SERP tracking fields
    serp_page_index: Optional[int] = None
    serp_index_on_page: Optional[int] = None
    serp_absolute_rank: Optional[int] = None
    serp_page_size_observed: Optional[int] = None
    serp_is_sponsored: Optional[bool] = None
    company_normalized: Optional[str] = None
    is_my_company: Optional[bool] = None


class JobResponse(BaseModel):
    """Response containing a list of job postings."""
    jobs: List[JobPost] = []


class Site(Enum):
    """Enumeration of supported job sites."""
    LINKEDIN = "linkedin"
    INDEED = "indeed"


class SalarySource(Enum):
    """Enumeration of salary data sources."""
    DIRECT_DATA = "direct_data"
    DESCRIPTION = "description"


class ScraperInput(BaseModel):
    """Input parameters for job scraping operations."""
    site_type: List[Site]
    search_term: Optional[str] = None
    google_search_term: Optional[str] = None

    location: Optional[str] = None
    country: Optional[Country] = Country.USA
    distance: Optional[int] = None
    is_remote: bool = False
    job_type: Optional[JobType] = None
    easy_apply: Optional[bool] = None
    offset: int = 0
    linkedin_fetch_description: bool = False
    linkedin_company_ids: Optional[List[int]] = None
    description_format: Optional[DescriptionFormat] = DescriptionFormat.MARKDOWN

    results_wanted: int = 15
    hours_old: Optional[int] = None

    # SERP tracking options
    track_serp: bool = False
    my_company_names: Optional[List[str]] = None


class Scraper(ABC):
    """Abstract base class for job scrapers."""
    def __init__(
        self, site: Site, proxies: Optional[List[str]] = None, ca_cert: Optional[str] = None
    ):
        """Initialize scraper with site and optional proxy configuration."""
        self.site = site
        self.proxies = proxies
        self.ca_cert = ca_cert

    @abstractmethod
    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        """Scrape jobs based on input parameters."""
        ...
