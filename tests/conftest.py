"""Shared test fixtures for ATLAS Bot tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Environment / directory fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def env_vars(tmp_path, monkeypatch):
    """Set core env vars to tmp_path so tests never touch real files."""
    vault = tmp_path / "vault"
    sessions = tmp_path / "sessions"
    vault.mkdir()
    sessions.mkdir()
    monkeypatch.setenv("VAULT_PATH", str(vault))
    monkeypatch.setenv("SESSIONS_DIR", str(sessions))
    monkeypatch.setenv("BOT_DIR", str(tmp_path / "bot"))
    return {"vault": vault, "sessions": sessions}


@pytest.fixture
def sessions_dir(tmp_path):
    d = tmp_path / "sessions"
    d.mkdir()
    return d


@pytest.fixture
def vault_dir(tmp_path):
    d = tmp_path / "vault"
    d.mkdir()
    return d


@pytest.fixture
def medications_file(vault_dir):
    """Create a realistic Medications.md with Medrol + Vitaplex dosing tables."""
    health_dir = vault_dir / "Areas" / "Health"
    health_dir.mkdir(parents=True)
    med_file = health_dir / "Medications.md"
    med_file.write_text(
        "# Medications\n"
        "\n"
        "## Medrol 5mg\n"
        "\n"
        "Some info about Medrol.\n"
        "\n"
        "## Dosing Log\n"
        "\n"
        "| Date | Dose | Side Effects | Notes | Source |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| 2025-01-01 | 2mg | — | Wed AM | Manual |\n"
        "\n"
        "---\n"
        "\n"
        "## Vitaplex\n"
        "\n"
        "Some info about Vitaplex.\n"
        "\n"
        "### Dosing Log\n"
        "\n"
        "| Date | Medication | Notes | Source |\n"
        "| --- | --- | --- | --- |\n"
        "| 2025-01-02 | Vitaplex | Thu PM | Manual |\n"
        "\n"
        "---\n"
    )
    return med_file


# ---------------------------------------------------------------------------
# Discord mock factories
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_channel():
    """A mock Discord TextChannel."""
    ch = MagicMock()
    ch.id = 123456
    ch.name = "atlas"
    ch.send = AsyncMock()
    ch.typing = MagicMock(return_value=AsyncContextManager())
    return ch


@pytest.fixture
def mock_message(mock_channel):
    """A mock Discord Message (non-bot, in #atlas)."""
    msg = MagicMock()
    msg.author = MagicMock()
    msg.author.bot = False
    msg.channel = mock_channel
    msg.content = "Hello ATLAS"
    msg.mentions = []
    msg.attachments = []
    return msg


@pytest.fixture
def mock_attachment(tmp_path):
    """A mock Discord Attachment that saves to disk."""
    att = MagicMock()
    att.filename = "photo.png"
    att.save = AsyncMock()
    return att


@pytest.fixture
def mock_reaction():
    """A mock Discord Reaction with a checkmark emoji."""
    reaction = MagicMock()
    reaction.emoji = "✅"
    reaction.message = MagicMock()
    reaction.message.author = MagicMock()
    reaction.message.content = "**Medication Reminder** - Medrol 5mg"
    reaction.message.created_at = MagicMock()
    reaction.message.created_at.isoformat.return_value = "2025-06-11T12:00:00+00:00"
    reaction.message.add_reaction = AsyncMock()
    return reaction


# ---------------------------------------------------------------------------
# Dispatcher fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_jobs():
    """Minimal jobs config for dispatcher tests."""
    return {
        "jobs": [
            {
                "id": "test_job",
                "name": "Test Job",
                "schedule": "30 5 * * *",
                "timezone": "America/Los_Angeles",
                "enabled": True,
                "model": "opus",
                "timeout_seconds": 60,
                "allowed_tools": ["Read"],
                "prompt": "Hello {current_datetime}",
                "notify": {
                    "type": "webhook",
                    "url_env": "DISCORD_WEBHOOK_URL",
                    "username": "Test",
                },
            },
            {
                "id": "shell_job",
                "name": "Shell Job",
                "schedule": "0 12 * * *",
                "timezone": "UTC",
                "enabled": True,
                "command": "echo hello",
                "notify": {"type": "silent"},
            },
        ]
    }


@pytest.fixture
def state_dir(tmp_path):
    d = tmp_path / "state"
    d.mkdir()
    return d


@pytest.fixture
def mock_process():
    """A mock asyncio subprocess with configurable stdout/stderr."""
    proc = MagicMock()
    proc.returncode = 0
    proc.communicate = AsyncMock(return_value=(b"output", b""))
    proc.kill = MagicMock()
    return proc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class AsyncContextManager:
    """Simple async context manager for mocking ``async with channel.typing()``."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass
