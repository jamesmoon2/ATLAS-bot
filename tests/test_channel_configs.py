"""Tests for configured Discord channel resolution."""

from channel_configs import get_channel_config, get_channel_config_by_key


def test_resolves_by_channel_id_before_name(monkeypatch):
    monkeypatch.setenv("ATLAS_CHANNEL_ID_HEALTH", "123")

    config = get_channel_config(channel_id=123, channel_name="projects")

    assert config is not None
    assert config.key == "health"


def test_resolves_by_channel_name(monkeypatch):
    monkeypatch.delenv("ATLAS_CONFIGURED_CHANNELS", raising=False)

    config = get_channel_config(channel_id=999, channel_name="briefings")

    assert config is not None
    assert config.key == "briefings"


def test_allowlist_disables_auto_configured_channel(monkeypatch):
    monkeypatch.setenv("ATLAS_CONFIGURED_CHANNELS", "atlas,health")

    assert get_channel_config(channel_id=999, channel_name="projects") is None
    assert get_channel_config_by_key("health").key == "health"
    assert get_channel_config_by_key("projects", honor_allowlist=False).key == "projects"


def test_invalid_channel_id_env_falls_back_to_name(monkeypatch):
    monkeypatch.setenv("ATLAS_CHANNEL_ID_HEALTH", "not-an-int")

    config = get_channel_config(channel_id=999, channel_name="health")

    assert config is not None
    assert config.key == "health"
