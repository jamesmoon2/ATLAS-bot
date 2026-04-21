"""Tests for the provider-agnostic agent runner."""

from __future__ import annotations

import json
from pathlib import Path

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


@pytest.mark.asyncio
async def test_run_codex_exec_retries_without_sandbox_on_bwrap_error(tmp_path, monkeypatch):
    class _RetryProcess:
        def __init__(self, stdout: bytes):
            self.returncode = 0
            self._stdout = stdout

        async def communicate(self):
            return self._stdout, b""

    sandboxes: list[str] = []
    responses = iter(
        [
            "Blocked by sandbox",
            "2026-04-12T09:15:02Z",
        ]
    )

    async def fake_create_subprocess_exec(*args, **kwargs):
        args_list = list(args)
        sandbox_index = args_list.index("-s")
        sandboxes.append(args_list[sandbox_index + 1])
        if len(sandboxes) == 1:
            return _RetryProcess(agent_runner.BWRAP_LOOPBACK_ERROR.encode())
        return _RetryProcess(b"")

    monkeypatch.setattr(agent_runner.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(agent_runner, "_get_codex_sandbox_mode", lambda: "workspace-write")
    monkeypatch.setattr(agent_runner, "_extract_codex_output", lambda _: next(responses))

    response, returncode, stdout, stderr = await agent_runner._run_codex_exec(
        workdir=str(tmp_path),
        prompt="Read the file and report a timestamp.",
        model="gpt-5.4",
        bot_dir=str(tmp_path),
        vault_path=str(tmp_path),
        image_paths=[],
        resume_last=False,
        timeout=10,
    )

    assert sandboxes == ["workspace-write", "danger-full-access"]
    assert response == "2026-04-12T09:15:02Z"
    assert returncode == 0
    assert stdout == b""
    assert stderr == b""


@pytest.mark.asyncio
async def test_run_codex_exec_retries_on_transient_api_error(tmp_path, monkeypatch):
    class _RetryProcess:
        def __init__(self, stdout: bytes, returncode: int = 1):
            self.returncode = returncode
            self._stdout = stdout

        async def communicate(self):
            return self._stdout, b""

    sandboxes: list[str] = []
    responses = iter(
        [
            "Error: API Error: 500",
            "All good",
        ]
    )

    async def fake_create_subprocess_exec(*args, **kwargs):
        args_list = list(args)
        sandbox_index = args_list.index("-s")
        sandboxes.append(args_list[sandbox_index + 1])
        if len(sandboxes) == 1:
            return _RetryProcess(b"Internal server error", returncode=1)
        return _RetryProcess(b"", returncode=0)

    monkeypatch.setattr(agent_runner.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(agent_runner, "_get_codex_sandbox_mode", lambda: "danger-full-access")
    monkeypatch.setattr(agent_runner, "_extract_codex_output", lambda _: next(responses))

    response, returncode, stdout, stderr = await agent_runner._run_codex_exec(
        workdir=str(tmp_path),
        prompt="Do the job.",
        model="gpt-5.4",
        bot_dir=str(tmp_path),
        vault_path=str(tmp_path),
        image_paths=[],
        resume_last=False,
        timeout=10,
    )

    assert sandboxes == ["danger-full-access", "danger-full-access"]
    assert response == "All good"
    assert returncode == 0
    assert stdout == b""
    assert stderr == b""


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


def test_needs_calendar_context_does_not_false_positive_on_expected():
    assert (
        agent_runner._needs_calendar_context(
            ["Read"],
            "## Expected Behavior\n\n- Success: no output",
        )
        is False
    )


def test_needs_calendar_context_does_not_false_positive_on_medication_schedule():
    assert (
        agent_runner._needs_calendar_context(
            ["Read"],
            "Compare medication schedule changes between the vault and meds.json.",
        )
        is False
    )


def test_needs_calendar_context_for_schedule_requests_with_calendar_language():
    assert agent_runner._needs_calendar_context(
        ["Read"],
        "What is on my schedule for tomorrow morning?",
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
        "mcp__google_bot__create_event",
        "mcp__google_bot__list_labels",
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
        "mcp__google_bot__search_events",
        "mcp__google_bot__get_profile",
    ]


def test_normalize_allowed_tools_maps_atlas_names_for_codex():
    normalized = normalize_allowed_tools_for_provider(
        [
            "Read",
            "atlas__google_calendar__search_events",
            "atlas__google_calendar__probe_auth",
            "atlas__gmail__list_labels",
        ],
        "codex",
    )

    assert normalized == [
        "Read",
        "mcp__google_bot__search_events",
        "mcp__google_bot__get_profile",
        "mcp__google_bot__list_labels",
    ]


def test_normalize_allowed_tools_maps_probe_auth_for_claude():
    normalized = normalize_allowed_tools_for_provider(
        [
            "Read",
            "atlas__google_calendar__probe_auth",
        ],
        "claude",
    )

    assert normalized == [
        "Read",
        "mcp__google_bot__get_profile",
    ]


def test_inject_librarian_index_if_needed(tmp_path):
    vault_dir = tmp_path / "vault"
    index_path = vault_dir / "System" / "vault-index.md"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("# Vault Index\n\n- Recent note\n", encoding="utf-8")

    prompt = "Run the second-brain-librarian skill using the latest vault index."
    injected = agent_runner._inject_librarian_index_if_needed(prompt, str(vault_dir))

    assert "## Preloaded Vault Index" in injected
    assert "# Vault Index" in injected
    assert "Recent note" in injected


def test_build_prompt_with_attachments_adds_manifest(tmp_path):
    attachment = tmp_path / "report.pdf"
    attachment.write_text("hello", encoding="utf-8")

    prompt = agent_runner.build_prompt_with_attachments("Review this.", [str(attachment)])

    assert "## Attached Files" in prompt
    assert "pdf" in prompt
    assert str(attachment) in prompt


def test_resolve_skills_dir_prefers_atlas_namespace(tmp_path):
    atlas_skills = tmp_path / ".atlas" / "skills"
    claude_skills = tmp_path / ".claude" / "skills"
    atlas_skills.mkdir(parents=True)
    claude_skills.mkdir(parents=True)

    assert agent_runner.resolve_skills_dir(str(tmp_path)) == atlas_skills


@pytest.mark.asyncio
async def test_run_codex_exec_uses_reasoning_effort_override(tmp_path, monkeypatch):
    captured: dict[str, tuple] = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        return _FakeProcess()

    monkeypatch.setattr(agent_runner.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    await agent_runner._run_codex_exec(
        workdir=str(tmp_path),
        prompt="Reply with READY",
        model="gpt-5.4",
        bot_dir=str(tmp_path),
        vault_path=str(tmp_path),
        image_paths=[],
        resume_last=False,
        timeout=10,
        reasoning_effort="medium",
    )

    args = list(captured["args"])
    config_index = args.index("-c")
    assert args[config_index + 1] == 'model_reasoning_effort="medium"'


def test_build_codex_env_uses_managed_bot_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("ATLAS_CODEX_HOME", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)

    env = agent_runner._build_codex_env(str(tmp_path), str(tmp_path / "vault"))
    config_path = tmp_path / ".atlas-codex-home" / "config.toml"

    assert env["CODEX_HOME"] == str(tmp_path / ".atlas-codex-home")
    assert config_path.exists()
    config = config_path.read_text()
    assert '[plugins."github@openai-curated"]' in config
    assert '[mcp_servers."google_bot"]' in config
    assert '[mcp_servers."garmin"]' in config
    assert '[mcp_servers."oura"]' in config
    assert '[mcp_servers."whoop"]' in config
    assert '[mcp_servers."weather"]' in config


def test_build_codex_env_seeds_auth_from_default_home(tmp_path, monkeypatch):
    home_dir = tmp_path / "home"
    source_auth = home_dir / ".codex" / "auth.json"
    source_auth.parent.mkdir(parents=True)
    source_auth.write_text('{"token":"existing-login"}', encoding="utf-8")

    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.delenv("ATLAS_CODEX_HOME", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)

    env = agent_runner._build_codex_env(str(tmp_path), str(tmp_path / "vault"))
    target_auth = Path(env["CODEX_HOME"]) / "auth.json"

    assert target_auth.read_text(encoding="utf-8") == '{"token":"existing-login"}'


def test_build_codex_env_respects_configured_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
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


def test_build_codex_config_uses_managed_garmin_and_ignores_external_duplicate(
    tmp_path, monkeypatch
):
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))

    bot_dir = tmp_path / "bot"
    settings_path = bot_dir / ".claude" / "settings.local.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(
        json.dumps(
            {
                "permissions": {
                    "allow": [
                        "Read",
                        "mcp__garmin__*",
                    ]
                },
                "enabledMcpjsonServers": ["garmin", "google_bot"],
            }
        ),
        encoding="utf-8",
    )
    (home_dir / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "garmin": {
                        "command": "/usr/bin/uvx",
                        "args": ["--from", "git+https://example.invalid/garmin_mcp", "garmin-mcp"],
                        "env": {
                            "GARMIN_REGION": "us",
                        },
                    },
                    "google_bot": {
                        "command": "/usr/bin/ignored",
                        "args": ["google-bot-server"],
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    config = agent_runner._build_codex_config(str(bot_dir), str(tmp_path / "vault"))

    assert '[mcp_servers."garmin"]' in config
    assert 'command = "/usr/bin/uvx"' not in config
    assert "git+https://example.invalid/garmin_mcp" not in config
    assert "args = [" in config
    assert "mcp-servers/garmin/mcp_server.py" in config
    assert '[mcp_servers."garmin".env]' in config
    assert '"GARMIN_TOKEN_DIR"' in config
    assert '"GARMIN_REGION" = "us"' not in config
    assert '[mcp_servers."google_bot"]' in config
