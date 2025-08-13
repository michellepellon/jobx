# Copyright (c) 2025 Michelle Pellon. MIT License

"""jobx.linkedin

This module contains the LinkedIn scraper implementation. It provides functionality
for scraping job listings from LinkedIn with support for filtering, pagination,
and job detail extraction.
"""

from __future__ import annotations

import math
import secrets
import time
from datetime import datetime
from typing import Any, List, Optional, Union
from urllib.parse import unquote, urlparse, urlunparse

import regex as re
from bs4 import BeautifulSoup
from bs4.element import Tag

from jobx.exception import LinkedInException
from jobx.linkedin.constant import headers
from jobx.linkedin.util import job_type_code, parse_company_industry, parse_job_level, parse_job_type
from jobx.model import (
    Compensation,
    Country,
    DescriptionFormat,
    JobPost,
    JobResponse,
    Location,
    Scraper,
    ScraperInput,
    Site,
)
from jobx.serp import LinkedInSerpParser, is_my_company, normalize_company_name
from jobx.util import (
    create_logger,
    create_session,
    currency_parser,
    extract_emails_from_text,
    is_remote_job,
    markdown_converter,
    remove_attributes,
)

log = create_logger("LinkedIn")


class LinkedIn(Scraper):
    """LinkedIn job scraper implementation."""
    base_url = "https://www.linkedin.com"
    delay = 3
    band_delay = 4
    jobs_per_page = 25

    def __init__(
        self, proxies: Union[List[str], str, None] = None, ca_cert: Optional[str] = None
    ):
        """Initializes LinkedInScraper with the LinkedIn job search url."""
        # Convert single proxy string to list for base class compatibility
        proxy_list: Optional[List[str]] = None
        if isinstance(proxies, str):
            proxy_list = [proxies]
        elif isinstance(proxies, list):
            proxy_list = proxies
        super().__init__(Site.LINKEDIN, proxies=proxy_list, ca_cert=ca_cert)
        self.session = create_session(
            proxies=self.proxies,
            ca_cert=ca_cert,
            is_tls=False,
            has_retry=True,
            delay=5,
            clear_cookies=True,
        )
        self.session.headers.update(headers)
        self.scraper_input: Optional[ScraperInput] = None
        self.country = "worldwide"
        self.job_url_direct_regex = re.compile(r'(?<=\?url=)[^"]+')

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        """Scrapes LinkedIn for jobs with scraper_input criteria.

        :param scraper_input:
        :return: job_response.
        """
        self.scraper_input = scraper_input
        job_list: list[JobPost] = []
        seen_ids = set()
        start = scraper_input.offset // 10 * 10 if scraper_input.offset else 0
        request_count = 0
        seconds_old = (
            scraper_input.hours_old * 3600 if scraper_input.hours_old else None
        )

        # Initialize SERP parser if tracking is enabled
        serp_parser = LinkedInSerpParser() if scraper_input.track_serp else None

        # Normalize company names for matching
        normalized_my_companies = set()
        if scraper_input.my_company_names:
            normalized_my_companies = {normalize_company_name(name) for name in scraper_input.my_company_names}
        def should_continue_search() -> bool:
            return len(job_list) < scraper_input.results_wanted and start < 1000

        while should_continue_search():
            request_count += 1
            log.info(
                f"search page: {request_count} / {math.ceil(scraper_input.results_wanted / 10)}"
            )
            params = {
                "keywords": scraper_input.search_term,
                "location": scraper_input.location,
                "distance": scraper_input.distance,
                "f_WT": 2 if scraper_input.is_remote else None,
                "f_JT": (
                    job_type_code(scraper_input.job_type)
                    if scraper_input.job_type
                    else None
                ),
                "pageNum": 0,
                "start": start,
                "f_AL": "true" if scraper_input.easy_apply else None,
                "f_C": (
                    ",".join(map(str, scraper_input.linkedin_company_ids))
                    if scraper_input.linkedin_company_ids
                    else None
                ),
            }
            if seconds_old is not None:
                params["f_TPR"] = f"r{seconds_old}"

            params = {k: v for k, v in params.items() if v is not None}
            try:
                response = self.session.get(
                    f"{self.base_url}/jobs-guest/jobs/api/seeMoreJobPostings/search?",
                    params=params,
                    timeout=10,
                )
                if response.status_code not in range(200, 400):
                    if response.status_code == 429:
                        err = (
                            "429 Response - Blocked by LinkedIn for too many requests"
                        )
                    else:
                        err = f"LinkedIn response status code {response.status_code}"
                        err += f" - {response.text}"
                    log.error(err)
                    return JobResponse(jobs=job_list)
            except Exception as e:
                if "Proxy responded with" in str(e):
                    log.error("LinkedIn: Bad proxy")
                else:
                    log.error(f"LinkedIn: {e!s}")
                return JobResponse(jobs=job_list)

            soup = BeautifulSoup(response.text, "html.parser")
            job_cards = soup.find_all("div", class_="base-search-card")
            if len(job_cards) == 0:
                return JobResponse(jobs=job_list)

            # Parse SERP items if tracking is enabled
            serp_items = []
            if serp_parser:
                page_index = (start // self.jobs_per_page)
                serp_items = serp_parser.parse_serp_items(soup, page_index)
                # Create a mapping from job_id to SERP item
                serp_map = {item.job_id: item for item in serp_items}
            else:
                serp_map = {}

            for job_card in job_cards:
                if not isinstance(job_card, Tag):
                    continue
                href_tag = job_card.find("a", class_="base-card__full-link")
                if href_tag and hasattr(href_tag, 'attrs') and "href" in href_tag.attrs:
                    href = href_tag.attrs["href"].split("?")[0]
                    job_id = href.split("-")[-1]

                    if job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)

                    try:
                        fetch_desc = scraper_input.linkedin_fetch_description
                        if isinstance(job_card, Tag):
                            job_post = self._process_job(job_card, job_id, fetch_desc)
                        else:
                            continue
                        if job_post:
                            # Add SERP tracking data if available
                            if job_id in serp_map:
                                serp_item = serp_map[job_id]
                                job_post.serp_page_index = serp_item.page_index
                                job_post.serp_index_on_page = serp_item.index_on_page
                                job_post.serp_absolute_rank = serp_item.absolute_rank_with_page_size(self.jobs_per_page)
                                job_post.serp_page_size_observed = len(serp_items)
                                job_post.serp_is_sponsored = serp_item.is_sponsored

                                # Add company matching
                                if job_post.company_name:
                                    job_post.company_normalized = normalize_company_name(job_post.company_name)
                                    job_post.is_my_company = is_my_company(job_post.company_name, normalized_my_companies)

                            job_list.append(job_post)
                        if not should_continue_search():
                            break
                    except Exception as e:
                        raise LinkedInException(str(e)) from e

            if should_continue_search():
                time.sleep(self.delay + secrets.randbelow(self.band_delay))
                start += len(job_list)

        job_list = job_list[: scraper_input.results_wanted]
        return JobResponse(jobs=job_list)

    def _process_job(
        self, job_card: Tag, job_id: str, full_descr: bool
    ) -> Optional[JobPost]:
        salary_tag = job_card.find("span", class_="job-search-card__salary-info")

        compensation = description = None
        if salary_tag:
            salary_text = salary_tag.get_text(separator=" ").strip()
            salary_values = [currency_parser(value) for value in salary_text.split("-")]
            salary_min = salary_values[0]
            salary_max = salary_values[1]
            currency = salary_text[0] if salary_text[0] != "$" else "USD"

            compensation = Compensation(
                min_amount=int(salary_min),
                max_amount=int(salary_max),
                currency=currency,
            )

        title_tag = job_card.find("span", class_="sr-only")
        title = title_tag.get_text(strip=True) if title_tag and hasattr(title_tag, 'get_text') else "N/A"

        company_tag = job_card.find("h4", class_="base-search-card__subtitle")
        company_a_tag = company_tag.find("a") if company_tag and hasattr(company_tag, 'find') else None
        company_url = (
            urlunparse(urlparse(company_a_tag.get("href"))._replace(query=""))
            if company_a_tag and company_a_tag.has_attr("href")
            else ""
        )
        company = company_a_tag.get_text(strip=True) if company_a_tag and hasattr(company_a_tag, 'get_text') else "N/A"

        metadata_card = job_card.find("div", class_="base-search-card__metadata")
        metadata_card_tag: Optional[Tag] = metadata_card if isinstance(metadata_card, Tag) else None
        location = self._get_location(metadata_card_tag)

        datetime_tag = (
            metadata_card_tag.find("time", class_="job-search-card__listdate")
            if metadata_card_tag
            else None
        )
        date_posted = None
        if (datetime_tag and hasattr(datetime_tag, 'get') and
            hasattr(datetime_tag, 'attrs') and "datetime" in datetime_tag.attrs):
            datetime_str = str(datetime_tag.get("datetime", ""))
            try:
                date_posted = datetime.strptime(datetime_str, "%Y-%m-%d")
            except ValueError:
                date_posted = None
        job_details: dict[str, Any] = {}
        if full_descr:
            job_details = self._get_job_details(job_id)
            description = job_details.get("description")
        location_str = location.display_location() if location else ""
        is_remote = is_remote_job(title, description or "", location_str)

        return JobPost(
            id=f"li-{job_id}",
            title=title,
            company_name=company,
            company_url=company_url,
            location=location,
            is_remote=is_remote,
            date_posted=date_posted,
            job_url=f"{self.base_url}/jobs/view/{job_id}",
            compensation=compensation,
            job_type=job_details.get("job_type"),
            job_level=job_details.get("job_level", "").lower(),
            company_industry=job_details.get("company_industry"),
            description=job_details.get("description"),
            job_url_direct=job_details.get("job_url_direct"),
            emails=extract_emails_from_text(description or ""),
            company_logo=job_details.get("company_logo"),
            job_function=job_details.get("job_function"),
        )

    def _get_job_details(self, job_id: str) -> dict[str, Any]:
        """Retrieves job description and other job details by going to the job page url.

        :param job_page_url:
        :return: dict.
        """
        try:
            response = self.session.get(
                f"{self.base_url}/jobs/view/{job_id}", timeout=5
            )
            response.raise_for_status()
        except Exception:
            return {}
        if "linkedin.com/signup" in response.url:
            return {}

        soup = BeautifulSoup(response.text, "html.parser")
        div_content = soup.find(
            "div", class_=lambda x: x and "show-more-less-html__markup" in x
        )
        description = None
        if div_content is not None:
            div_content = remove_attributes(div_content)
            description = div_content.prettify(formatter="html")
            if self.scraper_input and self.scraper_input.description_format == DescriptionFormat.MARKDOWN:
                description = markdown_converter(description)

        h3_tag = soup.find(
            "h3", text=lambda text: text and "Job function" in text.strip()
        )

        job_function = None
        if h3_tag:
            job_function_span = h3_tag.find_next(
                "span", class_="description__job-criteria-text"
            )
            if job_function_span:
                job_function = job_function_span.text.strip()

        logo_image = soup.find("img", {"class": "artdeco-entity-image"})
        company_logo = (
            logo_image.get("data-delayed-url")
            if logo_image and hasattr(logo_image, 'get')
            else None
        )
        return {
            "description": description,
            "job_level": parse_job_level(soup),
            "company_industry": parse_company_industry(soup),
            "job_type": parse_job_type(soup),
            "job_url_direct": self._parse_job_url_direct(soup),
            "company_logo": company_logo,
            "job_function": job_function,
        }

    def _get_location(self, metadata_card: Optional[Tag]) -> Location:
        """Extracts the location data from the job metadata card.

        :param metadata_card
        :return: location.
        """
        location = Location(country=Country.from_string(self.country))
        if metadata_card is not None:
            location_tag = metadata_card.find(
                "span", class_="job-search-card__location"
            )
            location_string = location_tag.text.strip() if location_tag else "N/A"
            parts = location_string.split(", ")
            if len(parts) == 2:
                city, state = parts
                location = Location(
                    city=city,
                    state=state,
                    country=Country.from_string(self.country),
                )
            elif len(parts) == 3:
                city, state, country = parts
                country = Country.from_string(country)
                location = Location(city=city, state=state, country=country)
        return location

    def _parse_job_url_direct(self, soup: BeautifulSoup) -> Optional[str]:
        """Gets the job url direct from job page.

        :param soup:
        :return: str.
        """
        job_url_direct = None
        job_url_direct_content = soup.find("code", id="applyUrl")
        if job_url_direct_content and hasattr(job_url_direct_content, 'decode_contents'):
            job_url_direct_match = self.job_url_direct_regex.search(
                job_url_direct_content.decode_contents().strip()
            )
            if job_url_direct_match:
                job_url_direct = unquote(job_url_direct_match.group())

        return job_url_direct
