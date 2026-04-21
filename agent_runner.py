"""Shared agent runner for Claude Code and Codex-backed ATLAS sessions."""

from __future__ import annotations

import asyncio
import copy
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp_tooling import is_google_calendar_tool_name, normalize_allowed_tools_for_provider

SUPPORTED_PROVIDERS = {"claude", "codex"}
CLAUDE_MODELS = {"haiku", "sonnet", "opus"}
CODEX_MODELS = {"gpt-5.4"}
USER_SELECTABLE_MODELS = {
    "claude": ("opus", "sonnet"),
    "codex": ("gpt-5.4",),
}

CODEX_SESSION_MARKER = ".atlas-codex-session-started"
CODEX_AGENTS_FILENAME = "AGENTS.md"
CODEX_CALENDAR_CONTEXT_FILENAME = "ATLAS-Calendar-Context.md"
CODEX_GARMIN_WORKOUT_HELP_FILENAME = "ATLAS-Garmin-Workout-Helper.md"
CODEX_WORKOUT_HELP_FILENAME = "ATLAS-Workout-Postwrite.md"
ATLAS_SESSION_METADATA_FILENAME = "ATLAS-Session.json"
CODEX_HOME_DIRNAME = ".atlas-codex-home"
CODEX_AUTH_FILENAME = "auth.json"
BWRAP_LOOPBACK_ERROR = "bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted"
CODEX_SANDBOX_MODES = {"read-only", "workspace-write", "danger-full-access"}
CODEX_CURATED_PLUGINS = ("github@openai-curated",)
CODEX_MANAGED_MCP_SERVER_NAMES = {"google_bot", "oura", "weather", "whoop"}
CODEX_EXTERNAL_MCP_SERVER_SKIP_NAMES = {
    *CODEX_MANAGED_MCP_SERVER_NAMES,
    "github",
    "gmail",
    "google-calendar",
}
MCP_SERVER_ALLOW_PATTERN = re.compile(r"^mcp__(?P<server>[A-Za-z0-9._-]+)__\*$")
CALENDAR_CONTEXT_KEYWORD_RE = re.compile(
    r"\b(calendar|meeting|meetings|event|events|scheduling)\b",
    re.IGNORECASE,
)
CALENDAR_SCHEDULE_PHRASE_RE = re.compile(
    r"\b(?:my|your|the|today'?s|tomorrow'?s|this week'?s|next week'?s)\s+schedule\b"
    r"|\bschedule\s+(?:for|on)\b",
    re.IGNORECASE,
)


def resolve_system_prompt_path(vault_path: str, configured_path: str | None = None) -> str:
    """Resolve the system prompt path without hard-coding a provider-specific filename."""
    if configured_path:
        return configured_path

    system_dir = Path(vault_path) / "System"
    for filename in ("ATLAS.md", "atlas.md", "claude.md"):
        candidate = system_dir / filename
        if candidate.exists():
            return str(candidate)

    return str(system_dir / "ATLAS.md")


def resolve_skills_dir(bot_dir: str) -> Path:
    """Resolve the repo-local ATLAS skills directory."""
    atlas_skills = Path(bot_dir) / ".atlas" / "skills"
    if atlas_skills.is_dir():
        return atlas_skills
    return Path(bot_dir) / ".claude" / "skills"


def get_agent_provider() -> str:
    """Return the configured agent provider, defaulting to Claude."""
    provider = os.getenv("ATLAS_AGENT_PROVIDER", "claude").strip().lower()
    return provider if provider in SUPPORTED_PROVIDERS else "claude"


def get_user_selectable_models(provider: str | None = None) -> tuple[str, ...]:
    """Return models that users may select for the active provider."""
    active_provider = provider or get_agent_provider()
    return USER_SELECTABLE_MODELS[active_provider]


def get_default_model(provider: str | None = None) -> str:
    """Return the default model for the active provider."""
    active_provider = provider or get_agent_provider()
    if active_provider == "codex":
        return os.getenv("ATLAS_CODEX_MODEL", "gpt-5.4")
    return os.getenv("ATLAS_CLAUDE_MODEL", "opus")


def resolve_model_for_provider(model: str, provider: str | None = None) -> str:
    """Map a stored model preference to a valid model for the active provider."""
    active_provider = provider or get_agent_provider()
    normalized = model.strip().lower()

    if active_provider == "codex":
        return normalized if normalized in CODEX_MODELS else get_default_model(active_provider)
    return normalized if normalized in CLAUDE_MODELS else get_default_model(active_provider)


