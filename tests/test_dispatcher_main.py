"""Tests for dispatcher main() orchestration loop."""

import json
from unittest.mock import patch

import pytest

import cron.dispatcher as dispatcher


@pytest.fixture(autouse=True)
def _patch_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(dispatcher, "JOBS_FILE", tmp_path / "jobs.json")
    monkeypatch.setattr(dispatcher, "STATE_FILE", tmp_path / "state" / "last_runs.json")
    monkeypatch.setattr(dispatcher, "LOGS_DIR", tmp_path / "logs")
    return tmp_path


class TestJobsFileHandling:
    """main() exits on missing or invalid jobs.json."""

    @pytest.mark.asyncio
    async def test_missing_jobs_file_exits(self, _patch_paths):
        with pytest.raises(SystemExit) as exc:
            await dispatcher.main()
        assert exc.value.code == 1

    @pytest.mark.asyncio
    async def test_invalid_json_exits(self, _patch_paths):
        (_patch_paths / "jobs.json").write_text("{bad json")
        with pytest.raises(SystemExit):
            await dispatcher.main()

    @pytest.mark.asyncio
    async def test_empty_jobs_runs_without_error(self, _patch_paths):
        (_patch_paths / "jobs.json").write_text('{"jobs": []}')
        await dispatcher.main()  # Should not raise


class TestJobFiltering:
    """main() skips disabled, not-due, and id-less jobs."""

    @pytest.mark.asyncio
    @patch("cron.dispatcher.execute_job", return_value=True)
    async def test_disabled_job_skipped(self, mock_exec, _patch_paths):
        jobs = {
            "jobs": [{"id": "j1", "enabled": False, "schedule": "* * * * *", "timezone": "UTC"}]
        }
        (_patch_paths / "jobs.json").write_text(json.dumps(jobs))
        await dispatcher.main()
        mock_exec.assert_not_called()

    @pytest.mark.asyncio
    @patch("cron.dispatcher.execute_job", return_value=True)
    @patch("cron.dispatcher.is_job_due", return_value=False)
    async def test_not_due_skipped(self, mock_due, mock_exec, _patch_paths):
        jobs = {"jobs": [{"id": "j1", "enabled": True, "schedule": "0 3 * * *", "timezone": "UTC"}]}
        (_patch_paths / "jobs.json").write_text(json.dumps(jobs))
        await dispatcher.main()
        mock_exec.assert_not_called()

    @pytest.mark.asyncio
    @patch("cron.dispatcher.execute_job", return_value=True)
    async def test_job_without_id_skipped(self, mock_exec, _patch_paths):
        jobs = {"jobs": [{"schedule": "* * * * *", "timezone": "UTC", "command": "echo hi"}]}
        (_patch_paths / "jobs.json").write_text(json.dumps(jobs))
        await dispatcher.main()
        mock_exec.assert_not_called()


class TestRunNow:
    """--run-now bypasses schedule and enabled checks."""

    @pytest.mark.asyncio
    @patch("cron.dispatcher.execute_job", return_value=True)
    async def test_run_now_bypasses_schedule(self, mock_exec, _patch_paths):
        jobs = {
            "jobs": [
                {
                    "id": "j1",
                    "enabled": False,
                    "schedule": "0 3 * * *",
                    "timezone": "UTC",
                    "command": "echo",
                }
            ]
        }
        (_patch_paths / "jobs.json").write_text(json.dumps(jobs))
        await dispatcher.main(run_now="j1")
        mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_now_not_found_exits(self, _patch_paths):
        jobs = {"jobs": [{"id": "j1", "schedule": "* * * * *", "timezone": "UTC"}]}
        (_patch_paths / "jobs.json").write_text(json.dumps(jobs))
        with pytest.raises(SystemExit) as exc:
            await dispatcher.main(run_now="nonexistent")
        assert exc.value.code == 1

    @pytest.mark.asyncio
    @patch("cron.dispatcher.execute_job", return_value=True)
    async def test_run_now_resets_failure_count(self, mock_exec, _patch_paths):
        jobs = {
            "jobs": [{"id": "j1", "schedule": "* * * * *", "timezone": "UTC", "command": "echo"}]
        }
        (_patch_paths / "jobs.json").write_text(json.dumps(jobs))

        # Set up state with 3 failures (disabled)
        state_dir = _patch_paths / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "last_runs.json").write_text(
            json.dumps({"j1": {"last_run": None, "failures": 3}})
        )

        await dispatcher.main(run_now="j1")
        mock_exec.assert_called_once()


