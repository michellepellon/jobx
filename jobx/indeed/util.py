# Copyright (c) 2025 Michelle Pellon. MIT License

"""jobx.indeed.util

This module contains utility functions specific to Indeed job scraping,
including compensation parsing, job type extraction, and remote job detection.
"""

from typing import Any

from jobx.model import Compensation, CompensationInterval, JobType
from jobx.util import parse_job_type_enum


def get_job_type(attributes: list[dict[str, Any]]) -> list[JobType]:
    """Parses the attributes to get list of job types.

    :param attributes:
    :return: list of JobType.
    """
    job_types: list[JobType] = []
    for attribute in attributes:
        job_type_str = attribute["label"].replace("-", "").replace(" ", "").lower()
        job_type = parse_job_type_enum(job_type_str)
        if job_type:
            job_types.append(job_type)
    return job_types


def get_compensation(compensation: dict[str, Any]) -> Compensation | None:
    """Parses the job to get compensation.

    :param compensation:
    :return: compensation object.
    """
    if not compensation["baseSalary"] and not compensation["estimated"]:
        return None
    comp = (
        compensation["baseSalary"]
        if compensation["baseSalary"]
        else compensation["estimated"]["baseSalary"]
    )
    if not comp:
        return None
    interval = get_compensation_interval(comp["unitOfWork"])
    if not interval:
        return None
    min_range = comp["range"].get("min")
    max_range = comp["range"].get("max")
    return Compensation(
        interval=interval,
        min_amount=int(min_range) if min_range is not None else None,
        max_amount=int(max_range) if max_range is not None else None,
        currency=(
            compensation["estimated"]["currencyCode"]
            if compensation["estimated"]
            else compensation["currencyCode"]
        ),
    )




def get_compensation_interval(interval: str) -> CompensationInterval:
    """Map interval string to CompensationInterval enum."""
    interval_mapping = {
        "DAY": "DAILY",
        "YEAR": "YEARLY",
        "HOUR": "HOURLY",
        "WEEK": "WEEKLY",
        "MONTH": "MONTHLY",
    }
    mapped_interval = interval_mapping.get(interval.upper(), None)
    if mapped_interval and mapped_interval in CompensationInterval.__members__:
        return CompensationInterval[mapped_interval]
    else:
        raise ValueError(f"Unsupported interval: {interval}")