def _atomic_write_text(path: str | Path, content: str) -> None:
    """Atomically replace a text file."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(temp_path, target)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def _atomic_write_json(path: str | Path, data: dict[str, Any]) -> None:
    """Atomically replace a JSON file."""
    _atomic_write_text(path, json.dumps(data, indent=2))


def _shell_command(program: str, *args: str) -> str:
    """Build a shell command with safely quoted arguments."""
    return " ".join(shlex.quote(part) for part in (program, *args))


def _read_text_if_exists(path: str | Path) -> str:
    """Read a UTF-8 text file if it exists."""
    target = Path(path)
    if not target.exists():
        return ""
    return target.read_text(encoding="utf-8")


def _read_json_object_if_exists(path: str | Path) -> dict[str, Any]:
    """Read a JSON object from disk when present."""
    target = Path(path)
    if not target.exists():
        return {}

    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

    return data if isinstance(data, dict) else {}


def _merge_settings(base: Any, overlay: Any) -> Any:
    """Deep-merge Codex/Claude settings while preserving unique list entries."""
    if isinstance(base, dict) and isinstance(overlay, dict):
        merged = {key: copy.deepcopy(value) for key, value in base.items()}
        for key, value in overlay.items():
            if key in merged:
                merged[key] = _merge_settings(merged[key], value)
            else:
                merged[key] = copy.deepcopy(value)
        return merged

    if isinstance(base, list) and isinstance(overlay, list):
        merged_list: list[Any] = []
        for item in [*base, *overlay]:
            copied_item = copy.deepcopy(item)
            if copied_item not in merged_list:
                merged_list.append(copied_item)
        return merged_list

    return copy.deepcopy(overlay)


def _run_shell_hook(command: str, *, env: dict[str, str]) -> str:
    """Run a shell hook synchronously and return trimmed stdout."""
    result = subprocess.run(
        command,
        shell=True,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.stdout.strip()


def _build_codex_agents_content(
    *,
    bot_dir: str,
    system_prompt_path: str,
    context_path: str,
    channel_dir: str,
) -> str:
    """Render a session-scoped AGENTS.md file for Codex-backed Discord sessions."""
    system_prompt = _read_text_if_exists(system_prompt_path).strip()
    persistent_context = _read_text_if_exists(context_path).strip()
    skills_dir = resolve_skills_dir(bot_dir)
    calendar_context_path = Path(channel_dir) / CODEX_CALENDAR_CONTEXT_FILENAME
    garmin_workout_help_path = Path(channel_dir) / CODEX_GARMIN_WORKOUT_HELP_FILENAME
    workout_help_path = Path(channel_dir) / CODEX_WORKOUT_HELP_FILENAME

    sections = [
        "# ATLAS Session Instructions",
        "",
        "These instructions define the ATLAS Discord session behavior for this channel.",
        "",
        "## System Prompt",
        "",
        system_prompt or "System prompt unavailable.",
        "",
        "## Persistent Context",
        "",
        persistent_context or "Persistent context unavailable.",
        "",
        "## Session Rules",
        "",
        "- Treat the system prompt and persistent context above as authoritative.",
        f"- ATLAS skill definitions live in `{skills_dir}`.",
        "- When a prompt tells you to run a named skill, read the matching file in that directory and follow it.",
        f"- Attachments from Discord are saved under `{Path(channel_dir) / 'attachments'}`.",
        f"- Before using Google Calendar create/update tools, read `{calendar_context_path}`.",
        (
            "- Treat `claudiamooney00@gmail.com` as ATLAS's default Google identity unless "
            "James explicitly directs otherwise."
        ),
        (
            "- Create bot-owned events on Claudia's calendar and include "
            "`jamesmoon2@gmail.com` unless James explicitly says not to. If Emma should be "
            "invited, use `lorzem15@gmail.com`."
        ),
        (
            "- Send outbound email only from `claudiamooney00@gmail.com` unless James "
            "explicitly overrides that instruction."
        ),
        (
            "- Before collecting Garmin data for workout logging, read "
            f"`{garmin_workout_help_path}`."
        ),
        f"- After writing a workout log under `Workout-Logs/YYYY-MM-DD.md`, read `{workout_help_path}` and complete the checklist.",
        "- Keep the behavior aligned with ATLAS operational conventions rather than Codex defaults.",
    ]
    return "\n".join(sections) + "\n"


def _build_codex_garmin_workout_help(bot_dir: str) -> str:
    """Create a stable helper note for Garmin-backed workout logging."""
    helper_path = Path(bot_dir) / "garmin_workout_fallback.py"
    return (
        "# Garmin Workout Data Helper\n\n"
        "When a workout logging flow needs Garmin data:\n\n"
        "1. Use direct `mcp__garmin__*` tools if they are available in the current session.\n"
        "2. If those tools are missing or the Garmin MCP server is unavailable, run:\n"
        f"   `python3 {helper_path} --date YYYY-MM-DD`\n"
        "   Add `--activity-id <id>` when you need a specific activity from that date.\n"
        "3. Never launch `garmin-mcp` manually or attempt a raw MCP stdio handshake from the terminal.\n\n"
        "The fallback returns normalized JSON including activity id, start time, duration, heart rate, calories, training effects, training load, body battery impact, readiness, HRV, sleep, and HR zones.\n"
    )


def _build_codex_workout_help(bot_dir: str) -> str:
    """Create a stable helper note for the Codex workout post-write flow."""
    hook_path = Path(bot_dir) / "hooks" / "workout_oura_data.sh"
    return (
        "# Workout Post-Write Checklist\n\n"
        "After writing a workout log file that matches `Workout-Logs/YYYY-MM-DD.md`:\n\n"
        f"1. Run `{hook_path} <absolute-workout-log-path>`.\n"
        "2. Read the checklist output.\n"
        "3. Complete the Oura and Training-State follow-up steps before finishing.\n"
    )


def _load_existing_session_metadata(path: Path) -> dict[str, Any]:
    """Read ATLAS session metadata if it already exists."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _build_session_metadata(
    *,
    channel_dir: str,
    bot_dir: str,
    system_prompt_path: str,
    context_path: str,
) -> dict[str, Any]:
    """Render provider-neutral session metadata owned by ATLAS."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "channel_dir": str(Path(channel_dir).resolve()),
        "active_provider": get_agent_provider(),
        "skills_dir": str(resolve_skills_dir(bot_dir).resolve()),
        "system_prompt_path": str(Path(system_prompt_path).resolve()),
        "context_path": str(Path(context_path).resolve()),
        "updated_at": now,
    }


def prepare_session_dir(
    channel_dir: str,
    *,
    bot_dir: str,
    system_prompt_path: str,
    context_path: str,
    channel_settings: dict[str, Any],
    channel_permissions: dict[str, Any],
) -> None:
    """Prepare a channel session directory for both Claude and Codex."""
    session_path = Path(channel_dir)
    claude_dir = session_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    project_settings_path = Path(bot_dir) / ".claude" / "settings.json"
    settings_path = claude_dir / "settings.json"
    merged_settings = _merge_settings(
        _read_json_object_if_exists(project_settings_path),
        channel_settings,
    )
    _atomic_write_json(settings_path, merged_settings)

    project_local_settings_path = Path(bot_dir) / ".claude" / "settings.local.json"
    local_settings_path = claude_dir / "settings.local.json"
    merged_local_settings = _merge_settings(
        _read_json_object_if_exists(project_local_settings_path),
        channel_permissions,
    )
    _atomic_write_json(local_settings_path, merged_local_settings)

    skills_symlink = claude_dir / "skills"
    skills_target = resolve_skills_dir(bot_dir)
    if skills_target.is_dir():
        desired_target = os.path.realpath(skills_target)
        if skills_symlink.is_symlink():
            current_target = os.path.realpath(skills_symlink)
            if current_target != desired_target:
                skills_symlink.unlink()
                skills_symlink.symlink_to(skills_target)
        elif not skills_symlink.exists():
            skills_symlink.symlink_to(skills_target)

    hook_env = os.environ.copy()
    hook_env.setdefault("BOT_DIR", bot_dir)
    calendar_context_path = session_path / CODEX_CALENDAR_CONTEXT_FILENAME
    calendar_hook = Path(bot_dir) / "hooks" / "calendar_context.sh"
    if calendar_hook.exists():
        calendar_output = _run_shell_hook(str(calendar_hook), env=hook_env)
        if calendar_output:
            _atomic_write_text(calendar_context_path, calendar_output + "\n")

    garmin_workout_help_path = session_path / CODEX_GARMIN_WORKOUT_HELP_FILENAME
    _atomic_write_text(garmin_workout_help_path, _build_codex_garmin_workout_help(bot_dir))

    workout_help_path = session_path / CODEX_WORKOUT_HELP_FILENAME
    _atomic_write_text(workout_help_path, _build_codex_workout_help(bot_dir))

    codex_agents_path = session_path / CODEX_AGENTS_FILENAME
    _atomic_write_text(
        codex_agents_path,
        _build_codex_agents_content(
            bot_dir=bot_dir,
            system_prompt_path=system_prompt_path,
            context_path=context_path,
            channel_dir=channel_dir,
        ),
    )

    metadata_path = session_path / ATLAS_SESSION_METADATA_FILENAME
    metadata = _load_existing_session_metadata(metadata_path)
    metadata.update(
        _build_session_metadata(
            channel_dir=channel_dir,
            bot_dir=bot_dir,
            system_prompt_path=system_prompt_path,
            context_path=context_path,
        )
    )
    metadata.setdefault("created_at", metadata["updated_at"])
    _atomic_write_json(metadata_path, metadata)


def _format_process_error(
    stdout: bytes,
    stderr: bytes,
    *,
    prefix: str = "Error",
    fallback: str = "Process failed with no output.",
) -> str:
    """Build a user-facing error message from subprocess output."""
    parts = [stdout.decode().strip(), stderr.decode().strip()]
    message = "\n\n".join(part for part in parts if part)
    return f"{prefix}: {message}" if message else f"{prefix}: {fallback}"


async def _kill_process(process: asyncio.subprocess.Process) -> None:
    """Terminate and reap a subprocess."""
    process.kill()
    await process.communicate()


def _codex_command_prefix(
    *,
    workdir: str,
    model: str,
    bot_dir: str,
    vault_path: str,
    sandbox_mode: str | None = None,
    reasoning_effort: str | None = None,
) -> list[str]:
    """Build the shared Codex CLI prefix."""
    resolved_reasoning_effort = reasoning_effort or os.getenv(
        "ATLAS_CODEX_REASONING_EFFORT", "xhigh"
    )
    resolved_sandbox_mode = sandbox_mode or _get_codex_sandbox_mode()
    prefix = [
        "codex",
        "exec",
        "-C",
        workdir,
        "-m",
        model,
        "-s",
        resolved_sandbox_mode,
        "--skip-git-repo-check",
        "--add-dir",
        bot_dir,
        "--add-dir",
        vault_path,
        "-c",
        f'model_reasoning_effort="{resolved_reasoning_effort}"',
        "-c",
        'approval_policy="never"',
    ]
    return prefix


def _get_codex_sandbox_mode() -> str:
    """Return the configured Codex sandbox mode for ATLAS."""
    sandbox_mode = os.getenv("ATLAS_CODEX_SANDBOX", "workspace-write").strip().lower()
    if sandbox_mode in CODEX_SANDBOX_MODES:
        return sandbox_mode
    return "workspace-write"


def _get_codex_home(bot_dir: str) -> Path:
    """Resolve the Codex home directory used by the ATLAS harness."""
    configured_home = os.getenv("ATLAS_CODEX_HOME")
    if configured_home:
        return Path(configured_home).expanduser()
    return Path(bot_dir) / CODEX_HOME_DIRNAME


def _sync_codex_auth_into_managed_home(codex_home: Path) -> None:
    """Seed the managed Codex profile with the operator's existing login."""
    source_auth = Path.home() / ".codex" / CODEX_AUTH_FILENAME
    target_auth = codex_home / CODEX_AUTH_FILENAME

    try:
        if target_auth.resolve() == source_auth.resolve():
            return
    except OSError:
        pass

    if not source_auth.exists():
        return

    source_content = source_auth.read_text(encoding="utf-8")
    if target_auth.exists() and target_auth.read_text(encoding="utf-8") == source_content:
        return

    _atomic_write_text(target_auth, source_content)
    target_auth.chmod(0o600)


