# Copyright (c) 2025 Michelle Pellon. MIT License

"""Tests for the jobx.scoring module."""

import pytest

from jobx.model import JobPost, Location
from jobx.scoring import (
    calculate_confidence_score,
    calculate_description_score,
    calculate_keyword_match_score,
    calculate_location_score,
    calculate_text_similarity,
    calculate_title_score,
    normalize_text,
    score_jobs,
)


class TestTextUtilities:
    """Test text normalization and similarity functions."""
    
    def test_normalize_text(self):
        """Test text normalization."""
        assert normalize_text("  Hello   World  ") == "hello world"
        assert normalize_text("UPPER CASE") == "upper case"
        assert normalize_text("") == ""
        assert normalize_text(None) == ""
        assert normalize_text("Multiple\n\nNewlines") == "multiple newlines"
    
    def test_calculate_text_similarity(self):
        """Test text similarity calculation."""
        # Exact match
        assert calculate_text_similarity("hello", "hello") == 1.0
        
        # Case insensitive
        assert calculate_text_similarity("Hello", "HELLO") == 1.0
        
        # Completely different
        assert calculate_text_similarity("hello", "goodbye") < 0.5
        
        # Empty strings
        assert calculate_text_similarity("", "") == 0.0
        assert calculate_text_similarity("hello", "") == 0.0
        assert calculate_text_similarity("", "hello") == 0.0
        
        # Similar strings
        similarity = calculate_text_similarity("software engineer", "software developer")
        assert 0.5 < similarity < 1.0


class TestKeywordMatching:
    """Test keyword matching functionality."""
    
    def test_calculate_keyword_match_score(self):
        """Test keyword matching score calculation."""
        # All keywords match
        assert calculate_keyword_match_score("python developer", "python developer needed") == 1.0
        
        # Partial match
        assert calculate_keyword_match_score("python developer", "python needed") == 0.5
        
        # No match
        assert calculate_keyword_match_score("python developer", "java architect") == 0.0
        
        # Empty inputs
        assert calculate_keyword_match_score("", "text") == 0.0
        assert calculate_keyword_match_score("query", "") == 0.0
        
        # Case insensitive
        assert calculate_keyword_match_score("Python Developer", "PYTHON DEVELOPER") == 1.0


class TestTitleScoring:
    """Test job title scoring functionality."""
    
    def test_calculate_title_score(self):
        """Test title scoring calculation."""
        # Exact match should score high
        score = calculate_title_score("software engineer", "Software Engineer")
        assert score > 0.8
        
        # Substring match should get bonus
        score = calculate_title_score("engineer", "Senior Software Engineer")
        assert score > 0.5
        
        # Partial keyword match
        score = calculate_title_score("python developer", "Python Software Engineer")
        assert 0.3 < score < 0.8
        
        # No match should score low
        score = calculate_title_score("python developer", "Java Architect")
        assert score < 0.3
        
        # Empty inputs
        assert calculate_title_score("", "title") == 0.0
        assert calculate_title_score("query", "") == 0.0


class TestDescriptionScoring:
    """Test job description scoring functionality."""
    
    def test_calculate_description_score(self):
        """Test description scoring calculation."""
        description = """
        We are looking for a Python developer with experience in Django and REST APIs.
        The ideal candidate will have strong programming skills and work with our team.
        """
        
        # Good keyword match
        score = calculate_description_score("python django", description)
        assert score > 0.8
        
        # Partial match
        score = calculate_description_score("python java", description)
        assert 0.3 < score < 0.7
        
        # Exact phrase match gets bonus
        score = calculate_description_score("python developer", description)
        assert score > 0.7
        
        # No match
        score = calculate_description_score("ruby rails", description)
        assert score < 0.3
        
        # Empty inputs
        assert calculate_description_score("", description) == 0.0
        assert calculate_description_score("query", "") == 0.0
        assert calculate_description_score("query", None) == 0.0


class TestLocationScoring:
    """Test location scoring functionality."""
    
    def test_calculate_location_score(self):
        """Test location scoring calculation."""
        # Exact match
        assert calculate_location_score("New York, NY", "New York, NY") == 1.0
        
        # Remote jobs always score 1.0
        assert calculate_location_score("New York", "San Francisco", is_remote=True) == 1.0
        
        # City match
        score = calculate_location_score("New York", "New York, NY, USA")
        assert score > 0.8
        
        # Partial match - NY state match
        score = calculate_location_score("New York", "Albany, NY")
        assert score == 0.0  # No common parts between "New York" and "Albany"
        
        # No match
        assert calculate_location_score("New York", "San Francisco") == 0.0
        
        # Empty inputs
        assert calculate_location_score("", "location") == 0.5
        assert calculate_location_score("location", "") == 0.5
        assert calculate_location_score(None, "location") == 0.5
        
        # Case insensitive
        assert calculate_location_score("new york", "NEW YORK") == 1.0


