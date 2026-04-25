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
        monkeypatch.setenv("ATLAS_AGENT_PROVIDER", "claude")
        monkeypatch.delenv("ATLAS_CONFIGURED_CHANNELS", raising=False)
        for key in (
            "ATLAS_CHANNEL_ID_ATLAS",
            "ATLAS_CHANNEL_ID_HEALTH",
            "ATLAS_CHANNEL_ID_PROJECTS",
            "ATLAS_CHANNEL_ID_BRIEFINGS",
            "ATLAS_CHANNEL_ID_ATLAS_DEV",
        ):
            monkeypatch.delenv(key, raising=False)
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
        bot.ensure_channel_session(100, channel_name="health")
        settings = self.sessions_dir / "100" / ".claude" / "settings.json"
        assert settings.exists()
        data = json.loads(settings.read_text())
        assert "hooks" in data
        session_start_hooks = data["hooks"]["SessionStart"][0]["hooks"]
        commands = [hook["command"] for hook in session_start_hooks]
        assert "ATLAS-Channel-Role.md" in commands[1]

    def test_writes_permissions_json(self):
        bot.ensure_channel_session(100)
        perms = self.sessions_dir / "100" / ".claude" / "settings.local.json"
        assert perms.exists()
        data = json.loads(perms.read_text())
        assert "permissions" in data
        assert "mcp__google_bot__*" in data["permissions"]["allow"]
        assert "mcp__whoop__*" in data["permissions"]["allow"]

    def test_merges_repo_local_claude_settings_into_session_settings(self):
        project_settings = self.bot_dir / ".claude" / "settings.local.json"
        project_settings.write_text(
            json.dumps(
                {
                    "permissions": {
                        "allow": ["Bash", "mcp__garmin__*", "mcp__whoop__*"],
                        "deny": ["Bash(rm:*)"],
                    },
                    "enabledMcpjsonServers": ["garmin"],
                }
            ),
            encoding="utf-8",
        )

        bot.ensure_channel_session(100)

        data = json.loads(
            (self.sessions_dir / "100" / ".claude" / "settings.local.json").read_text()
        )
        assert "Bash" in data["permissions"]["allow"]
        assert "mcp__garmin__*" in data["permissions"]["allow"]
        assert "mcp__whoop__*" in data["permissions"]["allow"]
        assert "mcp__google_bot__*" in data["permissions"]["allow"]
        assert "Bash(rm:*)" in data["permissions"]["deny"]
        assert data["enabledMcpjsonServers"] == ["garmin"]

    def test_writes_google_calendar_hook_matchers_for_both_namespaces(self):
        bot.ensure_channel_session(100)
        settings = self.sessions_dir / "100" / ".claude" / "settings.json"
        data = json.loads(settings.read_text())
        matchers = [hook["matcher"] for hook in data["hooks"]["PreToolUse"]]

        assert "mcp__google_bot__create_event" in matchers
        assert "mcp__google_bot__update_event" in matchers
        assert "mcp__codex_apps__google_calendar_create_event" in matchers
        assert "mcp__google-calendar__create-event" in matchers

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
        assert "claudiamooney00@gmail.com" in contents
        assert "jamesmoon2@gmail.com" in contents
        assert "lorzem15@gmail.com" in contents

    def test_writes_codex_workout_helper(self):
        bot.ensure_channel_session(100)
        helper_file = self.sessions_dir / "100" / "ATLAS-Workout-Postwrite.md"
        assert helper_file.exists()
        assert "workout log" in helper_file.read_text().lower()

    def test_writes_garmin_workout_helper(self):
        bot.ensure_channel_session(100)
        helper_file = self.sessions_dir / "100" / "ATLAS-Garmin-Workout-Helper.md"
        assert helper_file.exists()
        contents = helper_file.read_text()
        assert "mcp__garmin__" in contents
        assert "garmin_workout_fallback.py" in contents

    def test_writes_provider_neutral_session_metadata(self):
        bot.ensure_channel_session(100, channel_name="health")
        metadata_file = self.sessions_dir / "100" / "ATLAS-Session.json"
        assert metadata_file.exists()
        data = json.loads(metadata_file.read_text())
        assert data["active_provider"] == "claude"
        assert data["channel_dir"].endswith("/100")
        assert data["skills_dir"].endswith("/.claude/skills")
        assert data["channel_id"] == 100
        assert data["channel_name"] == "health"
        assert data["channel_key"] == "health"
        assert data["default_model"] == "opus"

    def test_writes_channel_role_context(self):
        bot.ensure_channel_session(100, channel_name="health")
        role_file = self.sessions_dir / "100" / "ATLAS-Channel-Role.md"
        assert role_file.exists()
        contents = role_file.read_text()
        assert "Channel: #health" in contents
        assert "health-pattern-monitor" in contents


class TestResetChannelSession:
    """reset_channel_session() removes session dirs."""

    @pytest.fixture(autouse=True)
    def _patch(self, sessions_dir, monkeypatch, tmp_path):
        monkeypatch.setenv("ATLAS_AGENT_PROVIDER", "claude")
        monkeypatch.setattr(bot, "SESSIONS_DIR", str(sessions_dir))
        self.home_dir = tmp_path / "home"
        monkeypatch.setenv("HOME", str(self.home_dir))
        self.sessions_dir = sessions_dir

    def test_removes_existing_session(self):
        bot.ensure_channel_session(100)
        assert bot.reset_channel_session(100) is True
        assert not (self.sessions_dir / "100").exists()

    def test_removes_external_claude_session_storage(self):
        channel_dir = self.sessions_dir / "100"
        channel_dir.mkdir(parents=True, exist_ok=True)
        claude_project_name = str(channel_dir.resolve()).replace("/", "-")
        claude_session_dir = self.home_dir / ".claude" / "projects" / claude_project_name
        claude_session_dir.mkdir(parents=True)

        assert bot.reset_channel_session(100) is True
        assert not claude_session_dir.exists()

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