class TestStateSaving:
    """State is saved before execution to prevent race conditions."""

    @pytest.mark.asyncio
    @patch("cron.dispatcher.execute_job", return_value=True)
    @patch("cron.dispatcher.is_job_due", return_value=True)
    async def test_state_saved_before_execution(self, mock_due, mock_exec, _patch_paths):
        jobs = {
            "jobs": [
                {
                    "id": "j1",
                    "enabled": True,
                    "schedule": "* * * * *",
                    "timezone": "UTC",
                    "command": "echo",
                }
            ]
        }
        (_patch_paths / "jobs.json").write_text(json.dumps(jobs))

        saved_states = []
        original_save = dispatcher.save_state

        def capture_save(state):
            saved_states.append(json.loads(json.dumps(state)))
            original_save(state)

        with patch("cron.dispatcher.save_state", side_effect=capture_save):
            await dispatcher.main()

        # State should have been saved at least once before execute
        assert len(saved_states) >= 1
        # First save should have a last_run set
        assert saved_states[0]["j1"]["last_run"] is not None


class TestFailureTracking:
    """Failure counter increments on failure and disables at 3."""

    @pytest.mark.asyncio
    @patch("cron.dispatcher.execute_job", return_value=False)
    @patch("cron.dispatcher.is_job_due", return_value=True)
    async def test_failure_increments(self, mock_due, mock_exec, _patch_paths):
        jobs = {
            "jobs": [
                {
                    "id": "j1",
                    "enabled": True,
                    "schedule": "* * * * *",
                    "timezone": "UTC",
                    "command": "echo",
                    "notify": {"type": "silent"},
                }
            ]
        }
        (_patch_paths / "jobs.json").write_text(json.dumps(jobs))
        await dispatcher.main()

        state = json.loads((_patch_paths / "state" / "last_runs.json").read_text())
        assert state["j1"]["failures"] == 1

    @pytest.mark.asyncio
    @patch("cron.dispatcher.execute_job", return_value=True)
    @patch("cron.dispatcher.is_job_due", return_value=True)
    async def test_success_resets_failures(self, mock_due, mock_exec, _patch_paths):
        jobs = {
            "jobs": [
                {
                    "id": "j1",
                    "enabled": True,
                    "schedule": "* * * * *",
                    "timezone": "UTC",
                    "command": "echo",
                }
            ]
        }
        (_patch_paths / "jobs.json").write_text(json.dumps(jobs))

        state_dir = _patch_paths / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "last_runs.json").write_text(
            json.dumps({"j1": {"last_run": None, "failures": 2}})
        )

        await dispatcher.main()

        state = json.loads((state_dir / "last_runs.json").read_text())
        assert state["j1"]["failures"] == 0

    @pytest.mark.asyncio
    @patch("cron.dispatcher.execute_job", return_value=False)
    @patch("cron.dispatcher.is_job_due", return_value=True)
    @patch("cron.dispatcher.send_webhook", return_value=True)
    async def test_3_failures_sends_disable_notification(
        self, mock_webhook, mock_due, mock_exec, _patch_paths
    ):
        jobs = {
            "jobs": [
                {
                    "id": "j1",
                    "name": "Test Job",
                    "enabled": True,
                    "schedule": "* * * * *",
                    "timezone": "UTC",
                    "command": "echo",
                    "notify": {"type": "webhook", "url_env": "URL"},
                }
            ]
        }
        (_patch_paths / "jobs.json").write_text(json.dumps(jobs))

        state_dir = _patch_paths / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "last_runs.json").write_text(
            json.dumps({"j1": {"last_run": None, "failures": 2}})
        )

        await dispatcher.main()

        # Should have sent a disable notification
        mock_webhook.assert_called_once()
        call_args = mock_webhook.call_args[0]
        assert "DISABLED" in call_args[0]

    @pytest.mark.asyncio
    @patch("cron.dispatcher.execute_job", return_value=True)
    async def test_3_failure_job_skipped_in_normal_mode(self, mock_exec, _patch_paths):
        jobs = {
            "jobs": [
                {
                    "id": "j1",
                    "enabled": True,
                    "schedule": "* * * * *",
                    "timezone": "UTC",
                    "command": "echo",
                }
            ]
        }
        (_patch_paths / "jobs.json").write_text(json.dumps(jobs))

        state_dir = _patch_paths / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "last_runs.json").write_text(
            json.dumps({"j1": {"last_run": None, "failures": 3}})
        )

        await dispatcher.main()
        mock_exec.assert_not_called()


class TestStateMigration:
    """Old string-format state entries are migrated to dict format."""

    @pytest.mark.asyncio
    @patch("cron.dispatcher.execute_job", return_value=True)
    @patch("cron.dispatcher.is_job_due", return_value=True)
    async def test_old_string_state_migrated(self, mock_due, mock_exec, _patch_paths):
        jobs = {
            "jobs": [
                {
                    "id": "j1",
                    "enabled": True,
                    "schedule": "* * * * *",
                    "timezone": "UTC",
                    "command": "echo",
                }
            ]
        }
        (_patch_paths / "jobs.json").write_text(json.dumps(jobs))

        state_dir = _patch_paths / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "last_runs.json").write_text(json.dumps({"j1": "2025-01-01T00:00:00"}))

        await dispatcher.main()

        state = json.loads((state_dir / "last_runs.json").read_text())
        assert isinstance(state["j1"], dict)
        assert "failures" in state["j1"]
