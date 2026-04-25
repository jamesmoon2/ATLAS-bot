"""Shared ATLAS session settings and permission builders."""

from __future__ import annotations

import os
import shlex
from typing import Any

from atlas_utils import shell_command
from mcp_tooling import (
    GMAIL_PERMISSION_PATTERNS,
    GOOGLE_CALENDAR_PERMISSION_PATTERNS,
    GOOGLE_CALENDAR_PRE_TOOL_MATCHERS,
)

BASE_BASH_PERMISSION_PATTERNS = (
    "Bash(find:*)",
    "Bash(grep:*)",
    "Bash(rg:*)",
    "Bash(ls:*)",
    "Bash(cat:*)",
    "Bash(head:*)",
    "Bash(tail:*)",
    "Bash(wc:*)",
    "Bash(tree:*)",
    "Bash(date:*)",
    "Bash(echo:*)",
    "Bash(pwd:*)",
    "Bash(python3:*)",
    "Bash(which:*)",
    "Bash(file:*)",
    "Bash(stat:*)",
    "Bash(du:*)",
    "Bash(df:*)",
    "Bash(mv:*)",
    "Bash(mkdir:*)",
    "Bash(done)",
)

BASE_MCP_PERMISSION_PATTERNS = (
    *GOOGLE_CALENDAR_PERMISSION_PATTERNS,
    *GMAIL_PERMISSION_PATTERNS,
    "mcp__garmin__*",
    "mcp__whoop__*",
)


def build_channel_settings(
    *,
    bot_dir: str,
    system_prompt_path: str,
    context_path: str,
    channel_role_path: str | None = None,
    include_post_tool_hooks: bool = True,
) -> dict[str, Any]:
    """Build provider session hook settings for a channel/session."""
    session_start_hooks = [
        {"type": "command", "command": shell_command("cat", system_prompt_path)},
    ]
    if channel_role_path:
        session_start_hooks.append(
            {"type": "command", "command": shell_command("cat", channel_role_path)}
        )
    session_start_hooks.extend(
        [
            {"type": "command", "command": shell_command("cat", context_path)},
            {"type": "command", "command": "echo '\n---\n# Session Context'"},
            {
                "type": "command",
                "command": "TZ='America/Los_Angeles' date '+**Current Time:** %A, %B %d, %Y %H:%M %Z'",
            },
            {
                "type": "command",
                "command": shlex.quote(os.path.join(bot_dir, "hooks", "tasks_summary.sh")),
            },
            {
                "type": "command",
                "command": shlex.quote(os.path.join(bot_dir, "hooks", "recent_changes.sh")),
            },
            {
                "type": "command",
                "command": shlex.quote(os.path.join(bot_dir, "hooks", "recent_summaries.sh")),
            },
            {
                "type": "command",
                "command": shlex.quote(os.path.join(bot_dir, "hooks", "librarian_context.sh")),
            },
        ]
    )

    hooks: dict[str, Any] = {
        "SessionStart": [{"hooks": session_start_hooks}],
        "PreToolUse": [
            {
                "matcher": matcher,
                "hooks": [
                    {
                        "type": "command",
                        "command": shlex.quote(
                            os.path.join(bot_dir, "hooks", "calendar_context.sh")
                        ),
                    }
                ],
            }
            for matcher in GOOGLE_CALENDAR_PRE_TOOL_MATCHERS
        ],
    }

    if include_post_tool_hooks:
        hooks["PostToolUse"] = [
            {
                "matcher": "Write(**Workout-Logs/20*.md)",
                "hooks": [
                    {
                        "type": "command",
                        "command": shlex.quote(
                            os.path.join(bot_dir, "hooks", "workout_oura_data.sh")
                        ),
                    }
                ],
            }
        ]

    return {"hooks": hooks}


def build_channel_permissions() -> dict[str, Any]:
    """Build provider session permission settings."""
    return {
        "permissions": {
            "allow": [
                "Read(*)",
                "Write(*)",
                "Edit(*)",
                *BASE_BASH_PERMISSION_PATTERNS,
                *BASE_MCP_PERMISSION_PATTERNS,
            ]
        }
    }
