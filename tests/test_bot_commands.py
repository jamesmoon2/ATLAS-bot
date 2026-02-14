"""Tests for bot on_message() command routing."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import bot
from tests.conftest import AsyncContextManager


@pytest.fixture(autouse=True)
def _patch_env(sessions_dir, monkeypatch):
    monkeypatch.setattr(bot, "SESSIONS_DIR", str(sessions_dir))
    bot.channel_locks.clear()


@pytest.fixture(autouse=True)
def _mock_client(monkeypatch):
    """Replace bot.client with a MagicMock so .user is settable."""
    mock_client = MagicMock()
    mock_client.user = MagicMock()
    mock_client.user.mentioned_in = MagicMock(return_value=False)
    monkeypatch.setattr(bot, "client", mock_client)
    return mock_client


def _make_message(content, channel_name="atlas", is_bot=False, channel_id=100):
    msg = MagicMock()
    msg.author = MagicMock()
    msg.author.bot = is_bot
    msg.channel = MagicMock()
    msg.channel.id = channel_id
    msg.channel.name = channel_name
    msg.channel.send = AsyncMock()
    msg.channel.typing = MagicMock(return_value=AsyncContextManager())
    msg.content = content
    msg.mentions = []
    msg.attachments = []
    return msg


class TestMessageFiltering:
    """Messages from bots and non-atlas channels are ignored."""

    @pytest.mark.asyncio
    async def test_bot_message_ignored(self):
        msg = _make_message("hello", is_bot=True)
        await bot.on_message(msg)
        msg.channel.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_atlas_non_mention_ignored(self):
        msg = _make_message("hello", channel_name="general")
        bot.client.user.mentioned_in = MagicMock(return_value=False)
        await bot.on_message(msg)
        msg.channel.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_atlas_channel_processed(self):
        msg = _make_message("!help", channel_name="atlas")
        await bot.on_message(msg)
        msg.channel.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_mention_in_other_channel_processed(self):
        msg = _make_message("!help", channel_name="general")
        bot.client.user.mentioned_in = MagicMock(return_value=True)
        await bot.on_message(msg)
        msg.channel.send.assert_called_once()


class TestHelpCommand:
    """!help returns help text."""

    @pytest.mark.asyncio
    async def test_help_command(self):
        msg = _make_message("!help")
        await bot.on_message(msg)
        sent = msg.channel.send.call_args[0][0]
        assert "ATLAS Commands" in sent

    @pytest.mark.asyncio
    async def test_help_without_bang(self):
        msg = _make_message("help")
        await bot.on_message(msg)
        sent = msg.channel.send.call_args[0][0]
        assert "ATLAS Commands" in sent


class TestResetCommand:
    """!reset / !clear clears the session."""

    @pytest.mark.asyncio
    async def test_reset_existing_session(self):
        bot.ensure_channel_session(100)
        msg = _make_message("!reset", channel_id=100)
        await bot.on_message(msg)
        sent = msg.channel.send.call_args[0][0]
        assert "cleared" in sent.lower()

    @pytest.mark.asyncio
    async def test_reset_no_session(self):
        msg = _make_message("!reset", channel_id=999)
        await bot.on_message(msg)
        sent = msg.channel.send.call_args[0][0]
        assert "no session" in sent.lower()

    @pytest.mark.asyncio
    async def test_clear_alias(self):
        msg = _make_message("!clear")
        await bot.on_message(msg)
        msg.channel.send.assert_called_once()


class TestModelCommand:
    """!model gets/sets model preference."""

    @pytest.mark.asyncio
    async def test_show_current_model(self):
        msg = _make_message("!model", channel_id=100)
        await bot.on_message(msg)
        sent = msg.channel.send.call_args[0][0]
        assert "opus" in sent.lower()

    @pytest.mark.asyncio
    async def test_set_valid_model(self):
        msg = _make_message("!model sonnet", channel_id=100)
        await bot.on_message(msg)
        sent = msg.channel.send.call_args[0][0]
        assert "sonnet" in sent.lower()

    @pytest.mark.asyncio
    async def test_set_invalid_model(self):
        msg = _make_message("!model gpt4", channel_id=100)
        await bot.on_message(msg)
        sent = msg.channel.send.call_args[0][0]
        assert "invalid" in sent.lower()


class TestClaudeInvocation:
    """Normal messages invoke run_claude and handle responses."""

    @pytest.mark.asyncio
    @patch("bot.run_claude", return_value="Hello!")
    async def test_short_response(self, mock_claude):
        msg = _make_message("say hello")
        await bot.on_message(msg)
        msg.channel.send.assert_called_once_with("Hello!")

    @pytest.mark.asyncio
    @patch("bot.run_claude", return_value="x" * 3000)
    async def test_long_response_chunked(self, mock_claude):
        msg = _make_message("write essay")
        await bot.on_message(msg)
        assert msg.channel.send.call_count >= 2

    @pytest.mark.asyncio
    async def test_empty_message_no_attachments(self):
        msg = _make_message("")
        await bot.on_message(msg)
        sent = msg.channel.send.call_args[0][0]
        assert "what do you need" in sent.lower()

    @pytest.mark.asyncio
    @patch("bot.run_claude", return_value="busy response")
    async def test_lock_busy_message(self, mock_claude):
        """When lock is held, user gets a 'processing' message."""
        msg = _make_message("hello", channel_id=300)

        lock = bot.get_channel_lock(300)
        await lock.acquire()

        async def release_later():
            await asyncio.sleep(0.05)
            lock.release()

        asyncio.create_task(release_later())
        await bot.on_message(msg)

        calls = [c[0][0] for c in msg.channel.send.call_args_list]
        assert any("processing" in c.lower() for c in calls)
