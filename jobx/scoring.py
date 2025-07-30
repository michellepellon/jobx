# Copyright (c) 2025 Michelle Pellon. MIT License

"""jobx.scoring.

This module implements confidence scoring for job postings based on search query
and location matching. It provides text similarity matching and location proximity
scoring to rank job postings by relevance.
"""

from __future__ import annotations

from difflib import SequenceMatcher

from jobx.model import JobPost


def normalize_text(text: str) -> str:
    """Normalize text for comparison by lowercasing and removing extra whitespace."""
    if not text:
        return ""
    # Remove extra whitespace and lowercase
    return " ".join(text.lower().split())


def calculate_text_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two text strings using SequenceMatcher.

    Returns a float between 0 and 1, where 1 is exact match.
    """
    if not text1 or not text2:
        return 0.0

    # Normalize both texts
    norm_text1 = normalize_text(text1)
    norm_text2 = normalize_text(text2)

    # Use SequenceMatcher for similarity
    return SequenceMatcher(None, norm_text1, norm_text2).ratio()


def calculate_keyword_match_score(query: str, text: str) -> float:
    """Calculate how many keywords from the query appear in the text.

    Returns a score between 0 and 1 based on keyword coverage.
    """
    if not query or not text:
        return 0.0

    # Split query into keywords
    query_keywords = set(normalize_text(query).split())
    text_normalized = normalize_text(text)

    # Count how many query keywords appear in text
    matches = sum(1 for keyword in query_keywords if keyword in text_normalized)

    # Return percentage of keywords matched
    return matches / len(query_keywords) if query_keywords else 0.0


def calculate_title_score(query: str, job_title: str) -> float:
    """Calculate confidence score for job title match.

    Uses a combination of:
    - Direct similarity matching
    - Keyword matching
    - Partial phrase matching
    """
    if not query or not job_title:
        return 0.0

    # Direct similarity
    direct_similarity = calculate_text_similarity(query, job_title)

    # Keyword matching
    keyword_score = calculate_keyword_match_score(query, job_title)

    # Check if query is a substring of title (or vice versa)
    query_norm = normalize_text(query)
    title_norm = normalize_text(job_title)

    substring_bonus = 0.0
    if query_norm in title_norm or title_norm in query_norm:
        substring_bonus = 0.3

    # Weighted combination
    score = (direct_similarity * 0.5) + (keyword_score * 0.3) + substring_bonus

    # Cap at 1.0
    return min(score, 1.0)


def calculate_description_score(query: str, description: str | None) -> float:
    """Calculate confidence score for job description match.

    Focuses on keyword matching since descriptions are typically long.
    """
    if not query or not description:
        return 0.0

    # For descriptions, keyword matching is more relevant than full similarity
    keyword_score = calculate_keyword_match_score(query, description)

    # Also check for exact phrase matches
    query_norm = normalize_text(query)
    desc_norm = normalize_text(description)

    exact_phrase_bonus = 0.2 if query_norm in desc_norm else 0.0

    return min(keyword_score + exact_phrase_bonus, 1.0)


def calculate_location_score(
    search_location: str | None,
    job_location: str | None,
    is_remote: bool | None = False
) -> float:
    """Calculate location matching score.

    Returns:
    - 1.0 for exact matches or remote jobs
    - 0.8 for same city/state matches
    - 0.5 for partial matches
    - 0.0 for no match
    """
    # Remote jobs always get full location score
    if is_remote:
        return 1.0

    if not search_location or not job_location:
        return 0.5  # Unknown location, neutral score

    search_loc_norm = normalize_text(search_location)
    job_loc_norm = normalize_text(job_location)

    # Exact match
    if search_loc_norm == job_loc_norm:
        return 1.0

    # Split location into components (city, state, country)
    search_parts = [p.strip() for p in search_loc_norm.split(',')]
    job_parts = [p.strip() for p in job_loc_norm.split(',')]

    # Check for partial matches
    matching_parts = sum(1 for part in search_parts if any(part in jp for jp in job_parts))

    if matching_parts == len(search_parts):
        return 0.9  # All search parts found
    elif matching_parts > 0:
        return 0.5 + (0.3 * matching_parts / len(search_parts))

    # Check if any part of search location appears in job location
    if any(part in job_loc_norm for part in search_parts):
        return 0.5

    return 0.0


def calculate_confidence_score(
    job: JobPost,
    search_query: str,
    search_location: str | None = None,
    weights: dict[str, float] | None = None
) -> float:
    """Calculate overall confidence score for a job posting.

    Args:
        job: The job posting to score
        search_query: The search query/term used
        search_location: The location searched for
        weights: Optional custom weights for scoring components

    Returns:
        A confidence score between 0 and 1
    """
    # Default weights if not provided
    if weights is None:
        weights = {
            'title': 0.5,      # Title match is most important
            'description': 0.3, # Description match is secondary
            'location': 0.2    # Location match is tertiary
        }

    scores = {}

    # Calculate title score
    scores['title'] = calculate_title_score(search_query, job.title)

    # Calculate description score
    scores['description'] = calculate_description_score(search_query, job.description)

    # Calculate location score
    job_location = job.location.display_location() if job.location else None
    scores['location'] = calculate_location_score(
        search_location,
        job_location,
        job.is_remote
    )

    # Calculate weighted average
    total_score = sum(scores[key] * weights.get(key, 0) for key in scores)

    # Ensure score is between 0 and 1
    return max(0.0, min(1.0, total_score))


def score_jobs(
    jobs: list[JobPost],
    search_query: str,
    search_location: str | None = None,
    weights: dict[str, float] | None = None
) -> list[tuple[JobPost, float]]:
    """Score a list of jobs and return them with their confidence scores.

    Returns:
        List of tuples containing (job, confidence_score), sorted by score descending
    """
    scored_jobs = []

    for job in jobs:
        score = calculate_confidence_score(job, search_query, search_location, weights)
        scored_jobs.append((job, score))

    # Sort by score descending
    scored_jobs.sort(key=lambda x: x[1], reverse=True)

    return scored_jobs

