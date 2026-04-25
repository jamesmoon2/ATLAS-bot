"""Tests for bot model get/set preferences."""

import pytest

import bot
from channel_configs import ChannelConfig


class TestGetChannelModel:
    """get_channel_model() reads model preference from model.txt."""

    @pytest.fixture(autouse=True)
    def _patch(self, sessions_dir, monkeypatch):
        monkeypatch.setenv("ATLAS_AGENT_PROVIDER", "claude")
        monkeypatch.setattr(bot, "SESSIONS_DIR", str(sessions_dir))
        self.sessions_dir = sessions_dir

    def test_default_is_opus(self):
        assert bot.get_channel_model(100) == "opus"

    def test_default_comes_from_channel_config(self):
        config = ChannelConfig(
            key="test",
            role_description="Test channel",
            webhook_env="DISCORD_WEBHOOK_TEST",
            default_model="sonnet",
        )
        assert bot.get_channel_model(100, config) == "sonnet"

    def test_reads_from_file(self):
        channel_dir = self.sessions_dir / "100"
        channel_dir.mkdir()
        (channel_dir / "model.txt").write_text("sonnet")
        assert bot.get_channel_model(100) == "sonnet"

    def test_strips_whitespace(self):
        channel_dir = self.sessions_dir / "100"
        channel_dir.mkdir()
        (channel_dir / "model.txt").write_text("  opus \n")
        assert bot.get_channel_model(100) == "opus"

    def test_falls_back_to_codex_default_for_incompatible_model(self, monkeypatch):
        monkeypatch.setenv("ATLAS_AGENT_PROVIDER", "codex")
        channel_dir = self.sessions_dir / "100"
        channel_dir.mkdir()
        (channel_dir / "model.txt").write_text("opus")
        assert bot.get_channel_model(100) == "gpt-5.4"


class TestSetChannelModel:
    """set_channel_model() writes model preference."""

    @pytest.fixture(autouse=True)
    def _patch(self, sessions_dir, monkeypatch):
        monkeypatch.setenv("ATLAS_AGENT_PROVIDER", "claude")
        monkeypatch.setattr(bot, "SESSIONS_DIR", str(sessions_dir))
        self.sessions_dir = sessions_dir

    def test_set_then_get(self):
        bot.set_channel_model(100, "sonnet")
        assert bot.get_channel_model(100) == "sonnet"

    def test_overwrites_previous(self):
        bot.set_channel_model(100, "sonnet")
        bot.set_channel_model(100, "opus")
        assert bot.get_channel_model(100) == "opus"

    def test_creates_session_dir(self):
        """set_channel_model calls ensure_channel_session."""
        bot.set_channel_model(100, "sonnet")
        assert (self.sessions_dir / "100").is_dir()

    def test_codex_model_round_trip(self, monkeypatch):
        monkeypatch.setenv("ATLAS_AGENT_PROVIDER", "codex")
        bot.set_channel_model(100, "gpt-5.4")
        assert bot.get_channel_model(100) == "gpt-5.4"
