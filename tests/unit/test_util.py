# Copyright (c) 2025 Michelle Pellon. MIT License..

"""
Unit tests for jobx.util module.
"""

import json
import logging
from unittest.mock import patch

import pytest

from jobx.util import (
    LogConfig,
    create_logger,
    currency_parser,
    extract_salary,
    is_remote_job,
    parse_job_type_enum,
)
from jobx.model import JobType


class TestLogConfig:
    """Test LogConfig dataclass."""
    
    def test_default_values(self):
        """Test default LogConfig values."""
        config = LogConfig()
        assert config.use_json is False
        assert config.level == "INFO"
        assert config.include_context is True
    
    def test_from_env_defaults(self):
        """Test LogConfig.from_env with default environment."""
        with patch.dict("os.environ", {}, clear=True):
            config = LogConfig.from_env()
            assert config.use_json is False
            assert config.level == "INFO"
            assert config.include_context is True
    
    def test_from_env_custom(self):
        """Test LogConfig.from_env with custom environment."""
        env_vars = {
            "JOBX_LOG_JSON": "true",
            "JOBX_LOG_LEVEL": "DEBUG",
            "JOBX_LOG_CONTEXT": "false",
        }
        with patch.dict("os.environ", env_vars):
            config = LogConfig.from_env()
            assert config.use_json is True
            assert config.level == "DEBUG"
            assert config.include_context is False


class TestCreateLogger:
    """Test logger creation functionality."""
    
    def test_create_logger_basic(self):
        """Test basic logger creation."""
        logger = create_logger("test")
        assert logger.name == "JobX:test"
        assert len(logger.handlers) > 0
    
    def test_create_logger_json_format(self):
        """Test logger creation with JSON format."""
        logger = create_logger("test_json", use_json=True)
        assert logger.name == "JobX:test_json"
        # Check that JSON formatter is used
        formatter = logger.handlers[0].formatter
        assert hasattr(formatter, "format")


class TestCurrencyParser:
    """Test currency parsing functionality."""
    
    def test_currency_parser_basic(self):
        """Test basic currency parsing."""
        assert currency_parser("$50,000") == 50000.0
        assert currency_parser("€75,500.50") == 75500.50
        assert currency_parser("£40000") == 40000.0
    
    def test_currency_parser_edge_cases(self):
        """Test currency parser edge cases."""
        assert currency_parser("100") == 100.0
        assert currency_parser("1,000.00") == 1000.0


class TestExtractSalary:
    """Test salary extraction functionality."""
    
    def test_extract_salary_range(self):
        """Test extracting salary range."""
        text = "Salary: $80,000 - $120,000 per year"
        interval, min_amt, max_amt, currency = extract_salary(text)
        assert interval == "yearly"
        assert min_amt == 80000
        assert max_amt == 120000
        assert currency == "USD"
    
    def test_extract_salary_hourly(self):
        """Test extracting hourly salary."""
        text = "Hourly rate: $25 - $35 per hour"
        interval, min_amt, max_amt, currency = extract_salary(text)
        assert interval == "hourly"
        assert min_amt == 25
        assert max_amt == 35
        assert currency == "USD"
    
    def test_extract_salary_none(self):
        """Test salary extraction returns None for invalid input."""
        result = extract_salary("")
        assert result == (None, None, None, None)
        
        result = extract_salary("No salary mentioned")
        assert result == (None, None, None, None)


class TestIsRemoteJob:
    """Test remote job detection."""
    
    def test_is_remote_job_positive(self):
        """Test detecting remote jobs."""
        assert is_remote_job("Remote Software Engineer", "", "")
        assert is_remote_job("", "Work from home opportunity", "")
        assert is_remote_job("", "", "Remote location")
        assert is_remote_job("", "WFH position available", "")
    
    def test_is_remote_job_negative(self):
        """Test non-remote job detection."""
        assert not is_remote_job("On-site Engineer", "Office based role", "New York")
        assert not is_remote_job("", "", "")
    
    def test_is_remote_job_case_insensitive(self):
        """Test case insensitive remote detection."""
        assert is_remote_job("REMOTE position", "", "")
        assert is_remote_job("", "WORK FROM HOME", "")


class TestParseJobTypeEnum:
    """Test job type enum parsing."""
    
    def test_parse_job_type_enum_success(self):
        """Test successful job type parsing."""
        assert parse_job_type_enum("fulltime") == JobType.FULL_TIME
        assert parse_job_type_enum("part-time") == JobType.PART_TIME
        assert parse_job_type_enum("contract") == JobType.CONTRACT
        assert parse_job_type_enum("internship") == JobType.INTERNSHIP
    
    def test_parse_job_type_enum_normalization(self):
        """Test job type string normalization."""
        assert parse_job_type_enum("Full Time") == JobType.FULL_TIME
        assert parse_job_type_enum("part-time") == JobType.PART_TIME
        assert parse_job_type_enum("CONTRACT") == JobType.CONTRACT
    
    def test_parse_job_type_enum_none(self):
        """Test job type parsing returns None for invalid input."""
        assert parse_job_type_enum(None) is None
        assert parse_job_type_enum("") is None
        assert parse_job_type_enum("invalid") is None