def _extract_enabled_mcpjson_servers(project_settings: dict[str, Any]) -> set[str]:
    """Return MCP servers explicitly enabled in the repo-local Claude settings."""
    enabled = project_settings.get("enabledMcpjsonServers")
    if not isinstance(enabled, list):
        return set()
    return {str(name).strip() for name in enabled if str(name).strip()}


def _extract_disabled_mcpjson_servers(project_settings: dict[str, Any]) -> set[str]:
    """Return MCP servers explicitly disabled in the repo-local Claude settings."""
    disabled = project_settings.get("disabledMcpjsonServers")
    if not isinstance(disabled, list):
        return set()
    return {str(name).strip() for name in disabled if str(name).strip()}


def _extract_allowed_mcp_server_names(project_settings: dict[str, Any]) -> set[str]:
    """Infer externally allowed MCP server names from `mcp__<server>__*` permissions."""
    permissions = project_settings.get("permissions")
    if not isinstance(permissions, dict):
        return set()

    allow_patterns = permissions.get("allow")
    if not isinstance(allow_patterns, list):
        return set()

    allowed_servers: set[str] = set()
    for pattern in allow_patterns:
        if not isinstance(pattern, str):
            continue
        match = MCP_SERVER_ALLOW_PATTERN.match(pattern.strip())
        if match:
            allowed_servers.add(match.group("server"))

    return allowed_servers


