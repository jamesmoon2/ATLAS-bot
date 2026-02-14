"""Tests for bot model get/set preferences."""

import pytest

import bot


class TestGetChannelModel:
    """get_channel_model() reads model preference from model.txt."""

    @pytest.fixture(autouse=True)
    def _patch(self, sessions_dir, monkeypatch):
        monkeypatch.setattr(bot, "SESSIONS_DIR", str(sessions_dir))
        self.sessions_dir = sessions_dir

    def test_default_is_opus(self):
        assert bot.get_channel_model(100) == "opus"

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


class TestSetChannelModel:
    """set_channel_model() writes model preference."""

    @pytest.fixture(autouse=True)
    def _patch(self, sessions_dir, monkeypatch):
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
