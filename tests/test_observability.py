"""Tests for pipeline observability: error classification, timing, stats, and run summary."""

import json
from unittest.mock import MagicMock

import pandas as pd
import pytest

from jobx.market_analysis.batch_executor import (
    BatchExecutor,
    ErrorCategory,
    LocationResult,
    RoleSearchTask,
    classify_error,
)
from jobx.market_analysis.cli import (
    _build_run_summary,
    _format_duration,
    _generate_recommendation,
)
from jobx.market_analysis.config_loader import (
    Center,
    Config,
    Market,
    Meta,
    Payband,
    Region,
    Role,
    SearchConfig,
)

# ── Helpers ────────────────────────────────────────────────────


def _make_role(role_id="rbt", name="RBT", pay_type="hourly"):
    return Role(id=role_id, name=name, pay_type=pay_type,
                default_unit="USD/hour", search_terms=["test term"])


def _make_center(code="HOU-001", name="Houston Center", zip_code="77001"):
    return Center(code=code, name=name, address_1="123 Main St",
                  city="Houston", state="TX", zip_code=zip_code)


def _make_config(roles=None, centers=None, batch_size=2):
    roles = roles or [_make_role()]
    centers = centers or [_make_center()]
    market = Market(
        name="Houston",
        paybands={r.id: Payband(min=20, max=40) for r in roles},
        centers=centers,
    )
    region = Region(name="Texas", markets=[market])
    return Config(
        meta=Meta(),
        roles=roles,
        search=SearchConfig(batch_size=batch_size),
        regions=[region],
    )


def _make_executor(config=None, tmp_path=None, enable_safety=False):
    config = config or _make_config()
    output_dir = str(tmp_path) if tmp_path else "."
    logger = MagicMock()
    return BatchExecutor(
        config, logger, output_dir=output_dir,
        enable_safety=enable_safety,
    )


def _make_task(role=None, center=None, market_name="Houston", region_name="Texas"):
    return RoleSearchTask(
        role=role or _make_role(),
        center=center or _make_center(),
        market_name=market_name,
        region_name=region_name,
    )


def _success_result(task, jobs_found=10, jobs_with_salary=5, duration=30.0):
    return LocationResult(
        center=task.center, role=task.role, success=True,
        jobs_df=pd.DataFrame(), jobs_found=jobs_found,
        jobs_with_salary=jobs_with_salary,
        market_name=task.market_name, region_name=task.region_name,
        duration_seconds=duration,
    )


def _failure_result(task, error="Connection timeout", duration=5.0, error_category=None):
    return LocationResult(
        center=task.center, role=task.role, success=False,
        error=error, market_name=task.market_name, region_name=task.region_name,
        duration_seconds=duration,
        error_category=error_category or classify_error(error).value,
    )


# ── Error Classification ──────────────────────────────────────


class TestErrorCategory:
    """ErrorCategory enum basics."""

    def test_string_serialization(self):
        assert ErrorCategory.NETWORK.value == "network"
        assert ErrorCategory.RATE_LIMIT.value == "rate_limit"

    def test_all_categories_are_unique(self):
        values = [e.value for e in ErrorCategory]
        assert len(values) == len(set(values))


