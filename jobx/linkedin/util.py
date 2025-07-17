# Copyright (c) 2025 Michelle Pellon. MIT License

"""jobx.linkedin.util

This module contains utility functions specific to LinkedIn job scraping,
including job type parsing, location processing, and remote job detection.
"""

from typing import Optional, List

from bs4 import BeautifulSoup

from jobx.model import JobType
from jobx.util import get_enum_from_job_type


def job_type_code(job_type_enum: JobType) -> str:
    """Convert JobType enum to LinkedIn job type code."""
    return {
        JobType.FULL_TIME: "F",
        JobType.PART_TIME: "P",
        JobType.INTERNSHIP: "I",
        JobType.CONTRACT: "C",
        JobType.TEMPORARY: "T",
    }.get(job_type_enum, "")


def parse_job_type(soup_job_type: BeautifulSoup) -> Optional[List[JobType]]:
    """Gets the job type from job page.

    :param soup_job_type:
    :return: JobType.
    """
    h3_tag = soup_job_type.find(
        "h3",
        class_="description__job-criteria-subheader",
        string=lambda text: "Employment type" in text,
    )
    employment_type = None
    if h3_tag:
        employment_type_span = h3_tag.find_next_sibling(
            "span",
            class_="description__job-criteria-text description__job-criteria-text--criteria",
        )
        if employment_type_span:
            employment_type = employment_type_span.get_text(strip=True)
            employment_type = employment_type.lower()
            employment_type = employment_type.replace("-", "")

    if employment_type:
        job_type = get_enum_from_job_type(employment_type)
        return [job_type] if job_type else []
    return []


def parse_job_level(soup_job_level: BeautifulSoup) -> Optional[str]:
    """Gets the job level from job page.

    :param soup_job_level:
    :return: str.
    """
    h3_tag = soup_job_level.find(
        "h3",
        class_="description__job-criteria-subheader",
        string=lambda text: "Seniority level" in text,
    )
    job_level = None
    if h3_tag:
        job_level_span = h3_tag.find_next_sibling(
            "span",
            class_="description__job-criteria-text description__job-criteria-text--criteria",
        )
        if job_level_span:
            job_level = job_level_span.get_text(strip=True)

    return job_level


def parse_company_industry(soup_industry: BeautifulSoup) -> Optional[str]:
    """Gets the company industry from job page.

    :param soup_industry:
    :return: str.
    """
    h3_tag = soup_industry.find(
        "h3",
        class_="description__job-criteria-subheader",
        string=lambda text: "Industries" in text,
    )
    industry = None
    if h3_tag:
        industry_span = h3_tag.find_next_sibling(
            "span",
            class_="description__job-criteria-text description__job-criteria-text--criteria",
        )
        if industry_span:
            industry = industry_span.get_text(strip=True)

    return industry


