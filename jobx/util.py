# Copyright (c) 2025 Michelle Pellon. MIT License

"""jobx.util.

This module contains utility functions and classes used throughout the jobx package.
It provides HTTP session management, data parsing, logging configuration, and
various helper functions for processing job data.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from itertools import cycle
from typing import Any

import numpy as np
import pricetag
import requests
import tls_client
import urllib3
from markdownify import markdownify as md
from requests.adapters import HTTPAdapter, Retry

from jobx.model import CompensationInterval, JobType, Site

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Salary processing constants
HOURS_PER_YEAR = 2080
MONTHS_PER_YEAR = 12
WEEKS_PER_YEAR = 52
DAYS_PER_YEAR = 260
HOURLY_THRESHOLD = 350
MONTHLY_THRESHOLD = 30000
MIN_SALARY_LIMIT = 1000
MAX_SALARY_LIMIT = 700000


@dataclass(frozen=True)
class LogConfig:
    """Configuration for logging setup."""

    use_json: bool = False
    level: str = "INFO"
    include_context: bool = True

    @classmethod
    def from_env(cls) -> LogConfig:
        """Create LogConfig from environment variables."""
        return cls(
            use_json=os.getenv("JOBX_LOG_JSON", "false").lower() == "true",
            level=os.getenv("JOBX_LOG_LEVEL", "INFO").upper(),
            include_context=os.getenv("JOBX_LOG_CONTEXT", "true").lower() == "true"
        )


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields if they exist
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def create_logger(name: str, use_json: bool | None = None) -> logging.Logger:
    """Create a structured logger with optional JSON output.

    Args:
        name: Logger name suffix (will be prefixed with 'JobX:')
        use_json: If True, use JSON formatting. If None, check environment variable.

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(f"JobX:{name}")
    logger.propagate = False

    if not logger.handlers:
        logger.setLevel(logging.INFO)
        console_handler = logging.StreamHandler()

        # Determine format based on parameter or environment
        if use_json is None:
            use_json = os.getenv("JOBX_LOG_JSON", "false").lower() == "true"

        formatter: logging.Formatter
        if use_json:
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
            )

        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def log_with_context(logger: logging.Logger, level: int, message: str, **kwargs: Any) -> None:
    """Log a message with additional context data.

    Args:
        logger: Logger instance
        level: Log level (e.g., logging.INFO)
        message: Log message
        **kwargs: Additional context data
    """
    # Create a custom log record with extra data
    record = logger.makeRecord(
        logger.name, level, "", 0, message, (), None
    )
    record.extra_data = kwargs
    logger.handle(record)


class RotatingProxySession:
    """Base class for rotating proxy sessions."""

    proxy_cycle: Iterator[dict[str, str]] | None

    def __init__(self, proxies: list[str] | str | None = None) -> None:
        """Initialize RotatingProxySession with optional proxies."""
        if isinstance(proxies, str):
            self.proxy_cycle = cycle([self.format_proxy(proxies)])
        elif isinstance(proxies, list):
            self.proxy_cycle = (
                cycle([self.format_proxy(proxy) for proxy in proxies])
                if proxies
                else None
            )
        else:
            self.proxy_cycle = None

    @staticmethod
    def format_proxy(proxy: str) -> dict[str, str]:
        """Utility method to format a proxy string into a dictionary."""
        if proxy.startswith("http://") or proxy.startswith("https://"):
            return {"http": proxy, "https": proxy}
        if proxy.startswith("socks5://"):
            return {"http": proxy, "https": proxy}
        return {"http": f"http://{proxy}", "https": f"http://{proxy}"}


