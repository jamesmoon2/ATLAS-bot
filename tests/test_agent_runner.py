"""Tests for the provider-agnostic agent runner."""

from __future__ import annotations

import pytest

import agent_runner
from mcp_tooling import normalize_allowed_tools_for_provider


class _FakeProcess:
    def __init__(self):
        self.returncode = 0

    async def communicate(self):
        return b"", b""


@pytest.mark.asyncio
async def test_run_codex_exec_uses_argument_separator(tmp_path, monkeypatch):
    captured: dict[str, tuple] = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return _FakeProcess()

    monkeypatch.setattr(agent_runner.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    await agent_runner._run_codex_exec(
        workdir=str(tmp_path),
        prompt="---\nUser request:\nReply with READY",
        model="gpt-5.4",
        bot_dir=str(tmp_path),
        vault_path=str(tmp_path),
        image_paths=[],
        resume_last=False,
        timeout=10,
    )

    args = list(captured["args"])
    separator_index = args.index("--")
    assert args[separator_index + 1] == "---\nUser request:\nReply with READY"


def test_needs_calendar_context_for_codex_google_calendar_tools():
    assert agent_runner._needs_calendar_context(
        ["mcp__codex_apps__google_calendar_create_event"], "write a workout plan"
    )


def test_needs_calendar_context_for_legacy_google_calendar_tools():
    assert agent_runner._needs_calendar_context(
        ["mcp__google-calendar__create-event"], "write a workout plan"
    )


def test_needs_calendar_context_for_atlas_google_calendar_tools():
    assert agent_runner._needs_calendar_context(
        ["atlas__google_calendar__create_event"], "write a workout plan"
    )


def test_normalize_allowed_tools_maps_atlas_names_for_claude():
    normalized = normalize_allowed_tools_for_provider(
        [
            "Read",
            "atlas__google_calendar__create_event",
            "atlas__gmail__list_labels",
        ],
        "claude",
    )

    assert normalized == [
        "Read",
        "mcp__google-calendar__create-event",
        "mcp__gmail__list_email_labels",
    ]


def test_normalize_allowed_tools_maps_legacy_names_for_codex():
    normalized = normalize_allowed_tools_for_provider(
        [
            "Read",
            "mcp__google-calendar__search-events",
            "mcp__google-calendar__list-calendars",
        ],
        "codex",
    )

    assert normalized == [
        "Read",
        "mcp__codex_apps__google_calendar_search_events",
        "mcp__codex_apps__google_calendar_get_profile",
    ]


def test_normalize_allowed_tools_maps_atlas_names_for_codex():
    normalized = normalize_allowed_tools_for_provider(
        [
            "Read",
            "atlas__google_calendar__search_events",
            "atlas__google_calendar__get_profile",
            "atlas__gmail__list_labels",
        ],
        "codex",
    )

    assert normalized == [
        "Read",
        "mcp__codex_apps__google_calendar_search_events",
        "mcp__codex_apps__google_calendar_get_profile",
        "mcp__codex_apps__gmail_list_labels",
    ]


def test_build_codex_env_uses_managed_bot_home(tmp_path, monkeypatch):
    monkeypatch.delenv("ATLAS_CODEX_HOME", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)

    env = agent_runner._build_codex_env(str(tmp_path), str(tmp_path / "vault"))
    config_path = tmp_path / ".atlas-codex-home" / "config.toml"

    assert env["CODEX_HOME"] == str(tmp_path / ".atlas-codex-home")
    assert config_path.exists()
    config = config_path.read_text()
    assert '[plugins."google-calendar@openai-curated"]' in config
    assert "[mcp_servers.oura]" in config
    assert "[mcp_servers.weather]" in config


def test_build_codex_env_respects_configured_home(tmp_path, monkeypatch):
    custom_home = tmp_path / "custom-codex-home"
    monkeypatch.setenv("ATLAS_CODEX_HOME", str(custom_home))
    monkeypatch.delenv("CODEX_HOME", raising=False)

    env = agent_runner._build_codex_env(str(tmp_path), str(tmp_path / "vault"))

    assert env["CODEX_HOME"] == str(custom_home)
    assert (custom_home / "config.toml").exists()


def test_codex_command_prefix_uses_configured_sandbox_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_CODEX_SANDBOX", "danger-full-access")

    prefix = agent_runner._codex_command_prefix(
        workdir=str(tmp_path),
        model="gpt-5.4",
        bot_dir=str(tmp_path),
        vault_path=str(tmp_path),
    )

    sandbox_index = prefix.index("-s")
    assert prefix[sandbox_index + 1] == "danger-full-access"
