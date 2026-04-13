"""Tests for bot session management (ensure/reset/locks)."""

import json
import os

import pytest

import bot


class TestGetChannelLock:
    """get_channel_lock() returns consistent asyncio.Lock per channel."""

    def setup_method(self):
        bot.channel_locks.clear()

    def test_same_channel_same_lock(self):
        lock1 = bot.get_channel_lock(100)
        lock2 = bot.get_channel_lock(100)
        assert lock1 is lock2

    def test_different_channel_different_lock(self):
        lock1 = bot.get_channel_lock(100)
        lock2 = bot.get_channel_lock(200)
        assert lock1 is not lock2

    def test_lock_stored_in_dict(self):
        bot.get_channel_lock(100)
        assert 100 in bot.channel_locks


class TestEnsureChannelSession:
    """ensure_channel_session() creates session dirs and writes config."""

    @pytest.fixture(autouse=True)
    def _patch(self, tmp_path, sessions_dir, monkeypatch):
        monkeypatch.setattr(bot, "SESSIONS_DIR", str(sessions_dir))
        bot_dir = tmp_path / "bot"
        (bot_dir / ".claude" / "skills").mkdir(parents=True)
        vault_dir = tmp_path / "vault" / "System"
        vault_dir.mkdir(parents=True)
        system_prompt = vault_dir / "claude.md"
        context_file = vault_dir / "ATLAS-Context.md"
        system_prompt.write_text("System prompt")
        context_file.write_text("Persistent context")
        monkeypatch.setattr(bot, "BOT_DIR", str(bot_dir))
        monkeypatch.setattr(bot, "SYSTEM_PROMPT_PATH", str(system_prompt))
        monkeypatch.setattr(bot, "CONTEXT_PATH", str(context_file))
        self.sessions_dir = sessions_dir
        self.bot_dir = bot_dir

    def test_creates_channel_dir(self):
        result = bot.ensure_channel_session(100)
        assert os.path.isdir(result)

    def test_creates_claude_subdir(self):
        bot.ensure_channel_session(100)
        claude_dir = self.sessions_dir / "100" / ".claude"
        assert claude_dir.is_dir()

    def test_writes_settings_json(self):
        bot.ensure_channel_session(100)
        settings = self.sessions_dir / "100" / ".claude" / "settings.json"
        assert settings.exists()
        data = json.loads(settings.read_text())
        assert "hooks" in data

    def test_writes_permissions_json(self):
        bot.ensure_channel_session(100)
        perms = self.sessions_dir / "100" / ".claude" / "settings.local.json"
        assert perms.exists()
        data = json.loads(perms.read_text())
        assert "permissions" in data

    def test_idempotent(self):
        """Calling twice doesn't error and overwrites config."""
        bot.ensure_channel_session(100)
        bot.ensure_channel_session(100)
        settings = self.sessions_dir / "100" / ".claude" / "settings.json"
        assert settings.exists()

    def test_returns_channel_dir_path(self):
        result = bot.ensure_channel_session(100)
        assert result == str(self.sessions_dir / "100")

    def test_creates_skills_symlink_to_repo_local_skills(self):
        bot.ensure_channel_session(100)
        skills_link = self.sessions_dir / "100" / ".claude" / "skills"
        assert skills_link.is_symlink()
        assert os.path.realpath(skills_link) == os.path.realpath(
            self.bot_dir / ".claude" / "skills"
        )

    def test_updates_existing_skills_symlink_target(self, tmp_path):
        wrong_target = tmp_path / "wrong-skills"
        wrong_target.mkdir()

        claude_dir = self.sessions_dir / "100" / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        skills_link = claude_dir / "skills"
        skills_link.symlink_to(wrong_target)

        bot.ensure_channel_session(100)

        assert skills_link.is_symlink()
        assert os.path.realpath(skills_link) == os.path.realpath(
            self.bot_dir / ".claude" / "skills"
        )

    def test_writes_codex_agents_file(self):
        bot.ensure_channel_session(100)
        agents_file = self.sessions_dir / "100" / "AGENTS.md"
        assert agents_file.exists()
        contents = agents_file.read_text()
        assert "System prompt" in contents
        assert "Persistent context" in contents

    def test_writes_codex_workout_helper(self):
        bot.ensure_channel_session(100)
        helper_file = self.sessions_dir / "100" / "ATLAS-Workout-Postwrite.md"
        assert helper_file.exists()
        assert "workout log" in helper_file.read_text().lower()


class TestResetChannelSession:
    """reset_channel_session() removes session dirs."""

    @pytest.fixture(autouse=True)
    def _patch(self, sessions_dir, monkeypatch):
        monkeypatch.setattr(bot, "SESSIONS_DIR", str(sessions_dir))
        self.sessions_dir = sessions_dir

    def test_removes_existing_session(self):
        bot.ensure_channel_session(100)
        assert bot.reset_channel_session(100) is True
        assert not (self.sessions_dir / "100").exists()

    def test_returns_false_when_nothing_to_clear(self):
        assert bot.reset_channel_session(999) is False

    def test_clears_after_reset(self):
        """After reset, directory is gone."""
        bot.ensure_channel_session(100)
        bot.reset_channel_session(100)
        assert not (self.sessions_dir / "100").exists()

    def test_reset_then_ensure_creates_fresh(self):
        """Session can be recreated after reset."""
        bot.ensure_channel_session(100)
        bot.reset_channel_session(100)
        result = bot.ensure_channel_session(100)
        assert os.path.isdir(result)
