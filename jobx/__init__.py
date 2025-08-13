# Copyright (c) 2025 Michelle Pellon. MIT License

"""jobx

A job scraper for LinkedIn and Indeed. This package provides a unified interface
for scraping job listings from multiple job boards with support for filtering,
concurrent execution, and data normalization.
"""

# Standard library dependencies
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, List, Optional, Union

# Third-party dependencies
import pandas as pd

# Internal dependencies
from jobx.indeed import Indeed
from jobx.linkedin import LinkedIn
from jobx.model import Country, JobResponse, Location, SalarySource, ScraperInput, Site
from jobx.scoring import calculate_confidence_score
from jobx.util import (
    convert_to_annual,
    create_logger,
    desired_order,
    extract_salary,
    get_enum_from_value,
    log_with_context,
    map_str_to_site,
    set_logger_level,
)

# Hatch (or Bumpver) treats __version__ as the *single source of truth*.
# When you run `hatch version minor` (or similar), this value is bumped
# and committed automatically.
__version__: str = "0.1.0"

def scrape_jobs(
    site_name: Union[str, List[str], Site, List[Site], None] = None,
    search_term: Optional[str] = None,
    google_search_term: Optional[str] = None,
    location: Optional[str] = None,
    distance: Optional[int] = 50,
    is_remote: bool = False,
    job_type: Optional[str] = None,
    easy_apply: Optional[bool] = None,
    results_wanted: int = 15,
    country_indeed: str = "usa",
    proxies: Union[List[str], str, None] = None,
    ca_cert: Optional[str] = None,
    description_format: str = "markdown",
    linkedin_fetch_description: Optional[bool] = False,
    linkedin_company_ids: Optional[List[int]] = None,
    offset: Optional[int] = 0,
    hours_old: Optional[int] = None,
    enforce_annual_salary: bool = False,
    verbose: int = 0,
    track_serp: bool = False,
    my_company_names: Optional[List[str]] = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """Scrapes job data from job boards concurrently.

    :return: Pandas DataFrame containing job data
    """
    SCRAPER_MAPPING = {
        Site.LINKEDIN: LinkedIn,
        Site.INDEED: Indeed,
    }
    set_logger_level(verbose)
    job_type_enum = get_enum_from_value(job_type) if job_type else None

    def get_site_type() -> list[Site]:
        site_types = list(Site)
        if isinstance(site_name, str):
            site_types = [map_str_to_site(site_name)]
        elif isinstance(site_name, Site):
            site_types = [site_name]
        elif isinstance(site_name, list):
            site_types = [
                map_str_to_site(site) if isinstance(site, str) else site
                for site in site_name
            ]
        return site_types

    country_enum = Country.from_string(country_indeed)

    scraper_input = ScraperInput(
        site_type=get_site_type(),
        country=country_enum,
        search_term=search_term,
        google_search_term=google_search_term,
        location=location,
        distance=distance,
        is_remote=is_remote,
        job_type=job_type_enum,
        easy_apply=easy_apply,
        description_format=description_format,
        linkedin_fetch_description=linkedin_fetch_description,
        results_wanted=results_wanted,
        linkedin_company_ids=linkedin_company_ids,
        offset=offset,
        hours_old=hours_old,
        track_serp=track_serp,
        my_company_names=my_company_names,
    )

    def scrape_site(site: Site) -> tuple[str, JobResponse]:
        scraper_class = SCRAPER_MAPPING[site]
        scraper = scraper_class(proxies=proxies, ca_cert=ca_cert)
        scraped_data: JobResponse = scraper.scrape(scraper_input)
        site_name = site.value.capitalize()
        site_logger = create_logger(site_name)
        log_with_context(
            site_logger, logging.INFO, "Finished scraping",
            site=site_name,
            jobs_found=len(scraped_data.jobs)
        )
        return site.value, scraped_data

    site_to_jobs_dict = {}

    def worker(site: Site) -> tuple[str, JobResponse]:
        site_val, scraped_info = scrape_site(site)
        return site_val, scraped_info

    with ThreadPoolExecutor() as executor:
        future_to_site = {
            executor.submit(worker, site): site for site in scraper_input.site_type
        }

        for future in as_completed(future_to_site):
            site_value, scraped_data = future.result()
            site_to_jobs_dict[site_value] = scraped_data

    jobs_dfs: list[pd.DataFrame] = []

    for site, job_response in site_to_jobs_dict.items():
        for job in job_response.jobs:
            job_data = job.dict()
            # job_url = job_data["job_url"]  # Unused variable
            job_data["site"] = site
            job_data["company"] = job_data["company_name"]
            job_data["job_type"] = (
                ", ".join(job_type.value[0] for job_type in job_data["job_type"])
                if job_data["job_type"]
                else None
            )
            job_data["emails"] = (
                ", ".join(job_data["emails"]) if job_data["emails"] else None
            )
            if job_data["location"]:
                job_data["location"] = Location(
                    **job_data["location"]
                ).display_location()

            # Handle compensation
            compensation_obj = job_data.get("compensation")
            if compensation_obj and isinstance(compensation_obj, dict):
                job_data["interval"] = (
                    compensation_obj.get("interval").value
                    if compensation_obj.get("interval")
                    else None
                )
                job_data["min_amount"] = compensation_obj.get("min_amount")
                job_data["max_amount"] = compensation_obj.get("max_amount")
                job_data["currency"] = compensation_obj.get("currency", "USD")
                job_data["salary_source"] = SalarySource.DIRECT_DATA.value
                if enforce_annual_salary and (
                    job_data["interval"]
                    and job_data["interval"] != "yearly"
                    and job_data["min_amount"]
                    and job_data["max_amount"]
                ):
                    convert_to_annual(job_data)
            else:
                if country_enum == Country.USA:
                    (
                        job_data["interval"],
                        job_data["min_amount"],
                        job_data["max_amount"],
                        job_data["currency"],
                    ) = extract_salary(
                        job_data["description"],
                        enforce_annual_salary=enforce_annual_salary,
                    )
                    job_data["salary_source"] = SalarySource.DESCRIPTION.value

            job_data["salary_source"] = (
                job_data["salary_source"]
                if job_data.get("min_amount")
                else None
            )

            # Calculate confidence score
            job_data["confidence_score"] = calculate_confidence_score(
                job,
                search_term or "",
                location
            )

            job_df = pd.DataFrame([job_data])
            jobs_dfs.append(job_df)

    if jobs_dfs:
        # Step 1: Filter out all-NA columns from each DataFrame before concatenation
        filtered_dfs = [df.dropna(axis=1, how="all") for df in jobs_dfs]

        # Step 2: Concatenate the filtered DataFrames
        jobs_df = pd.concat(filtered_dfs, ignore_index=True)

        # Step 3: Ensure all desired columns are present, adding missing ones as empty
        for column in desired_order:
            if column not in jobs_df.columns:
                jobs_df[column] = None  # Add missing columns as empty

        # Reorder the DataFrame according to the desired order
        jobs_df = jobs_df[desired_order]

        # Step 4: Sort the DataFrame by confidence score (descending), then by site and date
        return jobs_df.sort_values(
            by=["confidence_score", "site", "date_posted"], ascending=[False, True, False]
        ).reset_index(drop=True)
    else:
        return pd.DataFrame()