def _resolve_external_mcp_server_names(bot_dir: str) -> set[str]:
    """Resolve which `~/.mcp.json` servers should be inherited into managed Codex."""
    project_settings = _read_json_object_if_exists(
        Path(bot_dir) / ".claude" / "settings.local.json"
    )
    if not project_settings:
        return set()

    enabled_servers = _extract_enabled_mcpjson_servers(project_settings)
    allowed_servers = _extract_allowed_mcp_server_names(project_settings)
    disabled_servers = _extract_disabled_mcpjson_servers(project_settings)

    selected_servers = enabled_servers or allowed_servers
    if enabled_servers and allowed_servers:
        selected_servers = enabled_servers & allowed_servers

    return {
        name
        for name in selected_servers
        if name not in disabled_servers and name not in CODEX_EXTERNAL_MCP_SERVER_SKIP_NAMES
    }


def _normalize_external_mcp_server_config(server_config: Any) -> dict[str, Any]:
    """Translate an `~/.mcp.json` server definition into Codex config fields."""
    if not isinstance(server_config, dict):
        return {}

    normalized: dict[str, Any] = {}
    scalar_fields = (
        "command",
        "cwd",
        "url",
        "enabled",
        "required",
        "oauth_resource",
        "startup_timeout_sec",
        "tool_timeout_sec",
    )
    sequence_fields = (
        "args",
        "enabled_tools",
        "disabled_tools",
    )
    mapping_fields = {
        "env": "env",
        "http_headers": "http_headers",
        "env_http_headers": "env_http_headers",
    }
    aliases = {
        "startupTimeoutSec": "startup_timeout_sec",
        "startupTimeoutSeconds": "startup_timeout_sec",
        "startup_timeout_seconds": "startup_timeout_sec",
        "toolTimeoutSec": "tool_timeout_sec",
        "toolTimeoutSeconds": "tool_timeout_sec",
        "tool_timeout_seconds": "tool_timeout_sec",
        "oauthResource": "oauth_resource",
        "enabledTools": "enabled_tools",
        "disabledTools": "disabled_tools",
        "httpHeaders": "http_headers",
        "envHttpHeaders": "env_http_headers",
    }

    expanded_config = {
        aliases.get(key, key): value for key, value in server_config.items() if value is not None
    }

    for field in scalar_fields:
        value = expanded_config.get(field)
        if isinstance(value, (str, bool, int, float)):
            normalized[field] = value

    for field in sequence_fields:
        value = expanded_config.get(field)
        if isinstance(value, list):
            normalized[field] = value

    for source_field, target_field in mapping_fields.items():
        value = expanded_config.get(source_field)
        if isinstance(value, dict):
            normalized[target_field] = value

    return normalized


def _load_external_mcp_servers(bot_dir: str) -> dict[str, dict[str, Any]]:
    """Load repo-approved external MCP servers from `~/.mcp.json`."""
    selected_servers = _resolve_external_mcp_server_names(bot_dir)
    if not selected_servers:
        return {}

    mcp_json_path = Path.home() / ".mcp.json"
    if not mcp_json_path.exists():
        return {}

    mcp_config = _read_json_object_if_exists(mcp_json_path)
    server_entries = mcp_config.get("mcpServers") or mcp_config.get("mcp_servers")
    if not isinstance(server_entries, dict):
        return {}

    normalized_servers: dict[str, dict[str, Any]] = {}
    for server_name, server_config in server_entries.items():
        if server_name not in selected_servers:
            continue
        if server_name in CODEX_MANAGED_MCP_SERVER_NAMES:
            continue
        normalized_config = _normalize_external_mcp_server_config(server_config)
        if normalized_config:
            normalized_servers[server_name] = normalized_config

    return normalized_servers