class RequestsRotating(RotatingProxySession, requests.Session):
    """Requests session with rotating proxy support."""

    def __init__(self, proxies: list[str] | str | None = None, has_retry: bool = False,
                 delay: int = 1, clear_cookies: bool = False) -> None:
        """Initialize RequestsRotating session."""
        RotatingProxySession.__init__(self, proxies=proxies)
        requests.Session.__init__(self)
        self.clear_cookies = clear_cookies
        self.allow_redirects = True
        self.setup_session(has_retry, delay)

    def setup_session(self, has_retry: bool, delay: int) -> None:
        """Set up session with retry configuration."""
        if has_retry:
            retries = Retry(
                total=3,
                connect=3,
                status=3,
                status_forcelist=[500, 502, 503, 504, 429],
                backoff_factor=delay,
            )
            adapter = HTTPAdapter(max_retries=retries)
            self.mount("http://", adapter)
            self.mount("https://", adapter)

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:  # type: ignore[override]
        """Make request with proxy rotation."""
        if self.clear_cookies:
            self.cookies.clear()

        if self.proxy_cycle:
            next_proxy = next(self.proxy_cycle)
            if next_proxy["http"] != "http://localhost":
                self.proxies = next_proxy
            else:
                self.proxies = {}
        return requests.Session.request(self, method, url, **kwargs)


class TLSRotating(RotatingProxySession, tls_client.Session):  # type: ignore[misc]
    """TLS client session with rotating proxy support."""

    def __init__(self, proxies: list[str] | str | None = None) -> None:
        """Initialize TLSRotating session."""
        RotatingProxySession.__init__(self, proxies=proxies)
        tls_client.Session.__init__(self, random_tls_extension_order=True)

    def execute_request(self, *args: Any, **kwargs: Any) -> Any:
        """Execute request with proxy rotation."""
        if self.proxy_cycle:
            next_proxy = next(self.proxy_cycle)
            if next_proxy["http"] != "http://localhost":
                self.proxies = next_proxy
            else:
                self.proxies = {}
        response = tls_client.Session.execute_request(self, *args, **kwargs)
        response.ok = response.status_code in range(200, 400)
        return response


def create_session(
    *,
    proxies: list[str] | str | None = None,
    ca_cert: str | None = None,
    is_tls: bool = True,
    has_retry: bool = False,
    delay: int = 1,
    clear_cookies: bool = False,
    use_stealth: bool = False,
) -> requests.Session | TLSRotating:
    """Creates a requests session with optional tls, proxy, and retry settings.

    Args:
        proxies: Proxy configuration
        ca_cert: CA certificate path
        is_tls: Whether to use TLS client
        has_retry: Whether to enable retries
        delay: Delay between retries
        clear_cookies: Whether to clear cookies between requests
        use_stealth: Whether to wrap session with anti-detection features

    :return: A session object, optionally wrapped with StealthSession.
    """
    session: requests.Session | TLSRotating
    if is_tls:
        session = TLSRotating(proxies=proxies)
    else:
        session = RequestsRotating(
            proxies=proxies,
            has_retry=has_retry,
            delay=delay,
            clear_cookies=clear_cookies,
        )

    if ca_cert:
        session.verify = ca_cert

    # Wrap with stealth features if requested
    if use_stealth:
        from jobx.anti_detection import (
            StealthSession,
            UserAgentRotator,
            IntelligentDelayManager,
            ProxyRotator,
        )
        
        # Set up anti-detection components
        user_agent_rotator = UserAgentRotator()
        delay_manager = IntelligentDelayManager(base_delay=delay)
        
        # Set up proxy rotation if proxies provided
        proxy_rotator = None
        if proxies:
            proxy_list = [proxies] if isinstance(proxies, str) else proxies
            proxy_rotator = ProxyRotator(proxy_list)
        
        # Return wrapped session
        return StealthSession(
            session=session,
            user_agent_rotator=user_agent_rotator,
            delay_manager=delay_manager,
            proxy_rotator=proxy_rotator,
        )

    return session