class TestClassifyError:
    """classify_error() keyword matching."""

    @pytest.mark.parametrize("msg,expected", [
        ("Connection timeout after 30s", ErrorCategory.NETWORK),
        ("Connection timed out", ErrorCategory.NETWORK),
        ("proxy connection refused", ErrorCategory.NETWORK),
        ("DNS resolution failed", ErrorCategory.NETWORK),
        ("SSL handshake error", ErrorCategory.NETWORK),
        ("socket error", ErrorCategory.NETWORK),
        ("Connection reset by peer", ErrorCategory.NETWORK),
    ])
    def test_network_errors(self, msg, expected):
        assert classify_error(msg) == expected

    @pytest.mark.parametrize("msg,expected", [
        ("HTTP 429 Too Many Requests", ErrorCategory.RATE_LIMIT),
        ("rate limit exceeded", ErrorCategory.RATE_LIMIT),
        ("Request blocked by server", ErrorCategory.RATE_LIMIT),
        ("too many requests", ErrorCategory.RATE_LIMIT),
        ("throttled", ErrorCategory.RATE_LIMIT),
    ])
    def test_rate_limit_errors(self, msg, expected):
        assert classify_error(msg) == expected

    @pytest.mark.parametrize("msg,expected", [
        ("No jobs found", ErrorCategory.NO_DATA),
        ("No results returned", ErrorCategory.NO_DATA),
        ("Empty response body", ErrorCategory.NO_DATA),
    ])
    def test_no_data_errors(self, msg, expected):
        assert classify_error(msg) == expected

    @pytest.mark.parametrize("msg,expected", [
        ("ValueError: invalid literal", ErrorCategory.PARSE_ERROR),
        ("JSON decode error", ErrorCategory.PARSE_ERROR),
        ("Failed to parse response", ErrorCategory.PARSE_ERROR),
        ("KeyError: 'salary'", ErrorCategory.PARSE_ERROR),
    ])
    def test_parse_errors(self, msg, expected):
        assert classify_error(msg) == expected

    @pytest.mark.parametrize("msg,expected", [
        ("CAPTCHA challenge required", ErrorCategory.AUTH_BLOCK),
        ("HTTP 403 Forbidden", ErrorCategory.AUTH_BLOCK),
        ("Access denied", ErrorCategory.AUTH_BLOCK),
    ])
    def test_auth_block_errors(self, msg, expected):
        assert classify_error(msg) == expected

    def test_unknown_fallback(self):
        assert classify_error("something completely unexpected") == ErrorCategory.UNKNOWN

    def test_rate_limit_takes_precedence_over_network(self):
        """A 429 is technically a network response but should be classified as rate_limit."""
        assert classify_error("HTTP 429 connection reset") == ErrorCategory.RATE_LIMIT

    def test_case_insensitive(self):
        assert classify_error("CONNECTION TIMEOUT") == ErrorCategory.NETWORK
        assert classify_error("No Jobs Found") == ErrorCategory.NO_DATA


# ── LocationResult Extension ──────────────────────────────────


class TestLocationResultFields:
    """New optional fields on LocationResult."""

    def test_default_none(self):
        task = _make_task()
        result = LocationResult(
            center=task.center, role=task.role, success=True,
            market_name="Houston", region_name="Texas",
        )
        assert result.duration_seconds is None
        assert result.error_category is None

    def test_can_set_values(self):
        task = _make_task()
        result = _success_result(task, duration=42.5)
        assert result.duration_seconds == 42.5

    def test_backward_compat_location_property(self):
        """The existing .location property still works with new fields."""
        task = _make_task()
        result = _success_result(task)
        loc = result.location
        assert loc.zip_code == task.center.zip_code


# ── Timing Stats ──────────────────────────────────────────────


class TestTimingStats:
    """BatchExecutor.get_timing_stats()."""

    def test_empty_results(self, tmp_path):
        executor = _make_executor(tmp_path=tmp_path)
        stats = executor.get_timing_stats()
        assert stats == {"p50": 0, "p95": 0, "max": 0, "count": 0}

    def test_single_result(self, tmp_path):
        executor = _make_executor(tmp_path=tmp_path)
        task = _make_task()
        executor.results.append(_success_result(task, duration=10.0))
        stats = executor.get_timing_stats()
        assert stats["count"] == 1
        assert stats["max"] == 10.0

    def test_multiple_results(self, tmp_path):
        executor = _make_executor(tmp_path=tmp_path)
        task = _make_task()
        durations = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        for d in durations:
            executor.results.append(_success_result(task, duration=d))
        stats = executor.get_timing_stats()
        assert stats["count"] == 10
        assert stats["max"] == 100.0
        assert stats["p50"] == 60.0  # index 5
        assert stats["p95"] == 100.0  # index 9

    def test_ignores_none_durations(self, tmp_path):
        executor = _make_executor(tmp_path=tmp_path)
        task = _make_task()
        r = _success_result(task, duration=10.0)
        executor.results.append(r)
        # Add a result with no duration (e.g. reloaded from checkpoint)
        r2 = LocationResult(
            center=task.center, role=task.role, success=True,
            market_name="Houston", region_name="Texas",
        )
        executor.results.append(r2)
        assert executor.get_timing_stats()["count"] == 1


# ── Error Summary ─────────────────────────────────────────────


