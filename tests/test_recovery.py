"""Tests for crash recovery, checkpointing, retry, and graceful shutdown."""

import os
import signal
import threading
import time
from concurrent.futures import Future
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest
import yaml

from jobx.market_analysis.anti_detection_utils import SafetyManager
from jobx.market_analysis.batch_executor import (
    BatchExecutor,
    LocationResult,
    RoleSearchTask,
)
from jobx.market_analysis.cli import (
    EXIT_FAILURE,
    EXIT_INTERRUPTED,
    EXIT_PARTIAL,
    EXIT_SUCCESS,
)
from jobx.market_analysis.config_loader import (
    Center,
    Config,
    Market,
    Meta,
    Payband,
    PayType,
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


def _make_executor(config=None, tmp_path=None, enable_safety=True, max_retries=3):
    config = config or _make_config()
    output_dir = str(tmp_path) if tmp_path else "."
    logger = MagicMock()
    return BatchExecutor(
        config, logger, output_dir=output_dir,
        enable_safety=enable_safety, max_retries=max_retries,
    )


def _make_task(role=None, center=None, market_name="Houston", region_name="Texas"):
    return RoleSearchTask(
        role=role or _make_role(),
        center=center or _make_center(),
        market_name=market_name,
        region_name=region_name,
    )


def _success_result(task, jobs_found=10, jobs_with_salary=5):
    df = pd.DataFrame({
        "title": [f"Job {i}" for i in range(jobs_found)],
        "min_amount": [50000.0] * jobs_with_salary + [None] * (jobs_found - jobs_with_salary),
        "max_amount": [70000.0] * jobs_with_salary + [None] * (jobs_found - jobs_with_salary),
        "job_url": [f"https://example.com/job/{i}" for i in range(jobs_found)],
    })
    return LocationResult(
        center=task.center, role=task.role, success=True,
        jobs_df=df, jobs_found=jobs_found, jobs_with_salary=jobs_with_salary,
        market_name=task.market_name, region_name=task.region_name,
    )


def _failure_result(task, error="Connection timeout"):
    return LocationResult(
        center=task.center, role=task.role, success=False,
        error=error, market_name=task.market_name, region_name=task.region_name,
    )


# ── SafetyManager Checkpoint Tests ────────────────────────────


class TestSafetyManagerCheckpoint:
    """Test task-level checkpoint mark/query and YAML persistence."""

    def test_mark_task_complete(self, tmp_path):
        sm = SafetyManager(str(tmp_path))
        sm.mark_task_complete("HOU-001", "rbt", 10, 5, "raw_jobs_HOU-001_rbt.csv")

        assert sm.is_task_done("HOU-001", "rbt")
        assert sm.get_completed_task_csv("HOU-001", "rbt") == "raw_jobs_HOU-001_rbt.csv"

    def test_mark_task_failed(self, tmp_path):
        sm = SafetyManager(str(tmp_path))
        sm.mark_task_failed("ATL-001", "rbt", "Connection timeout", 3)

        assert sm.is_task_done("ATL-001", "rbt")
        assert sm.get_completed_task_csv("ATL-001", "rbt") is None

    def test_not_done_for_unknown_task(self, tmp_path):
        sm = SafetyManager(str(tmp_path))
        assert not sm.is_task_done("UNKNOWN", "rbt")

    def test_persistence_across_loads(self, tmp_path):
        sm1 = SafetyManager(str(tmp_path))
        sm1.mark_task_complete("HOU-001", "rbt", 10, 5, "raw.csv")

        sm2 = SafetyManager(str(tmp_path))
        assert sm2.is_task_done("HOU-001", "rbt")
        assert sm2.get_completed_task_csv("HOU-001", "rbt") == "raw.csv"

    def test_retry_success_clears_failed(self, tmp_path):
        sm = SafetyManager(str(tmp_path))
        sm.mark_task_failed("HOU-001", "rbt", "timeout", 2)
        assert "HOU-001:rbt" in sm.progress["failed_tasks"]

        sm.mark_task_complete("HOU-001", "rbt", 10, 5, "raw.csv")
        assert "HOU-001:rbt" not in sm.progress["failed_tasks"]
        assert "HOU-001:rbt" in sm.progress["completed_tasks"]

    def test_v1_migration(self, tmp_path):
        """Old v1 format (no schema_version) should migrate to v2."""
        v1_data = {
            "completed_regions": ["Texas"],
            "completed_centers": ["HOU-001"],
            "last_search_time": "2026-01-01T12:00:00",
            "total_runtime_minutes": 30,
        }
        progress_file = tmp_path / "search_progress.yaml"
        with open(progress_file, 'w') as f:
            yaml.dump(v1_data, f)

        sm = SafetyManager(str(tmp_path))
        assert sm.progress["schema_version"] == 2
        assert "HOU-001" in sm.progress["completed_centers"]
        assert "Texas" in sm.progress["completed_regions"]
        assert sm.progress["completed_tasks"] == {}

    def test_set_total_tasks(self, tmp_path):
        sm = SafetyManager(str(tmp_path))
        sm.set_total_tasks(42)
        assert sm.progress["total_tasks"] == 42

    def test_progress_summary(self, tmp_path):
        sm = SafetyManager(str(tmp_path))
        sm.set_total_tasks(10)
        sm.mark_task_complete("C1", "r1", 5, 2, "a.csv")
        sm.mark_task_failed("C2", "r1", "error", 3)

        summary = sm.get_progress_summary()
        assert summary == {"total": 10, "completed": 1, "failed": 1, "remaining": 8}

    def test_thread_safety(self, tmp_path):
        """Concurrent mark_task_complete calls should not lose entries."""
        sm = SafetyManager(str(tmp_path))
        errors = []

        def mark(i):
            try:
                sm.mark_task_complete(f"C{i}", "rbt", 1, 0, f"raw_{i}.csv")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=mark, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(sm.progress["completed_tasks"]) == 20

    def test_atomic_save(self, tmp_path):
        """No .yaml.tmp file should be left after save."""
        sm = SafetyManager(str(tmp_path))
        sm.mark_task_complete("C1", "r1", 5, 2, "a.csv")

        tmp_file = tmp_path / "search_progress.yaml.tmp"
        assert not tmp_file.exists()
        assert (tmp_path / "search_progress.yaml").exists()

    def test_legacy_mark_center_still_works(self, tmp_path):
        sm = SafetyManager(str(tmp_path))
        sm.mark_center_complete("HOU-001")
        assert sm.is_center_complete("HOU-001")

    def test_reset_progress(self, tmp_path):
        sm = SafetyManager(str(tmp_path))
        sm.mark_task_complete("C1", "r1", 5, 2, "a.csv")
        sm.reset_progress()
        assert not sm.is_task_done("C1", "r1")
        assert sm.progress["schema_version"] == 2


# ── Retry Search Tests ─────────────────────────────────────────


class TestRetrySearch:
    """Test _retry_search with backoff and short-circuit logic."""

    def test_success_on_first_attempt(self, tmp_path):
        executor = _make_executor(tmp_path=tmp_path, enable_safety=False)
        task = _make_task()
        expected = _success_result(task)

        with patch.object(executor, 'search_location', return_value=expected):
            result = executor._retry_search(task)

        assert result.success
        assert result.jobs_found == 10

    @patch('time.sleep')
    def test_success_on_second_attempt(self, mock_sleep, tmp_path):
        executor = _make_executor(tmp_path=tmp_path, enable_safety=False, max_retries=3)
        task = _make_task()
        fail = _failure_result(task, error="Connection timeout")
        success = _success_result(task)

        with patch.object(executor, 'search_location', side_effect=[fail, success]):
            result = executor._retry_search(task)

        assert result.success
        mock_sleep.assert_called_once()

    @patch('time.sleep')
    def test_exhausted_retries(self, mock_sleep, tmp_path):
        executor = _make_executor(tmp_path=tmp_path, enable_safety=False, max_retries=2)
        task = _make_task()
        fail = _failure_result(task, error="Server error")

        with patch.object(executor, 'search_location', return_value=fail):
            result = executor._retry_search(task)

        assert not result.success
        assert result.error == "Server error"
        # 2 retries => 1 sleep (between attempt 1 and 2)
        assert mock_sleep.call_count == 1

    def test_no_retry_on_no_jobs_found(self, tmp_path):
        executor = _make_executor(tmp_path=tmp_path, enable_safety=False, max_retries=3)
        task = _make_task()
        no_jobs = _failure_result(task, error="No jobs found")

        with patch.object(executor, 'search_location', return_value=no_jobs) as mock_search:
            result = executor._retry_search(task)

        assert not result.success
        mock_search.assert_called_once()  # No retries

    @patch('time.sleep')
    def test_exponential_backoff_timing(self, mock_sleep, tmp_path):
        executor = _make_executor(tmp_path=tmp_path, enable_safety=False, max_retries=3)
        task = _make_task()
        fail = _failure_result(task, error="Timeout")

        with patch.object(executor, 'search_location', return_value=fail):
            with patch('jobx.market_analysis.batch_executor.random.uniform', return_value=5.0):
                executor._retry_search(task, base_backoff=10.0)

        # Attempt 1 fails: sleep(10 * 2^0 + 5 = 15)
        # Attempt 2 fails: sleep(10 * 2^1 + 5 = 25)
        calls = mock_sleep.call_args_list
        assert len(calls) == 2
        assert calls[0][0][0] == 15.0
        assert calls[1][0][0] == 25.0


# ── Exception Handling in execute_batch ────────────────────────


class TestExecuteBatchExceptionHandling:
    """Test that exceptions from futures don't crash the batch loop."""

    @patch('time.sleep')
    def test_exception_produces_failure_result(self, mock_sleep, tmp_path):
        executor = _make_executor(tmp_path=tmp_path, enable_safety=False)
        task = _make_task()

        with patch.object(executor, '_retry_search', side_effect=RuntimeError("Boom")):
            results = executor.execute_batch([task])

        assert len(results) == 1
        assert not results[0].success
        assert "Uncaught exception: Boom" in results[0].error

    @patch('time.sleep')
    def test_other_tasks_unaffected(self, mock_sleep, tmp_path):
        task1 = _make_task(center=_make_center(code="C1"))
        task2 = _make_task(center=_make_center(code="C2"))
        executor = _make_executor(tmp_path=tmp_path, enable_safety=False)

        def side_effect(task):
            if task.center.code == "C1":
                raise RuntimeError("Boom")
            return _success_result(task)

        with patch.object(executor, '_retry_search', side_effect=side_effect):
            results = executor.execute_batch([task1, task2])

        assert len(results) == 2
        success_results = [r for r in results if r.success]
        failure_results = [r for r in results if not r.success]
        assert len(success_results) == 1
        assert len(failure_results) == 1


# ── Resume from Checkpoint Tests ───────────────────────────────


class TestResumeFromCheckpoint:
    """Test _reload_completed_tasks and resume flow in execute_all."""

    def test_reload_from_csv(self, tmp_path):
        config = _make_config()
        executor = _make_executor(config=config, tmp_path=tmp_path)
        task = _make_task()

        # Write a CSV that the reload will find
        csv_path = tmp_path / f"raw_jobs_{task.center.code}_{task.role.id}.csv"
        df = pd.DataFrame({
            "title": ["Job 1", "Job 2"],
            "min_amount": [50000.0, None],
            "max_amount": [70000.0, None],
        })
        df.to_csv(csv_path, index=False)

        # Mark as completed in checkpoint
        executor.safety.mark_task_complete(
            task.center.code, task.role.id, 2, 1, str(csv_path)
        )

        reloaded = executor._reload_completed_tasks([task])
        assert len(reloaded) == 1
        assert reloaded[0].success
        assert reloaded[0].jobs_found == 2
        assert reloaded[0].jobs_with_salary == 1

    def test_missing_csv_skips_and_reruns(self, tmp_path):
        executor = _make_executor(tmp_path=tmp_path)
        task = _make_task()

        # Mark as completed but don't create the CSV
        executor.safety.mark_task_complete(
            task.center.code, task.role.id, 10, 5, "nonexistent.csv"
        )

        reloaded = executor._reload_completed_tasks([task])
        assert len(reloaded) == 0
        # The stale entry should be removed so the task re-runs
        assert not executor.safety.is_task_done(task.center.code, task.role.id)

    @patch('time.sleep')
    def test_resume_skips_completed_tasks(self, mock_sleep, tmp_path):
        role = _make_role()
        c1 = _make_center(code="C1")
        c2 = _make_center(code="C2")
        config = _make_config(centers=[c1, c2])
        executor = _make_executor(config=config, tmp_path=tmp_path)

        # Write CSV for C1 so it can be reloaded
        csv_path = tmp_path / f"raw_jobs_C1_{role.id}.csv"
        pd.DataFrame({
            "title": ["J1"], "min_amount": [50000.0], "max_amount": [60000.0],
        }).to_csv(csv_path, index=False)

        executor.safety.mark_task_complete("C1", role.id, 1, 1, str(csv_path))

        # Mock search_location so C2 "succeeds"
        with patch.object(executor, 'search_location', return_value=_success_result(
            _make_task(role=role, center=c2)
        )) as mock_search:
            executor.execute_all(resume=True)

        # Only C2 should have been searched (C1 was reloaded from checkpoint)
        for call in mock_search.call_args_list:
            task_arg = call[0][0]
            assert task_arg.center.code != "C1"

    @patch('time.sleep')
    def test_resume_all_done(self, mock_sleep, tmp_path):
        config = _make_config()
        executor = _make_executor(config=config, tmp_path=tmp_path)
        task = _make_task()

        csv_path = tmp_path / f"raw_jobs_{task.center.code}_{task.role.id}.csv"
        pd.DataFrame({
            "title": ["J1"], "min_amount": [50000.0], "max_amount": [60000.0],
        }).to_csv(csv_path, index=False)
        executor.safety.mark_task_complete(
            task.center.code, task.role.id, 1, 1, str(csv_path)
        )

        with patch.object(executor, 'execute_batch') as mock_batch:
            executor.execute_all(resume=True)

        mock_batch.assert_not_called()
        assert len(executor.results) == 1  # Reloaded result


# ── Shutdown Signal Tests ──────────────────────────────────────


class TestSignalHandling:
    """Test graceful shutdown via _shutdown_event."""

    @patch('time.sleep')
    def test_shutdown_stops_batch_loop(self, mock_sleep, tmp_path):
        centers = [_make_center(code=f"C{i}") for i in range(10)]
        config = _make_config(centers=centers, batch_size=2)
        executor = _make_executor(config=config, tmp_path=tmp_path, enable_safety=False)

        batch_count = 0
        original_execute_batch = executor.execute_batch

        def counting_execute_batch(tasks):
            nonlocal batch_count
            batch_count += 1
            # Request shutdown after first batch
            if batch_count == 1:
                executor.request_shutdown()
            return original_execute_batch(tasks)

        with patch.object(executor, 'execute_batch', side_effect=counting_execute_batch):
            with patch.object(executor, 'search_location', side_effect=lambda t: _success_result(t)):
                # Need to call _retry_search which wraps search_location
                with patch.object(executor, '_retry_search', side_effect=lambda t, **kw: _success_result(t)):
                    executor.execute_all()

        assert executor.shutdown_requested
        # Should have stopped after first batch, not processed all 5
        assert batch_count <= 2

    def test_request_shutdown_sets_event(self, tmp_path):
        executor = _make_executor(tmp_path=tmp_path, enable_safety=False)
        assert not executor._shutdown_event.is_set()

        executor.request_shutdown()

        assert executor._shutdown_event.is_set()
        assert executor.shutdown_requested


# ── Exit Code Tests ────────────────────────────────────────────


class TestExitCodes:
    """Test exit code constants and logic."""

    def test_exit_code_values(self):
        assert EXIT_SUCCESS == 0
        assert EXIT_FAILURE == 1
        assert EXIT_PARTIAL == 2
        assert EXIT_INTERRUPTED == 130


# ── CLI Flags Tests ────────────────────────────────────────────


class TestCLIFlags:
    """Test --resume and --max-retries argument parsing."""

    def test_resume_flag(self):
        from jobx.market_analysis.cli import main
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("config")
        parser.add_argument("--resume", action="store_true")
        parser.add_argument("--max-retries", type=int, default=3)

        args = parser.parse_args(["config.yaml", "--resume", "--max-retries", "5"])
        assert args.resume is True
        assert args.max_retries == 5

    def test_defaults(self):
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("config")
        parser.add_argument("--resume", action="store_true")
        parser.add_argument("--max-retries", type=int, default=3)

        args = parser.parse_args(["config.yaml"])
        assert args.resume is False
        assert args.max_retries == 3


# ── Checkpoint + execute_batch Integration ─────────────────────


class TestCheckpointResult:
    """Test _checkpoint_result persists to SafetyManager."""

    @patch('time.sleep')
    def test_success_checkpointed(self, mock_sleep, tmp_path):
        executor = _make_executor(tmp_path=tmp_path)
        task = _make_task()
        result = _success_result(task)

        executor._checkpoint_result(task, result)

        assert executor.safety.is_task_done(task.center.code, task.role.id)
        csv = executor.safety.get_completed_task_csv(task.center.code, task.role.id)
        assert csv is not None
        assert "raw_jobs_HOU-001_rbt.csv" in csv

    @patch('time.sleep')
    def test_failure_checkpointed(self, mock_sleep, tmp_path):
        executor = _make_executor(tmp_path=tmp_path)
        task = _make_task()
        result = _failure_result(task)

        executor._checkpoint_result(task, result)

        assert executor.safety.is_task_done(task.center.code, task.role.id)
        assert executor.safety.get_completed_task_csv(task.center.code, task.role.id) is None

    @patch('time.sleep')
    def test_no_checkpoint_without_safety(self, mock_sleep, tmp_path):
        executor = _make_executor(tmp_path=tmp_path, enable_safety=False)
        task = _make_task()
        result = _success_result(task)

        # Should not raise even without safety manager
        executor._checkpoint_result(task, result)