def _render_toml_value(value: Any) -> str:
    """Render a primitive or array value as TOML."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return json.dumps(value)


def _append_codex_mcp_server_block(
    lines: list[str], server_name: str, server_config: dict[str, Any]
) -> None:
    """Append a single `[mcp_servers.*]` block to the managed Codex config."""
    lines.extend(
        [
            f"[mcp_servers.{json.dumps(server_name)}]",
        ]
    )

    for field in (
        "command",
        "args",
        "cwd",
        "url",
        "enabled",
        "required",
        "oauth_resource",
        "startup_timeout_sec",
        "tool_timeout_sec",
        "enabled_tools",
        "disabled_tools",
    ):
        value = server_config.get(field)
        if value is not None:
            lines.append(f"{field} = {_render_toml_value(value)}")

    for table_name in ("env", "http_headers", "env_http_headers"):
        table_values = server_config.get(table_name)
        if not isinstance(table_values, dict) or not table_values:
            continue
        lines.extend(
            [
                "",
                f"[mcp_servers.{json.dumps(server_name)}.{table_name}]",
            ]
        )
        for key in sorted(table_values):
            value = table_values[key]
            if isinstance(value, (str, bool, int, float)):
                lines.append(f"{json.dumps(key)} = {_render_toml_value(value)}")

    lines.append("")


def _build_codex_config(bot_dir: str, vault_path: str) -> str:
    """Render the managed Codex profile for ATLAS."""
    bot_path = Path(bot_dir).resolve()
    vault_root = Path(vault_path).resolve()
    reasoning_effort = os.getenv("ATLAS_CODEX_REASONING_EFFORT", "xhigh")
    model = os.getenv("ATLAS_CODEX_MODEL", "gpt-5.4")
    oura_python = os.getenv(
        "OURA_PYTHON",
        str(bot_path / "mcp-servers" / "oura" / "venv" / "bin" / "python3"),
    )
    oura_script = os.getenv(
        "OURA_SCRIPT",
        str(bot_path / "mcp-servers" / "oura" / "mcp_server.py"),
    )
    default_bot_python = bot_path / "venv" / "bin" / "python3"
    google_bot_python = os.getenv(
        "GOOGLE_BOT_PYTHON",
        str(default_bot_python if default_bot_python.exists() else Path(sys.executable)),
    )
    google_bot_script = os.getenv(
        "GOOGLE_BOT_SCRIPT",
        str(bot_path / "mcp-servers" / "google_bot" / "mcp_server.py"),
    )
    default_whoop_python = default_bot_python
    whoop_python = os.getenv(
        "WHOOP_PYTHON",
        str(default_whoop_python if default_whoop_python.exists() else Path(sys.executable)),
    )
    whoop_script = os.getenv(
        "WHOOP_SCRIPT",
        str(bot_path / "mcp-servers" / "whoop" / "mcp_server.py"),
    )
    lines = [
        f"model = {json.dumps(model)}",
        f"model_reasoning_effort = {json.dumps(reasoning_effort)}",
        'personality = "friendly"',
        "",
        f"[projects.{json.dumps(str(bot_path))}]",
        'trust_level = "trusted"',
        "",
        f"[projects.{json.dumps(str(vault_root))}]",
        'trust_level = "trusted"',
        "",
    ]

    for plugin_name in CODEX_CURATED_PLUGINS:
        lines.extend(
            [
                f"[plugins.{json.dumps(plugin_name)}]",
                "enabled = true",
                "",
            ]
        )

    _append_codex_mcp_server_block(
        lines,
        "google_bot",
        {
            "command": google_bot_python,
            "args": [google_bot_script],
            "env": {
                "GOOGLE_BOT_CLIENT_SECRET_FILE": str(
                    bot_path / "mcp-servers" / "credentials" / "google-bot-oauth-client.json"
                ),
                "GOOGLE_BOT_TOKEN_FILE": str(
                    bot_path / "mcp-servers" / "credentials" / "google-bot-tokens.json"
                ),
            },
        },
    )
    _append_codex_mcp_server_block(
        lines,
        "oura",
        {
            "command": oura_python,
            "args": [oura_script],
        },
    )
    _append_codex_mcp_server_block(
        lines,
        "whoop",
        {
            "command": whoop_python,
            "args": [whoop_script],
            "env": {
                "WHOOP_OAUTH_CREDENTIALS": str(
                    bot_path / "mcp-servers" / "credentials" / "whoop-oauth.keys.json"
                ),
                "WHOOP_TOKEN_FILE": str(
                    bot_path / "mcp-servers" / "credentials" / "whoop-tokens.json"
                ),
            },
        },
    )
    _append_codex_mcp_server_block(
        lines,
        "weather",
        {
            "command": "npx",
            "args": ["-y", "@dangahagan/weather-mcp@latest"],
        },
    )
    for server_name, server_config in sorted(_load_external_mcp_servers(bot_dir).items()):
        _append_codex_mcp_server_block(lines, server_name, server_config)

    return "\n".join(lines)


def _ensure_codex_home(bot_dir: str, vault_path: str) -> Path:
    """Create or refresh the managed Codex profile for ATLAS."""
    configured_home = os.getenv("ATLAS_CODEX_HOME")
    codex_home = _get_codex_home(bot_dir)
    codex_home.mkdir(parents=True, exist_ok=True)
    if not configured_home:
        _sync_codex_auth_into_managed_home(codex_home)
    config_path = codex_home / "config.toml"
    _atomic_write_text(config_path, _build_codex_config(bot_dir, vault_path) + "\n")
    return codex_home


def _build_codex_env(bot_dir: str, vault_path: str) -> dict[str, str]:
    """Build the environment for Codex subprocesses."""
    env = os.environ.copy()
    env["CODEX_HOME"] = str(_ensure_codex_home(bot_dir, vault_path))
    return env


def _extract_codex_output(output_file: str) -> str:
    """Read the last Codex assistant message from an output file."""
    path = Path(output_file)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _should_retry_codex_with_dangerous_sandbox(
    *, sandbox_mode: str, stdout: bytes, stderr: bytes
) -> bool:
    """Detect the known bubblewrap failure and retry without Codex sandboxing."""
    if sandbox_mode == "danger-full-access":
        return False

    combined_output = stdout.decode(errors="ignore") + stderr.decode(errors="ignore")
    return BWRAP_LOOPBACK_ERROR in combined_output


def _should_retry_codex_for_transient_api_error(
    *, response: str, stdout: bytes, stderr: bytes
) -> bool:
    """Detect transient Codex/OpenAI upstream failures worth retrying once."""
    combined_output = "\n".join(
        part
        for part in (response, stdout.decode(errors="ignore"), stderr.decode(errors="ignore"))
        if part
    )
    lowered_output = combined_output.lower()
    retry_markers = (
        "api error: 500",
        "internal server error",
        "currently experiencing high demand",
        "http error: 500",
        "unexpected status 500",
    )
    return any(marker in lowered_output for marker in retry_markers)


def _skill_path(bot_dir: str, skill_name: str) -> Path:
    """Resolve a repo-local ATLAS skill path."""
    return resolve_skills_dir(bot_dir) / f"{skill_name}.md"


def build_prompt_with_attachments(prompt: str, file_paths: list[str]) -> str:
    """Build a provider-neutral prompt that includes an attachment manifest."""
    if not file_paths:
        return prompt

    image_suffixes = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    lines = [
        prompt or "Please analyze the attached file(s).",
        "",
        "## Attached Files",
        "",
        "These local files are attached to this request. Use the Read tool to inspect them as needed.",
        "",
    ]

    for path in file_paths:
        suffix = Path(path).suffix.lower()
        if suffix in image_suffixes:
            kind = "image"
        elif suffix == ".pdf":
            kind = "pdf"
        else:
            kind = "file"
        lines.append(f"- {kind}: `{path}`")

    return "\n".join(lines)


def _expand_skill_prompt_if_needed(prompt: str, bot_dir: str) -> str:
    """Inline a skill definition for Codex when the prompt explicitly names one."""
    match = re.search(r"\brun the ([a-z0-9-]+) skill\b", prompt, re.IGNORECASE)
    if not match:
        return prompt

    skill_name = match.group(1).lower()
    skill_path = _skill_path(bot_dir, skill_name)
    if not skill_path.exists():
        return prompt

    skill_contents = skill_path.read_text(encoding="utf-8").strip()
    return (
        f"{prompt}\n\n"
        f"## ATLAS Skill Definition: {skill_name}\n\n"
        f"Read and follow this skill definition while completing the task:\n\n"
        f"{skill_contents}\n"
    )


def _inject_librarian_index_if_needed(prompt: str, vault_path: str) -> str:
    """Inline the compact vault index summary for librarian-oriented Codex runs."""
    lowered_prompt = prompt.lower()
    if all(
        marker not in lowered_prompt
        for marker in ("second-brain-librarian", "second-brain librarian", "second brain librarian")
    ):
        return prompt

    index_path = Path(vault_path) / "System" / "vault-index.md"
    if not index_path.exists():
        return prompt

    index_text = index_path.read_text(encoding="utf-8").strip()
    if not index_text:
        return prompt

    return (
        f"{prompt}\n\n"
        "## Preloaded Vault Index\n\n"
        "Use this preloaded vault index overview as the primary source for the digest. "
        "Only read additional notes if the index is genuinely insufficient.\n\n"
        f"{index_text}\n"
    )


def _build_allowed_tools_note(allowed_tools: list[str]) -> str:
    """Render a soft tool-usage constraint note for Codex."""
    if not allowed_tools:
        return ""
    joined_tools = ", ".join(allowed_tools)
    return (
        "## Allowed Tools\n\n"
        f"Prefer to stay within this task's allowed capabilities: {joined_tools}.\n"
        "If the task appears to require anything outside that set, say so before improvising.\n\n"
    )


def _build_scheduled_job_note() -> str:
    """Render execution guidance for unattended scheduled jobs."""
    return (
        "## Execution Context\n\n"
        "This is an unattended scheduled job.\n"
        "Do not ask the user follow-up questions or wait for input.\n"
        "Use the prompt, referenced files, and available tools to make the best autonomous effort.\n"
        "If something is missing or broken, state the blocker clearly in the output.\n\n"
    )


def _needs_calendar_context(allowed_tools: list[str], prompt: str) -> bool:
    """Determine whether a Codex prompt should include the calendar date reference."""
    if any(is_google_calendar_tool_name(tool) for tool in allowed_tools):
        return True
    if CALENDAR_CONTEXT_KEYWORD_RE.search(prompt):
        return True
    return CALENDAR_SCHEDULE_PHRASE_RE.search(prompt) is not None


async def _capture_shell(command: str, *, env: dict[str, str], cwd: str | None = None) -> str:
    """Run a shell command asynchronously and return stdout."""
    process = await asyncio.create_subprocess_shell(
        command,
        cwd=cwd,
        env=env,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _stderr = await process.communicate()
    return stdout.decode().strip()


async def _append_calendar_context_if_needed(
    *,
    prompt: str,
    allowed_tools: list[str],
    bot_dir: str,
    cwd: str,
) -> str:
    """Append the ATLAS-owned calendar date reference when the task implies calendar work."""
    if not _needs_calendar_context(allowed_tools, prompt):
        return prompt

    calendar_hook = Path(bot_dir) / "hooks" / "calendar_context.sh"
    if not calendar_hook.exists():
        return prompt

    calendar_context = await _capture_shell(
        str(calendar_hook),
        env=os.environ.copy(),
        cwd=cwd,
    )
    if not calendar_context:
        return prompt
    return f"{prompt}\n\n{calendar_context}\n"


async def _prepare_atlas_prompt(
    *,
    prompt: str,
    bot_dir: str,
    vault_path: str,
    cwd: str,
    attachment_paths: list[str] | None = None,
    allowed_tools: list[str] | None = None,
    include_scheduled_job_note: bool = False,
    include_allowed_tools_note: bool = False,
    include_calendar_context: bool = False,
) -> str:
    """Apply ATLAS-owned prompt augmentation consistently across providers."""
    attachment_paths = attachment_paths or []
    allowed_tools = allowed_tools or []

    effective_prompt = build_prompt_with_attachments(prompt, attachment_paths)
    if include_scheduled_job_note:
        effective_prompt = _build_scheduled_job_note() + effective_prompt
    if include_allowed_tools_note and allowed_tools:
        effective_prompt = _build_allowed_tools_note(allowed_tools) + effective_prompt

    effective_prompt = _expand_skill_prompt_if_needed(effective_prompt, bot_dir)
    effective_prompt = _inject_librarian_index_if_needed(effective_prompt, vault_path)

    if include_calendar_context:
        effective_prompt = await _append_calendar_context_if_needed(
            prompt=effective_prompt,
            allowed_tools=allowed_tools,
            bot_dir=bot_dir,
            cwd=cwd,
        )

    return effective_prompt


def _claude_session_dir_for_channel_dir(channel_dir: str) -> Path:
    """Return Claude's external per-workdir session storage path."""
    abs_channel_dir = str(Path(channel_dir).resolve())
    claude_project_name = abs_channel_dir.replace("/", "-")
    return Path.home() / ".claude" / "projects" / claude_project_name


