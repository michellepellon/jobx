# Copyright (c) 2025 Michelle Pellon. MIT License

"""jobx.serp

This module contains SERP (Search Engine Results Page) tracking functionality
for monitoring job posting positions and visibility metrics across job sites.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, List, Optional, Set, Union

from bs4 import BeautifulSoup
from bs4.element import Tag

from jobx.model import Site


@dataclass
class SerpItem:
    """Represents an item in search results with position tracking."""
    job_id: str
    page_index: int
    index_on_page: int
    is_sponsored: Optional[bool] = None
    company_name: Optional[str] = None

    @property
    def absolute_rank(self) -> int:
        """Calculate absolute rank across all pages (1-based)."""
        # We'll calculate this dynamically based on observed page size
        return self.absolute_rank_with_page_size(25)  # Default page size

    def absolute_rank_with_page_size(self, page_size: int) -> int:
        """Calculate absolute rank with specific page size."""
        return self.page_index * page_size + self.index_on_page + 1


class SerpParser(ABC):
    """Abstract base class for SERP parsers."""

    def __init__(self, site: Site):
        """Initialize parser with site type."""
        self.site = site

    @abstractmethod
    def parse_serp_items(
        self,
        soup: BeautifulSoup,
        page_index: int
    ) -> List[SerpItem]:
        """Parse SERP items from HTML soup.
        
        Args:
            soup: BeautifulSoup object of the search results page
            page_index: 0-based page index
            
        Returns:
            List of SerpItem objects
        """
        ...

    @abstractmethod
    def detect_sponsored(self, element: Tag) -> Optional[bool]:
        """Detect if a job posting is sponsored/promoted.
        
        Args:
            element: HTML element of the job posting
            
        Returns:
            True if sponsored, False if organic, None if uncertain
        """
        ...


class LinkedInSerpParser(SerpParser):
    """SERP parser for LinkedIn job listings."""

    def __init__(self) -> None:
        """Initialize LinkedIn SERP parser."""
        super().__init__(Site.LINKEDIN)

    def parse_serp_items(
        self,
        soup: BeautifulSoup,
        page_index: int
    ) -> List[SerpItem]:
        """Parse LinkedIn SERP items."""
        items = []
        job_cards = soup.find_all("div", class_="base-search-card")

        # Filter out non-organic widgets (e.g., "People also searched")
        organic_cards = []
        for card in job_cards:
            if not isinstance(card, Tag):
                continue
            # Check if it's an actual job card
            href_tag = card.find("a", class_="base-card__full-link")
            if href_tag and hasattr(href_tag, 'attrs') and "href" in href_tag.attrs:
                organic_cards.append(card)

        for index, job_card in enumerate(organic_cards):
            href_tag = job_card.find("a", class_="base-card__full-link")
            if not href_tag or not hasattr(href_tag, 'attrs') or "href" not in href_tag.attrs:
                continue

            href = href_tag.attrs["href"].split("?")[0]
            job_id = href.split("-")[-1]

            # Extract company name for matching
            company_tag = job_card.find("h4", class_="base-search-card__subtitle")
            company_a_tag = company_tag.find("a") if company_tag and isinstance(company_tag, Tag) else None
            company_name = None
            if company_a_tag and hasattr(company_a_tag, 'get_text'):
                company_name = company_a_tag.get_text(strip=True)

            # Detect if sponsored
            is_sponsored = self.detect_sponsored(job_card)

            items.append(SerpItem(
                job_id=job_id,
                page_index=page_index,
                index_on_page=index,
                is_sponsored=is_sponsored,
                company_name=company_name
            ))

        return items

    def detect_sponsored(self, element: Tag) -> Optional[bool]:
        """Detect sponsored LinkedIn postings."""
        # Look for promoted/sponsored indicators
        sponsored_indicators = [
            "promoted",
            "sponsored",
            "featured",
            "ad"
        ]

        element_text = element.get_text().lower() if element else ""
        for indicator in sponsored_indicators:
            if indicator in element_text:
                return True

        # Check for specific sponsored classes (LinkedIn may use these)
        if element:
            classes = element.get("class", [])
            if isinstance(classes, list):
                class_str = " ".join(str(c) for c in classes).lower()
            else:
                class_str = str(classes).lower()
            for indicator in sponsored_indicators:
                if indicator in class_str:
                    return True

        return False


class IndeedSerpParser(SerpParser):
    """SERP parser for Indeed job listings."""

    def __init__(self) -> None:
        """Initialize Indeed SERP parser."""
        super().__init__(Site.INDEED)

    def parse_serp_items(
        self,
        job_results: Union[List[dict[str, Any]], BeautifulSoup],
        page_index: int
    ) -> List[SerpItem]:
        """Parse Indeed SERP items from API response.
        
        Args:
            job_results: List of job result dicts from Indeed API
            page_index: 0-based page index
            
        Returns:
            List of SerpItem objects
        """
        items = []
        
        # Handle the union type - we only expect list for Indeed
        if not isinstance(job_results, list):
            return items

        for index, job_result in enumerate(job_results):
            job = job_result.get("job", {})
            job_id = job.get("key", "")

            # Extract company name
            employer = job.get("employer", {})
            company_name = employer.get("name") if employer else None

            # Detect if sponsored - Indeed API may include this info
            is_sponsored = self.detect_sponsored_from_api(job_result)

            items.append(SerpItem(
                job_id=job_id,
                page_index=page_index,
                index_on_page=index,
                is_sponsored=is_sponsored,
                company_name=company_name
            ))

        return items

    def detect_sponsored(self, element: Tag) -> Optional[bool]:
        """Detect sponsored Indeed postings from HTML (not used for API)."""
        # This method is for HTML parsing if needed
        return None

    def detect_sponsored_from_api(self, job_result: dict[str, Any]) -> Optional[bool]:
        """Detect if an Indeed job is sponsored from API response."""
        job = job_result.get("job", {})

        # Check for sponsored indicators in the API response
        # Indeed may mark these in various ways
        if job.get("sponsored"):
            return True

        # Check in attributes
        attributes = job.get("attributes", [])
        for attr in attributes:
            label = attr.get("label", "").lower()
            if "sponsored" in label or "promoted" in label:
                return True

        # Check listing type
        if job.get("listingType", "").lower() in ["sponsored", "promoted"]:
            return True

        return False


def normalize_company_name(company_name: str) -> str:
    """Normalize company name for matching.
    
    Args:
        company_name: Raw company name
        
    Returns:
        Normalized company name for comparison
    """
    if not company_name:
        return ""

    # Convert to lowercase
    normalized = company_name.lower()

    # Remove common suffixes
    suffixes_to_remove = [
        ", inc.",
        ", inc",
        " inc.",
        " inc",
        ", llc",
        " llc",
        ", ltd",
        " ltd",
        ", corp",
        " corp",
        ", co.",
        " co.",
        ", co",
        " co",
        ", incorporated",
        " incorporated",
        ", limited",
        " limited",
        ", corporation",
        " corporation",
        ", company",
        " company",
    ]

    for suffix in suffixes_to_remove:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)]
            break

    # Remove extra whitespace
    normalized = " ".join(normalized.split())

    return normalized


def is_my_company(company_name: str, my_company_names: Set[str]) -> bool:
    """Check if a company name matches any of the configured company names.
    
    Args:
        company_name: Company name to check
        my_company_names: Set of normalized company names to match against
        
    Returns:
        True if the company matches any of the configured names
    """
    if not company_name or not my_company_names:
        return False

    normalized = normalize_company_name(company_name)
    return normalized in my_company_names
