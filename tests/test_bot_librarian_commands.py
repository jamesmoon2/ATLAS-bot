"""Tests for librarian-oriented bot commands."""

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
    mock_client = MagicMock()
    mock_client.user = MagicMock()
    mock_client.user.mentioned_in = MagicMock(return_value=False)
    monkeypatch.setattr(bot, "client", mock_client)
    return mock_client


def _make_message(content, channel_name="atlas", channel_id=100):
    msg = MagicMock()
    msg.author = MagicMock()
    msg.author.bot = False
    msg.channel = MagicMock()
    msg.channel.id = channel_id
    msg.channel.name = channel_name
    msg.channel.send = AsyncMock()
    msg.channel.typing = MagicMock(return_value=AsyncContextManager())
    msg.content = content
    msg.mentions = []
    msg.attachments = []
    return msg


class TestLibrarianCommands:
    @pytest.mark.asyncio
    @patch("bot.run_claude", return_value="Recall result")
    async def test_recall_uses_librarian_prompt(self, mock_claude):
        msg = _make_message("!recall atlas roadmap")

        await bot.on_message(msg)

        prompt = mock_claude.call_args[0][1]
        assert "vault-index.json" in prompt
        assert "atlas roadmap" in prompt
        assert "second-brain librarian" in prompt.lower()
        msg.channel.send.assert_called_once_with("Recall result")

    @pytest.mark.asyncio
    async def test_recall_requires_query(self):
        msg = _make_message("!recall")

        await bot.on_message(msg)

        msg.channel.send.assert_called_once_with("Usage: !recall <query>")

    @pytest.mark.asyncio
    @patch("bot.run_claude", return_value="Open loops")
    async def test_open_loops_command(self, mock_claude):
        msg = _make_message("!open-loops")

        await bot.on_message(msg)

        prompt = mock_claude.call_args[0][1]
        assert "open loops" in prompt.lower()
        assert "vault-index.json" in prompt

    @pytest.mark.asyncio
    @patch("bot.run_claude", return_value="Recent notes")
    async def test_recent_notes_command(self, mock_claude):
        msg = _make_message("!recent-notes")

        await bot.on_message(msg)

        prompt = mock_claude.call_args[0][1]
        assert "recently updated notes" in prompt.lower()

    @pytest.mark.asyncio
    @patch("bot.run_claude", return_value="Orphan notes")
    async def test_orphan_notes_command(self, mock_claude):
        msg = _make_message("!orphan-notes")

        await bot.on_message(msg)

        prompt = mock_claude.call_args[0][1]
        assert "orphan notes" in prompt.lower()

    @pytest.mark.asyncio
    @patch("bot.run_claude", return_value="Digest")
    async def test_librarian_digest_command(self, mock_claude):
        msg = _make_message("!librarian")

        await bot.on_message(msg)

        prompt = mock_claude.call_args[0][1]
        assert "compact librarian digest" in prompt.lower()

    @pytest.mark.asyncio
    async def test_help_mentions_librarian_commands(self):
        msg = _make_message("!help")

        await bot.on_message(msg)

        sent = msg.channel.send.call_args[0][0]
        assert "!recall <query>" in sent
        assert "!open-loops" in sent
        assert "!recent-notes" in sent
        assert "!orphan-notes" in sent
        assert "!librarian" in sent
