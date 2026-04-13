"""Shared agent runner for Claude Code and Codex-backed ATLAS sessions."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import subprocess
import tempfile
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
CODEX_WORKOUT_HELP_FILENAME = "ATLAS-Workout-Postwrite.md"
CODEX_HOME_DIRNAME = ".atlas-codex-home"
CODEX_SANDBOX_MODES = {"read-only", "workspace-write", "danger-full-access"}
CODEX_CURATED_PLUGINS = (
    "google-calendar@openai-curated",
    "github@openai-curated",
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

    return str(system_dir / "claude.md")


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
    skills_dir = Path(bot_dir) / ".claude" / "skills"
    calendar_context_path = Path(channel_dir) / CODEX_CALENDAR_CONTEXT_FILENAME
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
        f"- After writing a workout log under `Workout-Logs/YYYY-MM-DD.md`, read `{workout_help_path}` and complete the checklist.",
        "- Keep the behavior aligned with ATLAS operational conventions rather than Codex defaults.",
    ]
    return "\n".join(sections) + "\n"


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

    settings_path = claude_dir / "settings.json"
    _atomic_write_json(settings_path, channel_settings)

    local_settings_path = claude_dir / "settings.local.json"
    _atomic_write_json(local_settings_path, channel_permissions)

    skills_symlink = claude_dir / "skills"
    skills_target = Path(bot_dir) / ".claude" / "skills"
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
) -> list[str]:
    """Build the shared Codex CLI prefix."""
    reasoning_effort = os.getenv("ATLAS_CODEX_REASONING_EFFORT", "xhigh")
    sandbox_mode = _get_codex_sandbox_mode()
    prefix = [
        "codex",
        "exec",
        "-C",
        workdir,
        "-m",
        model,
        "-s",
        sandbox_mode,
        "--skip-git-repo-check",
        "--add-dir",
        bot_dir,
        "--add-dir",
        vault_path,
        "-c",
        f'model_reasoning_effort="{reasoning_effort}"',
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

    lines.extend(
        [
            "[mcp_servers.oura]",
            f"command = {json.dumps(oura_python)}",
            f"args = {json.dumps([oura_script])}",
            "",
            "[mcp_servers.weather]",
            'command = "npx"',
            'args = ["-y", "@dangahagan/weather-mcp@latest"]',
            "",
        ]
    )
    return "\n".join(lines)


def _ensure_codex_home(bot_dir: str, vault_path: str) -> Path:
    """Create or refresh the managed Codex profile for ATLAS."""
    codex_home = _get_codex_home(bot_dir)
    codex_home.mkdir(parents=True, exist_ok=True)
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


def _skill_path(bot_dir: str, skill_name: str) -> Path:
    """Resolve a repo-local ATLAS skill path."""
    return Path(bot_dir) / ".claude" / "skills" / f"{skill_name}.md"


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
    lowered_prompt = prompt.lower()
    return any(token in lowered_prompt for token in ("calendar", "schedule", "meeting", "event"))


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
) -> tuple[str, int, bytes, bytes]:
    """Execute Codex and return (response_text, returncode, stdout, stderr)."""
    fd, output_file = tempfile.mkstemp(prefix="atlas-codex-", suffix=".txt")
    os.close(fd)

    prefix = _codex_command_prefix(
        workdir=workdir,
        model=model,
        bot_dir=bot_dir,
        vault_path=vault_path,
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
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        response = _extract_codex_output(output_file)
        return response, process.returncode, stdout, stderr
    except asyncio.TimeoutError:
        if process is not None:
            await _kill_process(process)
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

    if provider == "codex":
        return await _run_codex_channel_message(
            prompt=prompt,
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
        prompt=prompt,
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

    effective_prompt = _expand_skill_prompt_if_needed(prompt, bot_dir)
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
) -> tuple[str, bool]:
    """Run a one-shot job prompt through the active provider."""
    provider = get_agent_provider()
    resolved_model = resolve_model_for_provider(model, provider)
    provider_allowed_tools = normalize_allowed_tools_for_provider(allowed_tools, provider)

    if provider == "codex":
        effective_prompt = _build_scheduled_job_note()
        effective_prompt += _build_allowed_tools_note(provider_allowed_tools)
        effective_prompt += _expand_skill_prompt_if_needed(prompt, bot_dir)
        if _needs_calendar_context(provider_allowed_tools, prompt):
            calendar_hook = Path(bot_dir) / "hooks" / "calendar_context.sh"
            if calendar_hook.exists():
                calendar_context = await _capture_shell(
                    str(calendar_hook),
                    env=os.environ.copy(),
                    cwd=bot_dir,
                )
                if calendar_context:
                    effective_prompt += f"\n\n{calendar_context}\n"

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

    if provider == "codex":
        effective_prompt = _expand_skill_prompt_if_needed(prompt, bot_dir)
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
        prompt,
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
