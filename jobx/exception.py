# Copyright (c) 2025 Michelle Pellon. MIT License

"""jobx.exception.

This module contains custom exceptions for the jobx package scrapers.
"""

from typing import Optional


class LinkedInException(Exception):
    """Exception raised for LinkedIn scraping errors."""

    def __init__(self, message: Optional[str] = None) -> None:
        """Initialize LinkedInException with optional message."""
        super().__init__(message or "An error occurred scrapping LinkedIn")