class TestConfidenceScoring:
    """Test overall confidence scoring functionality."""
    
    def test_calculate_confidence_score(self):
        """Test confidence score calculation for a job."""
        job = JobPost(
            title="Python Developer",
            company_name="Tech Company",
            job_url="https://example.com/job/123",
            location=Location(city="New York", state="NY"),
            description="We need a Python developer with Django experience.",
            is_remote=False
        )
        
        # Good match
        score = calculate_confidence_score(job, "python developer", "New York")
        assert score > 0.7
        
        # Partial match
        score = calculate_confidence_score(job, "software engineer", "New York")
        assert 0.2 < score < 0.7
        
        # Poor match
        score = calculate_confidence_score(job, "java architect", "San Francisco")
        assert score < 0.3
        
        # Remote job with location mismatch still scores well
        job.is_remote = True
        score = calculate_confidence_score(job, "python developer", "San Francisco")
        assert score > 0.6
    
    def test_calculate_confidence_score_with_custom_weights(self):
        """Test confidence score with custom weights."""
        job = JobPost(
            title="Python Developer",
            company_name="Tech Company",
            job_url="https://example.com/job/123",
            location=Location(city="New York", state="NY"),
            description="Python developer needed"
        )
        
        # Title weight only
        weights = {'title': 1.0, 'description': 0.0, 'location': 0.0}
        score = calculate_confidence_score(job, "python developer", "San Francisco", weights)
        assert score > 0.8
        
        # Location weight only
        weights = {'title': 0.0, 'description': 0.0, 'location': 1.0}
        score = calculate_confidence_score(job, "java", "New York", weights)
        assert score > 0.8


class TestJobScoring:
    """Test batch job scoring functionality."""
    
    def test_score_jobs(self):
        """Test scoring multiple jobs."""
        jobs = [
            JobPost(
                title="Python Developer",
                company_name="Company A",
                job_url="https://example.com/1",
                location=Location(city="New York"),
                description="Python and Django required"
            ),
            JobPost(
                title="Java Developer",
                company_name="Company B",
                job_url="https://example.com/2",
                location=Location(city="New York"),
                description="Java and Spring required"
            ),
            JobPost(
                title="Senior Python Engineer",
                company_name="Company C",
                job_url="https://example.com/3",
                location=Location(city="San Francisco"),
                description="Python expert needed",
                is_remote=True
            ),
        ]
        
        # Score jobs
        scored = score_jobs(jobs, "python developer", "New York")
        
        # Should return list of tuples
        assert len(scored) == 3
        assert all(isinstance(item, tuple) and len(item) == 2 for item in scored)
        
        # Should be sorted by score descending
        scores = [score for _, score in scored]
        assert scores == sorted(scores, reverse=True)
        
        # Python jobs should score higher than Java job
        job_titles = [job.title for job, _ in scored]
        assert "Java Developer" == job_titles[-1]  # Lowest score
        
        # Remote Python job should score well despite location mismatch
        remote_job_score = next(score for job, score in scored if job.is_remote)
        assert remote_job_score > 0.5


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_none_inputs(self):
        """Test handling of None inputs."""
        # JobPost requires title, so test with empty string instead
        job = JobPost(
            title="",
            company_name=None,
            job_url="https://example.com",
            location=None,
            description=None
        )
        
        # Should not crash, should return low score
        score = calculate_confidence_score(job, "python", "New York")
        assert score < 0.5
    
    def test_empty_job_list(self):
        """Test scoring empty job list."""
        scored = score_jobs([], "python", "New York")
        assert scored == []
    
    def test_special_characters(self):
        """Test handling of special characters."""
        # Should handle special characters gracefully
        score1 = calculate_text_similarity("C++ Developer", "C++ Developer")
        assert score1 == 1.0
        
        # Special characters create separate tokens
        score2 = calculate_keyword_match_score("C# .NET", "C# and .NET developer")
        assert score2 == 1.0  # Both keywords match