@contextmanager
def managed_session(
    *,
    proxies: list[str] | str | None = None,
    ca_cert: str | None = None,
    is_tls: bool = True,
    has_retry: bool = False,
    delay: int = 1,
    clear_cookies: bool = False,
    use_stealth: bool = False,
) -> Generator[requests.Session | TLSRotating]:
    """Context manager for HTTP sessions with proper cleanup.

    Args:
        proxies: Proxy configuration
        ca_cert: CA certificate path
        is_tls: Whether to use TLS client
        has_retry: Whether to enable retries
        delay: Delay between retries
        clear_cookies: Whether to clear cookies between requests
        use_stealth: Whether to enable anti-detection features

    Yields:
        Configured session instance

    Example:
        with managed_session(has_retry=True, use_stealth=True) as session:
            response = session.get("https://example.com")
    """
    session = create_session(
        proxies=proxies,
        ca_cert=ca_cert,
        is_tls=is_tls,
        has_retry=has_retry,
        delay=delay,
        clear_cookies=clear_cookies,
        use_stealth=use_stealth,
    )

    try:
        yield session
    except Exception as e:
        # Log the exception with context
        logger = create_logger("session")
        log_with_context(
            logger, logging.ERROR, "Session error occurred",
            error=str(e),
            error_type=type(e).__name__,
            proxies=bool(proxies),
            is_tls=is_tls
        )
        raise
    finally:
        # Ensure session is properly closed
        with contextlib.suppress(Exception):
            session.close()


@contextmanager
def handle_scraping_errors(
    operation: str,
    site: str | None = None,
    **context_data: Any
) -> Generator[None]:
    """Context manager for handling scraping operation errors.

    Args:
        operation: Description of the operation being performed
        site: Name of the site being scraped
        **context_data: Additional context data for logging

    Example:
        with handle_scraping_errors("job parsing", site="LinkedIn", job_id="123"):
            # Parse job data that might fail
            job_data = parse_complex_job_data(raw_data)
    """
    logger = create_logger(site or "scraper")

    try:
        yield
    except Exception as e:
        # Log the error with full context
        log_with_context(
            logger, logging.ERROR, f"Error during {operation}",
            error=str(e),
            error_type=type(e).__name__,
            operation=operation,
            site=site,
            **context_data
        )
        # Re-raise the exception to allow caller to handle it
        raise


def set_logger_level(verbose: int | None) -> None:
    """Adjusts the logger's level. This function allows the logging level to be changed at runtime.

    Parameters:
    - verbose: int {0, 1, 2} (default=2, all logs)
    """
    if verbose is None:
        return
    level_name = {2: "INFO", 1: "WARNING", 0: "ERROR"}.get(verbose, "INFO")
    level = getattr(logging, level_name.upper(), None)
    if level is not None:
        for logger_name in logging.root.manager.loggerDict:
            if logger_name.startswith("JobX:"):
                logging.getLogger(logger_name).setLevel(level)

        # Also set the base JobX logger level if it exists
        base_logger = logging.getLogger("JobX")
        if base_logger.handlers:
            base_logger.setLevel(level)
    else:
        raise ValueError(f"Invalid log level: {level_name}")


def markdown_converter(description_html: str | None) -> str | None:
    """Convert HTML description to markdown format."""
    if description_html is None:
        return None
    markdown = md(description_html)
    return str(markdown).strip()


def extract_emails_from_text(text: str) -> list[str] | None:
    """Extract email addresses from text using regex."""
    if not text:
        return None
    email_regex = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    return email_regex.findall(text)


def parse_job_type_enum(job_type_str: str | None) -> JobType | None:
    """Given a string, returns the corresponding JobType enum member if a match is found.

    Returns None if no match is found or if job_type_str is None.
    """
    if not job_type_str:
        return None

    job_type_str = job_type_str.lower().replace("-", "").replace(" ", "")
    for job_type in JobType:
        if job_type_str in job_type.value:
            return job_type
    return None


