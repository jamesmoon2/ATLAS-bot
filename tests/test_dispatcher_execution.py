"""Tests for dispatcher job execution (run_shell_command, run_agent_job, execute_job)."""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import cron.dispatcher as dispatcher


class TestRunShellCommand:
    """run_shell_command() executes shell commands and returns output."""

    @pytest.mark.asyncio
    @patch("cron.dispatcher.asyncio.create_subprocess_shell")
    async def test_success(self, mock_shell):
        proc = MagicMock()
        proc.returncode = 0
        proc.communicate = AsyncMock(return_value=(b"hello world", b""))
        mock_shell.return_value = proc

        output, success = await dispatcher.run_shell_command(
            {"command": "echo hello", "timeout_seconds": 30}
        )
        assert success is True
        assert "hello world" in output

    @pytest.mark.asyncio
    @patch("cron.dispatcher.asyncio.create_subprocess_shell")
    async def test_failure_nonzero_exit(self, mock_shell):
        proc = MagicMock()
        proc.returncode = 1
        proc.communicate = AsyncMock(return_value=(b"", b"error"))
        mock_shell.return_value = proc

        output, success = await dispatcher.run_shell_command({"command": "false"})
        assert success is False

    @pytest.mark.asyncio
    @patch("cron.dispatcher.asyncio.create_subprocess_shell")
    async def test_timeout(self, mock_shell):
        proc = MagicMock()
        proc.kill = MagicMock()
        proc.communicate = AsyncMock(side_effect=[asyncio.TimeoutError, (b"", b"")])
        mock_shell.return_value = proc

        output, success = await dispatcher.run_shell_command(
            {"command": "sleep 999", "timeout_seconds": 1}
        )
        assert success is False
        assert "timed out" in output.lower()
        proc.kill.assert_called_once()

    @pytest.mark.asyncio
    @patch("cron.dispatcher.asyncio.create_subprocess_shell")
    async def test_stderr_appended(self, mock_shell):
        proc = MagicMock()
        proc.returncode = 0
        proc.communicate = AsyncMock(return_value=(b"output", b"warning"))
        mock_shell.return_value = proc

        output, success = await dispatcher.run_shell_command({"command": "cmd"})
        assert "Stderr:" in output
        assert "warning" in output

    @pytest.mark.asyncio
    @patch("cron.dispatcher.asyncio.create_subprocess_shell")
    async def test_no_output_default_message(self, mock_shell):
        proc = MagicMock()
        proc.returncode = 0
        proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_shell.return_value = proc

        output, success = await dispatcher.run_shell_command({"command": "true"})
        assert "no output" in output.lower()

    @pytest.mark.asyncio
    @patch("cron.dispatcher.asyncio.create_subprocess_shell", side_effect=Exception("boom"))
    async def test_exception_handling(self, mock_shell):
        output, success = await dispatcher.run_shell_command({"command": "bad"})
        assert success is False
        assert "boom" in output

    @pytest.mark.asyncio
    @patch("cron.dispatcher.asyncio.create_subprocess_shell")
    async def test_shell_env_includes_repo_context(self, mock_shell, monkeypatch):
        proc = MagicMock()
        proc.returncode = 0
        proc.communicate = AsyncMock(return_value=(b"ok", b""))
        mock_shell.return_value = proc

        monkeypatch.delenv("BOT_DIR", raising=False)
        monkeypatch.setenv("VAULT_PATH", "/tmp/vault")
        monkeypatch.setenv("PYTHONPATH", "/tmp/custom-pythonpath")

        await dispatcher.run_shell_command({"command": "true"})

        env = mock_shell.call_args.kwargs["env"]
        assert env["BOT_DIR"] == str(dispatcher.BOT_DIR)
        assert env["VAULT_PATH"] == "/tmp/vault"
        assert str(dispatcher.BOT_DIR) in env["PYTHONPATH"].split(os.pathsep)
        assert "/tmp/custom-pythonpath" in env["PYTHONPATH"].split(os.pathsep)