def clear_provider_private_session_state(channel_dir: str) -> bool:
    """Clear external provider-managed session state for a channel if present."""
    cleared = False

    claude_session_dir = _claude_session_dir_for_channel_dir(channel_dir)
    if claude_session_dir.exists():
        import shutil

        shutil.rmtree(claude_session_dir)
        cleared = True

    return cleared


def _should_skip_codex_sessionstart_command(
    command: str,
    *,
    system_prompt_path: str,
    context_path: str,
) -> bool:
    """Skip commands already represented in the generated AGENTS.md."""
    try:
        parts = shlex.split(command)
    except ValueError:
        return False

    if parts[:2] == ["cat", system_prompt_path]:
        return True
    if parts[:2] == ["cat", context_path]:
        return True
    return False


async def _build_codex_session_start_prelude(
    *,
    channel_dir: str,
    bot_dir: str,
    vault_path: str,
    system_prompt_path: str,
    context_path: str,
    channel_settings: dict[str, Any],
) -> str:
    """Collect the current SessionStart hook outputs for the first Codex turn."""
    hook_env = os.environ.copy()
    hook_env.setdefault("BOT_DIR", bot_dir)
    hook_env.setdefault("VAULT_PATH", vault_path)
    prelude_parts: list[str] = []
    session_start_entries = channel_settings.get("hooks", {}).get("SessionStart", [])
    for entry in session_start_entries:
        for hook in entry.get("hooks", []):
            command = hook.get("command")
            if not command or _should_skip_codex_sessionstart_command(
                command,
                system_prompt_path=system_prompt_path,
                context_path=context_path,
            ):
                continue
            output = await _capture_shell(command, env=hook_env, cwd=channel_dir)
            if output:
                prelude_parts.append(output)

    return "\n\n".join(part.strip() for part in prelude_parts if part.strip())


def _split_image_attachments(file_paths: list[str]) -> list[str]:
    """Return image attachments that Codex can accept as native image inputs."""
    images = []
    for path in file_paths:
        if Path(path).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
            images.append(path)
    return images


