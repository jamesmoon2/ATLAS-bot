"""Tests for bot.run_claude()/run_agent() wrapper behavior."""

from unittest.mock import patch

import pytest

import bot


class TestRunClaude:
    """run_claude() delegates to the shared provider runner."""

    @pytest.fixture(autouse=True)
    def _patch(self, sessions_dir, monkeypatch, tmp_path):
        monkeypatch.setenv("ATLAS_AGENT_PROVIDER", "claude")
        monkeypatch.setattr(bot, "SESSIONS_DIR", str(sessions_dir))
        bot_dir = tmp_path / "bot"
        (bot_dir / ".claude" / "skills").mkdir(parents=True)
        monkeypatch.setattr(bot, "BOT_DIR", str(bot_dir))
        self.sessions_dir = sessions_dir

    @pytest.mark.asyncio
    @patch("bot.run_channel_message", return_value="Hello!")
    async def test_returns_runner_response(self, mock_runner):
        result = await bot.run_claude(100, "hi")
        assert result == "Hello!"
        mock_runner.assert_called_once()

    @pytest.mark.asyncio
    @patch("bot.run_channel_message", side_effect=FileNotFoundError("claude"))
    async def test_generic_exception(self, mock_runner):
        result = await bot.run_claude(100, "hi")
        assert "Error" in result

    @pytest.mark.asyncio
    @patch("bot.run_channel_message", return_value="ok")
    async def test_correct_model_passed(self, mock_runner):
        bot.set_channel_model(100, "sonnet")

        await bot.run_claude(100, "hi")

        assert mock_runner.call_args.kwargs["model"] == "sonnet"

    @pytest.mark.asyncio
    @patch("bot.run_channel_message", return_value="ok")
    async def test_channel_dir_is_session_dir(self, mock_runner):
        await bot.run_claude(100, "hi")

        channel_dir = mock_runner.call_args.kwargs["channel_dir"]
        assert str(100) in channel_dir

    @pytest.mark.asyncio
    @patch("bot.run_channel_message", return_value="ok")
    async def test_defaults_to_empty_attachment_paths(self, mock_runner):
        await bot.run_claude(100, "hi")

        assert mock_runner.call_args.kwargs["attachment_paths"] == []