class TestRunAgentJob:
    """run_agent_job() invokes the shared provider runner with expanded prompt data."""

    @pytest.mark.asyncio
    @patch("cron.dispatcher.run_job_prompt", return_value=("response", True))
    async def test_datetime_injection(self, mock_run_job):
        job = {
            "prompt": "Time is {current_datetime}",
            "allowed_tools": ["Read"],
            "timeout_seconds": 60,
            "model": "opus",
            "timezone": "America/Los_Angeles",
        }
        output, success = await dispatcher.run_agent_job(job)

        assert success is True
        assert output == "response"
        prompt_arg = mock_run_job.call_args.kwargs["prompt"]
        assert "{current_datetime}" not in prompt_arg

    @pytest.mark.asyncio
    @patch("cron.dispatcher.run_job_prompt", return_value=("ok", True))
    async def test_model_forwarded(self, mock_run_job):
        job = {
            "prompt": "test",
            "allowed_tools": ["Read"],
            "timeout_seconds": 60,
            "model": "haiku",
            "timezone": "UTC",
        }
        await dispatcher.run_agent_job(job)

        assert mock_run_job.call_args.kwargs["model"] == "haiku"

    @pytest.mark.asyncio
    @patch("cron.dispatcher.run_job_prompt", return_value=("ok", True))
    async def test_allowed_tools_forwarded(self, mock_run_job):
        job = {
            "prompt": "test",
            "allowed_tools": ["Read", "Write", "Glob"],
            "timeout_seconds": 60,
            "model": "opus",
            "timezone": "UTC",
        }
        await dispatcher.run_agent_job(job)

        assert mock_run_job.call_args.kwargs["allowed_tools"] == ["Read", "Write", "Glob"]


class TestExecuteJob:
    """execute_job() dispatches to shell or the active agent and handles notification."""

    @pytest.fixture(autouse=True)
    def _patch_logs(self, tmp_path, monkeypatch):
        monkeypatch.setattr(dispatcher, "LOGS_DIR", tmp_path / "logs")

    @pytest.mark.asyncio
    @patch("cron.dispatcher.run_shell_command", return_value=("output", True))
    async def test_shell_job_dispatched(self, mock_run):
        job = {"id": "sh", "name": "Shell", "command": "echo hi", "notify": {"type": "silent"}}
        result = await dispatcher.execute_job(job)
        assert result is True
        mock_run.assert_called_once()

    @pytest.mark.asyncio
    @patch("cron.dispatcher.run_agent_job", return_value=("output", True))
    async def test_claude_job_dispatched(self, mock_run):
        job = {"id": "cl", "name": "Claude", "prompt": "hi", "notify": {"type": "silent"}}
        result = await dispatcher.execute_job(job)
        assert result is True
        mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_command_or_prompt(self):
        job = {"id": "bad", "name": "Bad", "notify": {"type": "silent"}}
        result = await dispatcher.execute_job(job)
        assert result is False

    @pytest.mark.asyncio
    @patch("cron.dispatcher.run_shell_command", return_value=("output", True))
    @patch("cron.dispatcher.send_webhook", return_value=True)
    async def test_webhook_notification(self, mock_webhook, mock_run):
        job = {
            "id": "wh",
            "name": "Webhook Job",
            "command": "echo hi",
            "timezone": "UTC",
            "notify": {"type": "webhook", "url_env": "DISCORD_WEBHOOK_URL"},
        }
        result = await dispatcher.execute_job(job)
        assert result is True
        mock_webhook.assert_called_once()

    @pytest.mark.asyncio
    @patch("cron.dispatcher.run_shell_command", return_value=("contains NO_ALERT marker", True))
    @patch("cron.dispatcher.send_webhook")
    async def test_suppression(self, mock_webhook, mock_run):
        job = {
            "id": "sup",
            "name": "Suppressed",
            "command": "echo hi",
            "notify": {
                "type": "webhook",
                "url_env": "URL",
                "suppress_if_contains": "NO_ALERT",
            },
        }
        await dispatcher.execute_job(job)
        mock_webhook.assert_not_called()

    @pytest.mark.asyncio
    @patch("cron.dispatcher.run_shell_command", return_value=("output", True))
    async def test_log_file_created(self, mock_run, tmp_path):
        job = {"id": "log_test", "name": "Log", "command": "echo hi", "notify": {"type": "silent"}}
        await dispatcher.execute_job(job)
        log_file = tmp_path / "logs" / "log_test.log"
        assert log_file.exists()
        assert "Running: Log" in log_file.read_text()

    @pytest.mark.asyncio
    @patch("cron.dispatcher.run_shell_command", return_value=("output", True))
    async def test_silent_notification(self, mock_run, tmp_path):
        job = {"id": "sil", "name": "Silent", "command": "echo hi", "notify": {"type": "silent"}}
        await dispatcher.execute_job(job)
        log_file = tmp_path / "logs" / "sil.log"
        assert "logged only" in log_file.read_text()

    @pytest.mark.asyncio
    @patch(
        "cron.dispatcher.run_agent_job",
        return_value=("No response generated (empty Codex output).", False),
    )
    async def test_empty_output_can_be_treated_as_success(self, mock_run, tmp_path):
        job = {
            "id": "quiet",
            "name": "Quiet Job",
            "prompt": "do the thing",
            "empty_output_ok": True,
            "notify": {"type": "silent"},
        }
        result = await dispatcher.execute_job(job)

        assert result is True
        log_file = tmp_path / "logs" / "quiet.log"
        assert "Treated as success" in log_file.read_text()
