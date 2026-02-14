"""Tests for bot.run_claude() subprocess invocation."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import bot


class TestRunClaude:
    """run_claude() invokes Claude CLI and parses JSON output."""

    @pytest.fixture(autouse=True)
    def _patch(self, sessions_dir, monkeypatch):
        monkeypatch.setattr(bot, "SESSIONS_DIR", str(sessions_dir))
        self.sessions_dir = sessions_dir

    def _mock_process(self, stdout=b"", stderr=b"", returncode=0):
        proc = MagicMock()
        proc.returncode = returncode
        proc.communicate = AsyncMock(return_value=(stdout, stderr))
        proc.kill = MagicMock()
        return proc

    @pytest.mark.asyncio
    @patch("bot.asyncio.create_subprocess_exec")
    @patch("bot.asyncio.wait_for")
    async def test_json_response_parsed(self, mock_wait, mock_exec):
        data = {"result": "Hello!", "modelUsage": {}}
        proc = self._mock_process(stdout=json.dumps(data).encode())
        mock_exec.return_value = proc
        mock_wait.return_value = (json.dumps(data).encode(), b"")

        result = await bot.run_claude(100, "hi")
        assert result == "Hello!"

    @pytest.mark.asyncio
    @patch("bot.asyncio.create_subprocess_exec")
    @patch("bot.asyncio.wait_for")
    async def test_fallback_on_json_error(self, mock_wait, mock_exec):
        proc = self._mock_process(stdout=b"plain text response")
        mock_exec.return_value = proc
        mock_wait.return_value = (b"plain text response", b"")

        result = await bot.run_claude(100, "hi")
        assert result == "plain text response"

    @pytest.mark.asyncio
    @patch("bot.asyncio.create_subprocess_exec")
    @patch("bot.asyncio.wait_for")
    async def test_empty_result_with_stderr(self, mock_wait, mock_exec):
        data = {"result": ""}
        proc = self._mock_process()
        mock_exec.return_value = proc
        mock_wait.return_value = (json.dumps(data).encode(), b"some error")

        result = await bot.run_claude(100, "hi")
        assert "some error" in result

    @pytest.mark.asyncio
    @patch("bot.asyncio.create_subprocess_exec")
    @patch("bot.asyncio.wait_for", side_effect=asyncio.TimeoutError)
    async def test_timeout_kills_process(self, mock_wait, mock_exec):
        proc = self._mock_process()
        mock_exec.return_value = proc

        result = await bot.run_claude(100, "hi")
        assert "timed out" in result.lower()
        proc.kill.assert_called_once()

    @pytest.mark.asyncio
    @patch("bot.asyncio.create_subprocess_exec", side_effect=FileNotFoundError("claude"))
    async def test_generic_exception(self, mock_exec):
        result = await bot.run_claude(100, "hi")
        assert "Error" in result

    @pytest.mark.asyncio
    @patch("bot.asyncio.create_subprocess_exec")
    @patch("bot.asyncio.wait_for")
    async def test_correct_model_passed(self, mock_wait, mock_exec):
        """Model from get_channel_model is passed to CLI."""
        bot.set_channel_model(100, "sonnet")
        data = {"result": "ok", "modelUsage": {}}
        proc = self._mock_process()
        mock_exec.return_value = proc
        mock_wait.return_value = (json.dumps(data).encode(), b"")

        await bot.run_claude(100, "hi")

        # Check the --model arg
        call_args = mock_exec.call_args[0]
        model_idx = list(call_args).index("--model")
        assert call_args[model_idx + 1] == "sonnet"

    @pytest.mark.asyncio
    @patch("bot.asyncio.create_subprocess_exec")
    @patch("bot.asyncio.wait_for")
    async def test_cwd_is_channel_session(self, mock_wait, mock_exec):
        data = {"result": "ok", "modelUsage": {}}
        proc = self._mock_process()
        mock_exec.return_value = proc
        mock_wait.return_value = (json.dumps(data).encode(), b"")

        await bot.run_claude(100, "hi")

        call_kwargs = mock_exec.call_args[1]
        assert str(100) in call_kwargs["cwd"]

    @pytest.mark.asyncio
    @patch("bot.asyncio.create_subprocess_exec")
    @patch("bot.asyncio.wait_for")
    async def test_no_response_fallback(self, mock_wait, mock_exec):
        data = {"result": ""}
        proc = self._mock_process()
        mock_exec.return_value = proc
        mock_wait.return_value = (json.dumps(data).encode(), b"")

        result = await bot.run_claude(100, "hi")
        assert result == "No response from Claude."
