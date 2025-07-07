# Copyright (c) 2025 Michelle Pellon. MIT License

"""jobx.exception.

This module contains custom exceptions for the jobx package scrapers.
"""


class LinkedInException(Exception):
    """Exception raised for LinkedIn scraping errors."""

    def __init__(self, message: str | None = None) -> None:
        """Initialize LinkedInException with optional message."""
        super().__init__(message or "An error occurred scrapping LinkedIn")
