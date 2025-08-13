# Copyright (c) 2025 Michelle Pellon. MIT License

"""jobx.indeed

This module contains the Indeed scraper implementation. It provides functionality
for scraping job listings from Indeed using their GraphQL API with support for
filtering, pagination, and job detail extraction.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from jobx.indeed.constant import api_headers, job_search_query
from jobx.indeed.util import get_compensation, get_job_type
from jobx.model import (
    DescriptionFormat,
    JobPost,
    JobResponse,
    JobType,
    Location,
    Scraper,
    ScraperInput,
    Site,
)
from jobx.serp import IndeedSerpParser, is_my_company, normalize_company_name
from jobx.util import (
    create_logger,
    create_session,
    extract_emails_from_text,
    is_remote_job,
    markdown_converter,
)

log = create_logger("Indeed")


class Indeed(Scraper):
    """Indeed job scraper implementation."""
    def __init__(
        self, proxies: Union[List[str], str, None] = None, ca_cert: Optional[str] = None
    ):
        """Initializes IndeedScraper with the Indeed API url."""
        # Convert single proxy string to list for base class compatibility
        proxy_list: Optional[List[str]] = None
        if isinstance(proxies, str):
            proxy_list = [proxies]
        elif isinstance(proxies, list):
            proxy_list = proxies
        super().__init__(Site.INDEED, proxies=proxy_list)

        self.session = create_session(
            proxies=self.proxies, ca_cert=ca_cert, is_tls=False
        )
        self.scraper_input: Optional[ScraperInput] = None
        self.jobs_per_page = 100
        self.num_workers = 10
        self.seen_urls: set[str] = set()
        self.headers: Optional[Dict[str, str]] = None
        self.api_country_code: Optional[str] = None
        self.base_url: Optional[str] = None
        self.api_url = "https://apis.indeed.com/graphql"

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        """Scrapes Indeed for jobs with scraper_input criteria.

        :param scraper_input:
        :return: job_response.
        """
        self.scraper_input = scraper_input
        assert self.scraper_input is not None and self.scraper_input.country is not None  # Type narrowing for mypy
        domain, self.api_country_code = self.scraper_input.country.indeed_domain_value
        self.base_url = f"https://{domain}.indeed.com"
        self.headers = api_headers.copy()
        self.headers["indeed-co"] = str(self.scraper_input.country.indeed_domain_value)
        job_list: list[JobPost] = []
        page = 1

        cursor = None

        # Initialize SERP parser if tracking is enabled
        serp_parser = IndeedSerpParser() if scraper_input.track_serp else None

        # Normalize company names for matching
        normalized_my_companies = set()
        if scraper_input.my_company_names:
            normalized_my_companies = {normalize_company_name(name) for name in scraper_input.my_company_names}

        while len(self.seen_urls) < scraper_input.results_wanted + scraper_input.offset:
            log.info(
                f"search page: {page} / {math.ceil(scraper_input.results_wanted / self.jobs_per_page)}"
            )
            jobs, cursor = self._scrape_page(cursor, page - 1, serp_parser, normalized_my_companies)
            if not jobs:
                log.info(f"found no jobs on page: {page}")
                break
            job_list += jobs
            page += 1
        return JobResponse(
            jobs=job_list[
                scraper_input.offset : scraper_input.offset
                + scraper_input.results_wanted
            ]
        )

    def _scrape_page(
        self,
        cursor: Optional[str],
        page_index: int,
        serp_parser: Optional[IndeedSerpParser],
        normalized_my_companies: set[str]
    ) -> Tuple[List[JobPost], Optional[str]]:
        """Scrapes a page of Indeed for jobs with scraper_input criteria.

        :param cursor:
        :return: jobs found on page, next page cursor.
        """
        jobs: list[JobPost] = []
        new_cursor = None
        filters = self._build_filters()
        search_term = (
            self.scraper_input.search_term.replace('"', '\\"')
            if self.scraper_input and self.scraper_input.search_term
            else ""
        )
        query = job_search_query.format(
            what=(f'what: "{search_term}"' if search_term else ""),
            location=(
                f'location: {{where: "{self.scraper_input.location if self.scraper_input else ""}", '
                f'radius: {self.scraper_input.distance if self.scraper_input else 0}, radiusUnit: MILES}}'
                if self.scraper_input and self.scraper_input.location
                else ""
            ),
            dateOnIndeed=self.scraper_input.hours_old if self.scraper_input else None,
            cursor=f'cursor: "{cursor}"' if cursor else "",
            filters=filters,
        )
        payload = {
            "query": query,
        }
        api_headers_temp = api_headers.copy()
        api_headers_temp["indeed-co"] = self.api_country_code or ""
        response = self.session.post(
            self.api_url,
            headers=api_headers_temp,
            json=payload,
            timeout=10,
            verify=False,
        )
        if not response.ok:
            log.info(
                f"responded with status code: {response.status_code} (submit GitHub issue if this appears to be a bug)"
            )
            return jobs, new_cursor
        data = response.json()
        job_results: list[dict[str, Any]] = data["data"]["jobSearch"]["results"]
        new_cursor = data["data"]["jobSearch"]["pageInfo"]["nextCursor"]

        # Parse SERP items if tracking is enabled
        serp_items = []
        if serp_parser:
            serp_items = serp_parser.parse_serp_items(job_results, page_index)
            # Create a mapping from job_id to SERP item
            serp_map = {item.job_id: item for item in serp_items}
        else:
            serp_map = {}

        job_list: list[JobPost] = []
        for job_result in job_results:
            job = job_result["job"]
            processed_job = self._process_job(job)
            if processed_job:
                # Add SERP tracking data if available
                job_id = job.get("key", "")
                if job_id in serp_map:
                    serp_item = serp_map[job_id]
                    processed_job.serp_page_index = serp_item.page_index
                    processed_job.serp_index_on_page = serp_item.index_on_page
                    # Indeed typically shows 15 jobs per page
                    processed_job.serp_absolute_rank = serp_item.absolute_rank_with_page_size(15)
                    processed_job.serp_page_size_observed = len(serp_items)
                    processed_job.serp_is_sponsored = serp_item.is_sponsored

                    # Add company matching
                    if processed_job.company_name:
                        processed_job.company_normalized = normalize_company_name(processed_job.company_name)
                        processed_job.is_my_company = is_my_company(processed_job.company_name, normalized_my_companies)

                job_list.append(processed_job)

        return job_list, new_cursor

    def _is_job_remote_indeed(self, job: dict[str, Any], description: str) -> bool:
        """Checks if a job is remote using Indeed-specific data sources."""
        # Check attributes for remote indicators
        attributes_text = " ".join(attr["label"] for attr in job.get("attributes", []))

        # Check location for remote indicators
        location_text = job.get("location", {}).get("formatted", {}).get("long", "")

        # Check title for remote indicators
        title = job.get("title", "")

        return is_remote_job(title, description or "", f"{attributes_text} {location_text}")

    def _build_filters(self) -> str:
        """Build filters dict for job type/is_remote.

        If hours_old is provided, composite filter for job_type/is_remote is not possible.
        IndeedApply: filters: { keyword: { field: "indeedApplyScope", keys: ["DESKTOP"] } }.
        """
        filters_str = ""
        if self.scraper_input and self.scraper_input.hours_old:
            filters_str = f"""
            filters: {{
                date: {{
                  field: "dateOnIndeed",
                  start: "{self.scraper_input.hours_old if self.scraper_input else ''}h"
                }}
            }}
            """
        elif self.scraper_input and self.scraper_input.easy_apply:
            filters_str = """
            filters: {
                keyword: {
                  field: "indeedApplyScope",
                  keys: ["DESKTOP"]
                }
            }
            """
        elif self.scraper_input and (self.scraper_input.job_type or self.scraper_input.is_remote):
            job_type_key_mapping = {
                JobType.FULL_TIME: "CF3CP",
                JobType.PART_TIME: "75GKK",
                JobType.CONTRACT: "NJXCK",
                JobType.INTERNSHIP: "VDTG7",
            }

            keys = []
            if self.scraper_input and self.scraper_input.job_type:
                key = job_type_key_mapping[self.scraper_input.job_type]
                keys.append(key)

            if self.scraper_input and self.scraper_input.is_remote:
                keys.append("DSQF7")

            if keys:
                keys_str = '", "'.join(keys)
                filters_str = f"""
                filters: {{
                  composite: {{
                    filters: [{{
                      keyword: {{
                        field: "attributes",
                        keys: ["{keys_str}"]
                      }}
                    }}]
                  }}
                }}
                """
        return filters_str

    def _process_job(self, job: Dict[str, Any]) -> Optional[JobPost]:
        """Parses the job dict into JobPost model.

        :param job: dict to parse
        :return: JobPost if it's a new job.
        """
        job_url = f'{self.base_url}/viewjob?jk={job["key"]}'
        if job_url in self.seen_urls:
            return None
        self.seen_urls.add(job_url)
        description = job["description"]["html"]
        if self.scraper_input and self.scraper_input.description_format == DescriptionFormat.MARKDOWN:
            description = markdown_converter(description)

        job_type = get_job_type(job["attributes"])
        timestamp_seconds = job["datePublished"] / 1000
        date_posted = datetime.fromtimestamp(timestamp_seconds).strftime("%Y-%m-%d")
        employer = job["employer"].get("dossier") if job["employer"] else None
        employer_details = employer.get("employerDetails", {}) if employer else {}
        rel_url = job["employer"]["relativeCompanyPageUrl"] if job["employer"] else None
        return JobPost(
            id=f'in-{job["key"]}',
            title=job["title"],
            description=description,
            company_name=job["employer"].get("name") if job.get("employer") else None,
            company_url=(f"{self.base_url}{rel_url}" if job["employer"] else None),
            company_url_direct=(
                employer["links"]["corporateWebsite"] if employer else None
            ),
            location=Location(
                city=job.get("location", {}).get("city"),
                state=job.get("location", {}).get("admin1Code"),
                country=job.get("location", {}).get("countryCode"),
            ),
            job_type=job_type,
            compensation=get_compensation(job["compensation"]),
            date_posted=date_posted,
            job_url=job_url,
            job_url_direct=(
                job["recruit"].get("viewJobUrl") if job.get("recruit") else None
            ),
            emails=extract_emails_from_text(description) if description else None,
            is_remote=self._is_job_remote_indeed(job, description),
            company_addresses=(
                employer_details["addresses"][0]
                if employer_details.get("addresses")
                else None
            ),
            company_industry=(
                employer_details["industry"]
                .replace("Iv1", "")
                .replace("_", " ")
                .title()
                .strip()
                if employer_details.get("industry")
                else None
            ),
            company_num_employees=employer_details.get("employeesLocalizedLabel"),
            company_revenue=employer_details.get("revenueLocalizedLabel"),
            company_description=employer_details.get("briefDescription"),
            company_logo=(
                employer["images"].get("squareLogoUrl")
                if employer and employer.get("images")
                else None
            ),
        )