def get_enum_from_job_type(job_type_str: str) -> JobType | None:
    """Deprecated: Use parse_job_type_enum instead.

    Given a string, returns the corresponding JobType enum member if a match is found.
    """
    return parse_job_type_enum(job_type_str)


def currency_parser(cur_str: str) -> float:
    """Parse currency string to float value."""
    # Remove any non-numerical characters
    # except for ',' '.' or '-' (e.g. EUR)
    cur_str = re.sub("[^-0-9.,]", "", cur_str)
    # Remove any 000s separators (either , or .)
    cur_str = re.sub("[.,]", "", cur_str[:-3]) + cur_str[-3:]

    if "." in list(cur_str[-3:]):
        num = float(cur_str)
    elif "," in list(cur_str[-3:]):
        num = float(cur_str.replace(",", "."))
    else:
        num = float(cur_str)

    return float(np.round(num, 2))


def remove_attributes(tag: Any) -> Any:
    """Remove all attributes from a BeautifulSoup tag."""
    for attr in list(tag.attrs):
        del tag[attr]
    return tag


def extract_salary(
    salary_str: str | None,
    lower_limit: float = MIN_SALARY_LIMIT,
    upper_limit: float = MAX_SALARY_LIMIT,
    hourly_threshold: float = HOURLY_THRESHOLD,
    monthly_threshold: float = MONTHLY_THRESHOLD,
    enforce_annual_salary: bool = False,
) -> tuple[str | None, float | None, float | None, str | None]:
    """Extract salary information from a string using pricetag library.

    Returns the salary interval, min and max salary values, and currency.
    """
    if not salary_str:
        return None, None, None, None

    # Create pricetag extractor with configuration
    extractor = pricetag.PriceExtractor(
        normalize_to_annual=False,  # We'll handle normalization ourselves
        min_salary=lower_limit,
        max_salary=upper_limit,
        assume_hours_per_year=HOURS_PER_YEAR,
    )

    # Extract price information
    results = extractor.extract(salary_str)

    if not results:
        return None, None, None, None

    # Get the first extracted price
    result = results[0]

    # Extract values from pricetag result
    if isinstance(result['value'], tuple):
        min_salary = result['value'][0]
        max_salary = result['value'][1]
    else:
        min_salary = result['value']
        max_salary = result['value']

    currency = result.get('currency', 'USD')

    # Determine interval based on type from pricetag
    type_mapping = {
        "hourly": CompensationInterval.HOURLY.value,
        "daily": CompensationInterval.DAILY.value,
        "weekly": CompensationInterval.WEEKLY.value,
        "monthly": CompensationInterval.MONTHLY.value,
        "yearly": CompensationInterval.YEARLY.value,
        "annual": CompensationInterval.YEARLY.value,
    }

    # Get interval from pricetag type
    interval = type_mapping.get(result.get('type', ''), None)

    if not interval:
        # Fall back to threshold-based detection
        if min_salary is not None:
            if min_salary < hourly_threshold:
                interval = CompensationInterval.HOURLY.value
            elif min_salary < monthly_threshold:
                interval = CompensationInterval.MONTHLY.value
            else:
                interval = CompensationInterval.YEARLY.value
        else:
            # Default to yearly if no salary to check
            interval = CompensationInterval.YEARLY.value

    # Convert to annual if requested
    if enforce_annual_salary:
        # Check for None values before calculations
        if min_salary is None or max_salary is None:
            return None, None, None, None
            
        annual_min_salary = min_salary
        annual_max_salary = max_salary

        if interval == CompensationInterval.HOURLY.value:
            annual_min_salary = min_salary * HOURS_PER_YEAR
            annual_max_salary = max_salary * HOURS_PER_YEAR
        elif interval == CompensationInterval.DAILY.value:
            annual_min_salary = min_salary * DAYS_PER_YEAR
            annual_max_salary = max_salary * DAYS_PER_YEAR
        elif interval == CompensationInterval.WEEKLY.value:
            annual_min_salary = min_salary * WEEKS_PER_YEAR
            annual_max_salary = max_salary * WEEKS_PER_YEAR
        elif interval == CompensationInterval.MONTHLY.value:
            annual_min_salary = min_salary * MONTHS_PER_YEAR
            annual_max_salary = max_salary * MONTHS_PER_YEAR

        # Validate against limits
        if (
            lower_limit <= annual_min_salary <= upper_limit
            and lower_limit <= annual_max_salary <= upper_limit
            and annual_min_salary <= annual_max_salary
        ):
            return interval, annual_min_salary, annual_max_salary, currency
        else:
            return None, None, None, None
    else:
        # Check for None values before calculations
        if min_salary is None or max_salary is None:
            return None, None, None, None
            
        # Validate against limits (check annualized values)
        check_min = min_salary
        check_max = max_salary

        if interval == CompensationInterval.HOURLY.value:
            check_min = min_salary * HOURS_PER_YEAR
            check_max = max_salary * HOURS_PER_YEAR
        elif interval == CompensationInterval.DAILY.value:
            check_min = min_salary * DAYS_PER_YEAR
            check_max = max_salary * DAYS_PER_YEAR
        elif interval == CompensationInterval.WEEKLY.value:
            check_min = min_salary * WEEKS_PER_YEAR
            check_max = max_salary * WEEKS_PER_YEAR
        elif interval == CompensationInterval.MONTHLY.value:
            check_min = min_salary * MONTHS_PER_YEAR
            check_max = max_salary * MONTHS_PER_YEAR

        if (
            lower_limit <= check_min <= upper_limit
            and lower_limit <= check_max <= upper_limit
            and check_min <= check_max
        ):
            return interval, min_salary, max_salary, currency
        else:
            return None, None, None, None