async def _run_codex_exec(
    *,
    workdir: str,
    prompt: str,
    model: str,
    bot_dir: str,
    vault_path: str,
    image_paths: list[str],
    resume_last: bool,
    timeout: int,
    reasoning_effort: str | None = None,
) -> tuple[str, int, bytes, bytes]:
    """Execute Codex and return (response_text, returncode, stdout, stderr)."""
    fd, output_file = tempfile.mkstemp(prefix="atlas-codex-", suffix=".txt")
    os.close(fd)

    async def _invoke(*, sandbox_mode: str, timeout_budget: float) -> tuple[str, int, bytes, bytes]:
        prefix = _codex_command_prefix(
            workdir=workdir,
            model=model,
            bot_dir=bot_dir,
            vault_path=vault_path,
            sandbox_mode=sandbox_mode,
            reasoning_effort=reasoning_effort,
        )

        if resume_last:
            command = prefix + ["resume", "--last", "--json", "-o", output_file]
        else:
            command = prefix + ["--json", "-o", output_file]

        for image_path in image_paths:
            command.extend(["-i", image_path])

        command.append("--")
        command.append(prompt)

        process: asyncio.subprocess.Process | None = None
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=_build_codex_env(bot_dir, vault_path),
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_budget)
            response = _extract_codex_output(output_file)
            return response, process.returncode, stdout, stderr
        except asyncio.TimeoutError:
            if process is not None:
                await _kill_process(process)
            raise

    start_time = time.monotonic()
    initial_sandbox_mode = _get_codex_sandbox_mode()
    try:
        active_sandbox_mode = initial_sandbox_mode
        response, returncode, stdout, stderr = await _invoke(
            sandbox_mode=active_sandbox_mode,
            timeout_budget=timeout,
        )
        if _should_retry_codex_with_dangerous_sandbox(
            sandbox_mode=active_sandbox_mode,
            stdout=stdout,
            stderr=stderr,
        ):
            remaining_timeout = timeout - (time.monotonic() - start_time)
            if remaining_timeout > 0:
                active_sandbox_mode = "danger-full-access"
                response, returncode, stdout, stderr = await _invoke(
                    sandbox_mode=active_sandbox_mode,
                    timeout_budget=remaining_timeout,
                )
        if _should_retry_codex_for_transient_api_error(
            response=response,
            stdout=stdout,
            stderr=stderr,
        ):
            remaining_timeout = timeout - (time.monotonic() - start_time)
            if remaining_timeout > 0:
                response, returncode, stdout, stderr = await _invoke(
                    sandbox_mode=active_sandbox_mode,
                    timeout_budget=remaining_timeout,
                )
        return response, returncode, stdout, stderr
    except asyncio.TimeoutError:
        raise
    finally:
        try:
            os.unlink(output_file)
        except OSError:
            pass


async def run_channel_message(
    *,
    channel_id: int,
    prompt: str,
    attachment_paths: list[str],
    channel_dir: str,
    model: str,
    bot_dir: str,
    vault_path: str,
    system_prompt_path: str,
    context_path: str,
    channel_settings: dict[str, Any],
) -> str:
    """Run a Discord channel message through the active provider."""
    provider = get_agent_provider()
    resolved_model = resolve_model_for_provider(model, provider)
    effective_prompt = await _prepare_atlas_prompt(
        prompt=prompt,
        bot_dir=bot_dir,
        vault_path=vault_path,
        cwd=channel_dir,
        attachment_paths=attachment_paths,
    )

    if provider == "codex":
        return await _run_codex_channel_message(
            prompt=effective_prompt,
            attachment_paths=attachment_paths,
            channel_dir=channel_dir,
            model=resolved_model,
            bot_dir=bot_dir,
            vault_path=vault_path,
            system_prompt_path=system_prompt_path,
            context_path=context_path,
            channel_settings=channel_settings,
        )

    return await _run_claude_channel_message(
        prompt=effective_prompt,
        channel_dir=channel_dir,
        model=resolved_model,
    )


async def _run_claude_channel_message(*, prompt: str, channel_dir: str, model: str) -> str:
    """Preserve the existing Claude channel-session behavior."""
    process: asyncio.subprocess.Process | None = None
    try:
        process = await asyncio.create_subprocess_exec(
            "claude",
            "--model",
            model,
            "--continue",
            "--output-format",
            "json",
            "--allowedTools",
            "Read,Write,Edit,Glob,Grep,Bash",
            "-p",
            prompt,
            cwd=channel_dir,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={k: v for k, v in os.environ.items() if k != "CLAUDECODE"},
        )

        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=600)
        if process.returncode != 0:
            return _format_process_error(
                stdout,
                stderr,
                fallback=f"Claude exited with status {process.returncode}.",
            )

        try:
            data = json.loads(stdout.decode())
            response = data.get("result", "")
            if not response and stderr:
                response = f"Error: {stderr.decode().strip()}"
            return response if response else "No response from Claude."
        except json.JSONDecodeError:
            response = stdout.decode().strip()
            if not response and stderr:
                response = f"Error: {stderr.decode().strip()}"
            return response if response else "No response from Claude."
    except asyncio.TimeoutError:
        if process is not None:
            await _kill_process(process)
        return "Request timed out after 10 minutes."
    except Exception as e:
        return f"Error: {str(e)}"


async def _run_codex_channel_message(
    *,
    prompt: str,
    attachment_paths: list[str],
    channel_dir: str,
    model: str,
    bot_dir: str,
    vault_path: str,
    system_prompt_path: str,
    context_path: str,
    channel_settings: dict[str, Any],
) -> str:
    """Run a Discord channel message through Codex with session continuity."""
    marker_path = Path(channel_dir) / CODEX_SESSION_MARKER
    is_fresh_session = not marker_path.exists()

    effective_prompt = prompt
    if is_fresh_session:
        session_prelude = await _build_codex_session_start_prelude(
            channel_dir=channel_dir,
            bot_dir=bot_dir,
            vault_path=vault_path,
            system_prompt_path=system_prompt_path,
            context_path=context_path,
            channel_settings=channel_settings,
        )
        if session_prelude:
            effective_prompt = f"{session_prelude}\n\n---\n\nUser request:\n{effective_prompt}"

    image_paths = _split_image_attachments(attachment_paths)
    try:
        response, returncode, stdout, stderr = await _run_codex_exec(
            workdir=channel_dir,
            prompt=effective_prompt,
            model=model,
            bot_dir=bot_dir,
            vault_path=vault_path,
            image_paths=image_paths,
            resume_last=not is_fresh_session,
            timeout=600,
            reasoning_effort=None,
        )
    except asyncio.TimeoutError:
        return "Request timed out after 10 minutes."
    except Exception as e:
        return f"Error: {str(e)}"

    if returncode != 0:
        return _format_process_error(
            stdout,
            stderr,
            prefix="Error",
            fallback=f"Codex exited with status {returncode}.",
        )

    if response:
        marker_path.touch(exist_ok=True)
        return response
    return "No response from Codex."