class TestErrorSummary:
    """BatchExecutor.get_error_summary()."""

    def test_no_failures(self, tmp_path):
        executor = _make_executor(tmp_path=tmp_path)
        task = _make_task()
        executor.results.append(_success_result(task))
        summary = executor.get_error_summary()
        assert summary["total_failures"] == 0
        assert summary["by_category"] == {}

    def test_categorized_failures(self, tmp_path):
        executor = _make_executor(tmp_path=tmp_path)
        task = _make_task()
        executor.results.append(_failure_result(task, "Connection timeout"))
        executor.results.append(_failure_result(task, "No jobs found"))
        executor.results.append(_failure_result(task, "No jobs found"))
        summary = executor.get_error_summary()
        assert summary["total_failures"] == 3
        assert summary["by_category"]["network"] == 1
        assert summary["by_category"]["no_data"] == 2

    def test_top_errors_ordering(self, tmp_path):
        executor = _make_executor(tmp_path=tmp_path)
        task = _make_task()
        for _ in range(5):
            executor.results.append(_failure_result(task, "No jobs found"))
        for _ in range(2):
            executor.results.append(_failure_result(task, "Connection timeout"))
        summary = executor.get_error_summary()
        assert summary["top_errors"][0]["message"] == "No jobs found"
        assert summary["top_errors"][0]["count"] == 5
        assert summary["top_errors"][1]["message"] == "Connection timeout"


# ── Slowest Searches ──────────────────────────────────────────


class TestSlowestSearches:
    """BatchExecutor.get_slowest_searches()."""

    def test_empty(self, tmp_path):
        executor = _make_executor(tmp_path=tmp_path)
        assert executor.get_slowest_searches() == []

    def test_returns_n_slowest(self, tmp_path):
        executor = _make_executor(tmp_path=tmp_path)
        task = _make_task()
        for d in [5.0, 50.0, 100.0, 200.0]:
            executor.results.append(_success_result(task, duration=d))
        slowest = executor.get_slowest_searches(n=2)
        assert len(slowest) == 2
        assert slowest[0]["duration_seconds"] == 200.0
        assert slowest[1]["duration_seconds"] == 100.0

    def test_includes_failures(self, tmp_path):
        executor = _make_executor(tmp_path=tmp_path)
        task = _make_task()
        executor.results.append(_success_result(task, duration=10.0))
        executor.results.append(_failure_result(task, duration=300.0))
        slowest = executor.get_slowest_searches(n=1)
        assert slowest[0]["success"] is False
        assert slowest[0]["duration_seconds"] == 300.0


# ── Format Duration ───────────────────────────────────────────


class TestFormatDuration:

    @pytest.mark.parametrize("seconds,expected", [
        (0, "0s"),
        (45, "45s"),
        (90, "1m 30s"),
        (3661, "1h 1m 1s"),
        (8853, "2h 27m 33s"),
    ])
    def test_formatting(self, seconds, expected):
        assert _format_duration(seconds) == expected


# ── Recommendation Generator ─────────────────────────────────


class TestGenerateRecommendation:

    def test_interrupted(self):
        rec = _generate_recommendation(100, 10, {}, shutdown_requested=True)
        assert "--resume" in rec

    def test_no_tasks(self):
        rec = _generate_recommendation(0, 0, {}, shutdown_requested=False)
        assert "configuration" in rec.lower()

    def test_all_success(self):
        rec = _generate_recommendation(100, 0, {"total_failures": 0}, shutdown_requested=False)
        assert "No re-run needed" in rec

    def test_all_no_data(self):
        error_summary = {
            "total_failures": 5,
            "by_category": {"no_data": 5},
        }
        rec = _generate_recommendation(50, 5, error_summary, shutdown_requested=False)
        assert "structural" in rec.lower()
        assert "Re-run will not help" in rec

    def test_rate_limit_advice(self):
        error_summary = {
            "total_failures": 3,
            "by_category": {"rate_limit": 3},
        }
        rec = _generate_recommendation(50, 3, error_summary, shutdown_requested=False)
        assert "--safe-mode" in rec

    def test_majority_network(self):
        error_summary = {
            "total_failures": 10,
            "by_category": {"network": 8, "no_data": 2},
        }
        rec = _generate_recommendation(20, 10, error_summary, shutdown_requested=False)
        assert "connectivity" in rec.lower()

    def test_high_failure_rate(self):
        error_summary = {
            "total_failures": 40,
            "by_category": {"unknown": 40},
        }
        rec = _generate_recommendation(100, 40, error_summary, shutdown_requested=False)
        assert "investigate" in rec.lower()


# ── Run Summary ───────────────────────────────────────────────


