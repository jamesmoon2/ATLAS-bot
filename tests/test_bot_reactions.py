"""Tests for bot on_reaction_add() medication auto-logging."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import bot


@pytest.fixture(autouse=True)
def _patch_env(vault_dir, med_config, monkeypatch):
    monkeypatch.setattr(bot, "VAULT_PATH", str(vault_dir))


@pytest.fixture(autouse=True)
def _mock_client(monkeypatch):
    """Replace bot.client with a MagicMock so .user is settable."""
    mock_client = MagicMock()
    monkeypatch.setattr(bot, "client", mock_client)
    return mock_client


def _make_reaction(emoji, content, is_bot_author=True, user_is_bot=False, is_webhook=False):
    reaction = MagicMock()
    reaction.emoji = emoji
    reaction.message = MagicMock()
    reaction.message.author = MagicMock()
    reaction.message.content = content
    reaction.message.webhook_id = 123456 if is_webhook else None
    reaction.message.created_at = MagicMock()
    reaction.message.created_at.isoformat.return_value = "2025-06-11T12:00:00+00:00"
    reaction.message.add_reaction = AsyncMock()

    user = MagicMock()
    user.bot = user_is_bot
    user.name = "testuser"

    return reaction, user


class TestReactionFiltering:
    """Reactions that should be ignored."""

    @pytest.mark.asyncio
    async def test_bot_reaction_ignored(self):
        reaction, user = _make_reaction(
            "✅", "**Medication Reminder** - Medrol 5mg", user_is_bot=True
        )
        bot.client.user = reaction.message.author
        await bot.on_reaction_add(reaction, user)
        reaction.message.add_reaction.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_checkmark_ignored(self):
        reaction, user = _make_reaction("👍", "**Medication Reminder** - Medrol 5mg")
        bot.client.user = reaction.message.author
        await bot.on_reaction_add(reaction, user)
        reaction.message.add_reaction.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_bot_message_ignored(self):
        reaction, user = _make_reaction("✅", "**Medication Reminder** - Medrol 5mg")
        # Message author is NOT the bot
        bot.client.user = MagicMock()
        await bot.on_reaction_add(reaction, user)
        reaction.message.add_reaction.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_medication_message_ignored(self):
        reaction, user = _make_reaction("✅", "Just a regular message")
        bot.client.user = reaction.message.author
        await bot.on_reaction_add(reaction, user)
        reaction.message.add_reaction.assert_not_called()


class TestWebhookReaction:
    """Reactions on webhook-sent reminders (the real-world flow)."""

    @pytest.mark.asyncio
    @patch("bot.log_medication_dose", return_value=True)
    async def test_webhook_reminder_processed(self, mock_log, vault_dir):
        """Webhook messages (webhook_id set) should be processed even though
        the message author is not client.user."""
        sys_dir = vault_dir / "System"
        sys_dir.mkdir()
        (sys_dir / "agent-state.json").write_text("{}")

        reaction, user = _make_reaction(
            "✅",
            "**Medication Reminder**\n\nMedrol 5mg due this morning (Wed AM)",
            is_bot_author=False,
            is_webhook=True,
        )
        # Author is NOT the bot
        bot.client.user = MagicMock()
        await bot.on_reaction_add(reaction, user)
        mock_log.assert_called_once_with("Medrol 5mg", "2025-06-11T12:00:00+00:00")

    @pytest.mark.asyncio
    async def test_webhook_non_medication_ignored(self):
        reaction, user = _make_reaction(
            "✅",
            "Just a webhook message",
            is_bot_author=False,
            is_webhook=True,
        )
        bot.client.user = MagicMock()
        await bot.on_reaction_add(reaction, user)
        reaction.message.add_reaction.assert_not_called()


class TestMedicationParsing:
    """Correct medication name extracted from message content."""

    @pytest.mark.asyncio
    @patch("bot.log_medication_dose", return_value=True)
    async def test_medrol_parsed(self, mock_log, vault_dir):
        sys_dir = vault_dir / "System"
        sys_dir.mkdir()
        (sys_dir / "agent-state.json").write_text("{}")

        reaction, user = _make_reaction("✅", "**Medication Reminder** - Medrol 5mg is due")
        bot.client.user = reaction.message.author
        await bot.on_reaction_add(reaction, user)
        mock_log.assert_called_once_with("Medrol 5mg", "2025-06-11T12:00:00+00:00")

    @pytest.mark.asyncio
    @patch("bot.log_medication_dose", return_value=True)
    async def test_vitaplex_neupro_parsed(self, mock_log, vault_dir):
        sys_dir = vault_dir / "System"
        sys_dir.mkdir()
        (sys_dir / "agent-state.json").write_text("{}")

        reaction, user = _make_reaction("✅", "**Medication Reminder** - Vitaplex + Neupro 300 units due")
        bot.client.user = reaction.message.author
        await bot.on_reaction_add(reaction, user)
        mock_log.assert_called_once_with("Vitaplex + Neupro 300 units", "2025-06-11T12:00:00+00:00")

    @pytest.mark.asyncio
    @patch("bot.log_medication_dose", return_value=True)
    async def test_vitaplex_only_parsed(self, mock_log, vault_dir):
        sys_dir = vault_dir / "System"
        sys_dir.mkdir()
        (sys_dir / "agent-state.json").write_text("{}")

        reaction, user = _make_reaction("✅", "**Medication Reminder** - Vitaplex is due")
        bot.client.user = reaction.message.author
        await bot.on_reaction_add(reaction, user)
        mock_log.assert_called_once_with("Vitaplex", "2025-06-11T12:00:00+00:00")


class TestSuccessActions:
    """On successful log, pencil reaction + state update."""

    @pytest.mark.asyncio
    @patch("bot.log_medication_dose", return_value=True)
    async def test_pencil_reaction_added(self, mock_log, vault_dir):
        sys_dir = vault_dir / "System"
        sys_dir.mkdir()
        (sys_dir / "agent-state.json").write_text("{}")

        reaction, user = _make_reaction("✅", "**Medication Reminder** - Medrol 5mg")
        bot.client.user = reaction.message.author
        await bot.on_reaction_add(reaction, user)
        reaction.message.add_reaction.assert_called_with("📝")

    @pytest.mark.asyncio
    @patch("bot.log_medication_dose", return_value=True)
    async def test_agent_state_updated(self, mock_log, vault_dir):
        sys_dir = vault_dir / "System"
        sys_dir.mkdir()
        (sys_dir / "agent-state.json").write_text('{"med_reminders": {}}')

        reaction, user = _make_reaction("✅", "**Medication Reminder** - Medrol 5mg")
        bot.client.user = reaction.message.author
        await bot.on_reaction_add(reaction, user)

        state = json.loads((sys_dir / "agent-state.json").read_text())
        assert state["med_reminders"]["Medrol 5mg"]["confirmed"] is True