def is_remote_job(title: str = "", description: str = "", location: str = "") -> bool:
    """Detects if a job is remote based on title, description, and location."""
    remote_keywords = ["remote", "work from home", "wfh"]
    combined_text = f"{title} {description} {location}".lower()
    return any(keyword in combined_text for keyword in remote_keywords)


def map_str_to_site(site_name: str) -> Site:
    """Map string to Site enum value."""
    return Site[site_name.upper()]


def get_enum_from_value(value_str: str) -> JobType:
    """Deprecated: Use parse_job_type_enum instead."""
    result = parse_job_type_enum(value_str)
    if result is None:
        raise Exception(f"Invalid job type: {value_str}")
    return result


def convert_to_annual(job_data: dict[str, Any]) -> None:
    """Convert job salary data to annual amounts."""
    if job_data["interval"] == "hourly":
        job_data["min_amount"] *= HOURS_PER_YEAR
        job_data["max_amount"] *= HOURS_PER_YEAR
    if job_data["interval"] == "monthly":
        job_data["min_amount"] *= MONTHS_PER_YEAR
        job_data["max_amount"] *= MONTHS_PER_YEAR
    if job_data["interval"] == "weekly":
        job_data["min_amount"] *= WEEKS_PER_YEAR
        job_data["max_amount"] *= WEEKS_PER_YEAR
    if job_data["interval"] == "daily":
        job_data["min_amount"] *= DAYS_PER_YEAR
        job_data["max_amount"] *= DAYS_PER_YEAR
    job_data["interval"] = "yearly"


desired_order = [
    "uuid",
    "site",
    "job_url_direct",
    "title",
    "company",
    "location",
    "postal_code",
    "date_posted",
    "job_type",
    "interval",
    "min_amount",
    "max_amount",
    "currency",
    "confidence_score",
    "emails",
    "description",
    "company_url",
]

column_renames = {
    "uuid": "id",
    "site": "source_job_board",
    "job_url_direct": "url",
    "company": "company_name",
    "job_type": "type",
    "postal_code": "zip_code",
}
