# Copyright (c) 2025 Michelle Pellon. MIT License.

"""
Unit tests for CLI functionality.
"""

import argparse
import sys
from unittest.mock import patch

import pandas as pd
import pytest

from jobx.cli import main


@pytest.fixture
def mock_scrape_jobs():
    """Mock scrape_jobs function to return test data."""
    data = {
        "title": ["Software Engineer", "Data Scientist", "ML Engineer"],
        "company": ["Company A", "Company B", "Company C"],
        "location": ["New York", "San Francisco", "Remote"],
        "salary_source": ["direct_data", "description", "direct_data"],
    }
    return pd.DataFrame(data)


class TestCLI:
    """Test CLI functionality."""

    def test_parquet_output_with_file(self, mock_scrape_jobs, tmp_path):
        """Test saving output in Parquet format."""
        output_file = tmp_path / "test_jobs.parquet"

        test_args = [
            "jobx",
            "-q", "python developer",
            "-l", "New York",
            "-o", str(output_file),
            "-f", "parquet",
        ]

        with patch.object(sys, "argv", test_args), \
             patch("jobx.cli.scrape_jobs", return_value=mock_scrape_jobs), \
             patch("sys.exit"):
            main()

        # Verify file was created
        assert output_file.exists()

        # Verify it's a valid Parquet file
        df = pd.read_parquet(output_file)
        assert len(df) == 3
        assert list(df.columns) == ["title", "company", "location", "salary_source"]

    def test_parquet_output_without_file(self):
        """Test that Parquet format requires output file."""
        test_args = [
            "jobx",
            "-q", "python developer",
            "-l", "New York",
            "-f", "parquet",
        ]

        with patch.object(sys, "argv", test_args), \
             patch("jobx.cli.scrape_jobs", return_value=pd.DataFrame({"col": [1, 2]})), \
             patch("sys.exit") as mock_exit, \
             patch("sys.stderr"):
            main()
            mock_exit.assert_called_with(1)

    def test_csv_output_with_file(self, mock_scrape_jobs, tmp_path):
        """Test saving output in CSV format."""
        output_file = tmp_path / "test_jobs.csv"

        test_args = [
            "jobx",
            "-q", "python developer",
            "-l", "New York",
            "-o", str(output_file),
            "-f", "csv",
        ]

        with patch.object(sys, "argv", test_args), \
             patch("jobx.cli.scrape_jobs", return_value=mock_scrape_jobs), \
             patch("sys.exit"):
            main()

        # Verify file was created
        assert output_file.exists()

        # Verify it's a valid CSV file
        df = pd.read_csv(output_file)
        assert len(df) == 3
        assert list(df.columns) == ["title", "company", "location", "salary_source"]

    def test_csv_output_to_stdout(self, mock_scrape_jobs, capsys):
        """Test CSV output to stdout (default behavior)."""
        test_args = [
            "jobx",
            "-q", "python developer",
            "-l", "New York",
        ]

        with patch.object(sys, "argv", test_args), \
             patch("jobx.cli.scrape_jobs", return_value=mock_scrape_jobs), \
             patch("sys.exit"):
            main()

        captured = capsys.readouterr()
        assert "Software Engineer" in captured.out
        assert "Company A" in captured.out

    def test_verbose_output_with_parquet(self, mock_scrape_jobs, tmp_path, capsys):
        """Test verbose output when saving Parquet file."""
        output_file = tmp_path / "test_jobs.parquet"

        test_args = [
            "jobx",
            "-q", "python developer",
            "-l", "New York",
            "-o", str(output_file),
            "-f", "parquet",
            "-v",
        ]

        with patch.object(sys, "argv", test_args), \
             patch("jobx.cli.scrape_jobs", return_value=mock_scrape_jobs), \
             patch("sys.exit"):
            main()

        captured = capsys.readouterr()
        assert "Saved 3 jobs to" in captured.out
        assert "in parquet format" in captured.out

    def test_format_choice_validation(self):
        """Test that only valid format choices are accepted."""
        parser = argparse.ArgumentParser()
        parser.add_argument("-f", "--format", choices=["csv", "parquet"], default="csv")

        # Valid formats
        args = parser.parse_args(["-f", "csv"])
        assert args.format == "csv"

        args = parser.parse_args(["-f", "parquet"])
        assert args.format == "parquet"

        # Invalid format should raise error
        with pytest.raises(SystemExit):
            parser.parse_args(["-f", "json"])