async def run_job_prompt(
    *,
    prompt: str,
    model: str,
    allowed_tools: list[str],
    timeout: int,
    bot_dir: str,
    vault_path: str,
    reasoning_effort: str | None = None,
) -> tuple[str, bool]:
    """Run a one-shot job prompt through the active provider."""
    provider = get_agent_provider()
    resolved_model = resolve_model_for_provider(model, provider)
    provider_allowed_tools = normalize_allowed_tools_for_provider(allowed_tools, provider)
    effective_prompt = await _prepare_atlas_prompt(
        prompt=prompt,
        bot_dir=bot_dir,
        vault_path=vault_path,
        cwd=bot_dir,
        attachment_paths=[],
        allowed_tools=provider_allowed_tools,
        include_scheduled_job_note=True,
        include_allowed_tools_note=True,
        include_calendar_context=True,
    )

    if provider == "codex":
        try:
            response, returncode, stdout, stderr = await _run_codex_exec(
                workdir=bot_dir,
                prompt=effective_prompt,
                model=resolved_model,
                bot_dir=bot_dir,
                vault_path=vault_path,
                image_paths=[],
                resume_last=False,
                timeout=timeout,
                reasoning_effort=reasoning_effort,
            )
        except asyncio.TimeoutError:
            return f"Job timed out after {timeout} seconds.", False
        except Exception as e:
            return f"Error: {str(e)}", False

        if returncode != 0:
            return (
                _format_process_error(
                    stdout,
                    stderr,
                    fallback=f"Codex exited with status {returncode}.",
                ),
                False,
            )

        if response:
            return response, True
        if stderr:
            return f"Error (stderr): {stderr.decode().strip()}", False
        return "No response generated (empty Codex output).", False

    process: asyncio.subprocess.Process | None = None
    try:
        process = await asyncio.create_subprocess_exec(
            "claude",
            "--print",
            "--model",
            resolved_model,
            "--allowedTools",
            ",".join(provider_allowed_tools or ["Read"]),
            "-p",
            prompt,
            cwd=bot_dir,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={
                **{k: v for k, v in os.environ.items() if k != "CLAUDECODE"},
                "ANTHROPIC_DISABLE_PROMPT_CACHING": "1",
            },
        )

        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        output = stdout.decode().strip()
        error_output = stderr.decode().strip()

        if process.returncode != 0:
            return (
                _format_process_error(
                    stdout,
                    stderr,
                    fallback=f"Claude exited with status {process.returncode}.",
                ),
                False,
            )

        if not output:
            if error_output:
                return f"Error (stderr): {error_output}", False
            return "No response generated (empty stdout, no stderr).", False

        return output, True
    except asyncio.TimeoutError:
        if process is not None:
            await _kill_process(process)
        return f"Job timed out after {timeout} seconds.", False
    except Exception as e:
        return f"Error: {str(e)}", False


async def run_session_prompt(
    *,
    session_dir: str,
    prompt: str,
    bot_dir: str,
    vault_path: str,
    system_prompt_path: str,
    context_path: str,
    channel_settings: dict[str, Any],
    channel_permissions: dict[str, Any],
    model: str | None = None,
    timeout: int = 180,
) -> str:
    """Run a one-shot prompt in a session directory for shell helpers."""
    prepare_session_dir(
        session_dir,
        bot_dir=bot_dir,
        system_prompt_path=system_prompt_path,
        context_path=context_path,
        channel_settings=channel_settings,
        channel_permissions=channel_permissions,
    )

    provider = get_agent_provider()
    resolved_model = resolve_model_for_provider(model or get_default_model(provider), provider)
    effective_prompt = await _prepare_atlas_prompt(
        prompt=prompt,
        bot_dir=bot_dir,
        vault_path=vault_path,
        cwd=session_dir,
        attachment_paths=[],
        allowed_tools=[],
        include_calendar_context=True,
    )

    if provider == "codex":
        session_prelude = await _build_codex_session_start_prelude(
            channel_dir=session_dir,
            bot_dir=bot_dir,
            vault_path=vault_path,
            system_prompt_path=system_prompt_path,
            context_path=context_path,
            channel_settings=channel_settings,
        )
        if session_prelude:
            effective_prompt = f"{session_prelude}\n\n---\n\nUser request:\n{effective_prompt}"
        response, returncode, stdout, stderr = await _run_codex_exec(
            workdir=session_dir,
            prompt=effective_prompt,
            model=resolved_model,
            bot_dir=bot_dir,
            vault_path=vault_path,
            image_paths=[],
            resume_last=False,
            timeout=timeout,
            reasoning_effort=None,
        )
        if returncode != 0:
            raise RuntimeError(
                _format_process_error(
                    stdout,
                    stderr,
                    fallback=f"Codex exited with status {returncode}.",
                )
            )
        return response or "No response from Codex."

    process = await asyncio.create_subprocess_exec(
        "claude",
        "--model",
        resolved_model,
        "--output-format",
        "json",
        "-p",
        effective_prompt,
        cwd=session_dir,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={k: v for k, v in os.environ.items() if k != "CLAUDECODE"},
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    if process.returncode != 0:
        raise RuntimeError(
            _format_process_error(
                stdout,
                stderr,
                fallback=f"Claude exited with status {process.returncode}.",
            )
        )

    try:
        data = json.loads(stdout.decode())
        return data.get("result", "") or "No response from Claude."
    except json.JSONDecodeError:
        return stdout.decode().strip() or "No response from Claude."