class TestBuildRunSummary:
    """_build_run_summary() produces a valid, well-structured dict."""

    def _make_summary(self, tmp_path, successes=8, failures=2, shutdown=False):
        """Helper to build a summary with controlled results."""
        role = _make_role()
        centers = [_make_center(code=f"HOU-{i:03d}", zip_code=f"7700{i}") for i in range(10)]
        config = _make_config(roles=[role], centers=centers)
        executor = _make_executor(config=config, tmp_path=tmp_path)
        if shutdown:
            executor.shutdown_requested = True

        for i in range(successes):
            task = _make_task(role=role, center=centers[i])
            executor.results.append(_success_result(task, duration=30.0 + i * 10))
        for i in range(failures):
            task = _make_task(role=role, center=centers[successes + i])
            executor.results.append(_failure_result(task, "No jobs found", duration=5.0))

        exec_stats = executor.get_summary_stats()

        # Minimal aggregated_markets stub
        class FakeMarket:
            has_sufficient_data = True
        aggregated_markets = {"Houston": FakeMarket()}

        return _build_run_summary(
            start_time=1000000.0,
            end_time=1008853.0,
            config=config,
            config_file="test_config.yaml",
            executor=executor,
            exec_stats=exec_stats,
            aggregated_markets=aggregated_markets,
        )

    def test_schema_version(self, tmp_path):
        summary = self._make_summary(tmp_path)
        assert summary["schema_version"] == 1

    def test_timestamps_present(self, tmp_path):
        summary = self._make_summary(tmp_path)
        assert "run_started_at" in summary
        assert "run_finished_at" in summary

    def test_duration(self, tmp_path):
        summary = self._make_summary(tmp_path)
        assert summary["duration_seconds"] == 8853.0
        assert summary["duration_human"] == "2h 27m 33s"

    def test_exit_status_partial(self, tmp_path):
        summary = self._make_summary(tmp_path, successes=8, failures=2)
        assert summary["exit_status"] == "partial"

    def test_exit_status_success(self, tmp_path):
        summary = self._make_summary(tmp_path, successes=10, failures=0)
        assert summary["exit_status"] == "success"

    def test_exit_status_interrupted(self, tmp_path):
        summary = self._make_summary(tmp_path, shutdown=True)
        assert summary["exit_status"] == "interrupted"

    def test_task_counts(self, tmp_path):
        summary = self._make_summary(tmp_path, successes=8, failures=2)
        assert summary["tasks"]["total"] == 10
        assert summary["tasks"]["successful"] == 8
        assert summary["tasks"]["failed"] == 2
        assert summary["tasks"]["success_rate_pct"] == 80.0

    def test_config_summary(self, tmp_path):
        summary = self._make_summary(tmp_path)
        cs = summary["config_summary"]
        assert cs["roles"] == ["rbt"]
        assert cs["regions"] == 1
        assert cs["markets"] == 1
        assert cs["centers"] == 10

    def test_timing_section(self, tmp_path):
        summary = self._make_summary(tmp_path)
        assert "search_duration_p50_seconds" in summary["timing"]
        assert "slowest_searches" in summary["timing"]
        assert len(summary["timing"]["slowest_searches"]) <= 5

    def test_errors_section(self, tmp_path):
        summary = self._make_summary(tmp_path, failures=2)
        assert summary["errors"]["total_failures"] == 2
        assert "no_data" in summary["errors"]["by_category"]

    def test_per_role(self, tmp_path):
        summary = self._make_summary(tmp_path)
        assert "rbt" in summary["per_role"]
        assert summary["per_role"]["rbt"]["tasks"] == 10

    def test_per_market(self, tmp_path):
        summary = self._make_summary(tmp_path)
        assert "Houston" in summary["per_market"]
        houston = summary["per_market"]["Houston"]
        assert houston["tasks"] == 10
        assert houston["with_sufficient_data"] is True

    def test_recommendation_present(self, tmp_path):
        summary = self._make_summary(tmp_path)
        assert isinstance(summary["recommendation"], str)
        assert len(summary["recommendation"]) > 0

    def test_json_serializable(self, tmp_path):
        """The entire summary must serialize to JSON without errors."""
        summary = self._make_summary(tmp_path)
        serialized = json.dumps(summary, indent=2)
        roundtripped = json.loads(serialized)
        assert roundtripped["schema_version"] == 1
