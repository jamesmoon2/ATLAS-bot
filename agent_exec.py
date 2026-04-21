#!/usr/bin/env python3
"""Run a one-shot ATLAS agent prompt from shell scripts."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from agent_runner import resolve_system_prompt_path, run_session_prompt
from mcp_tooling import (
    GMAIL_PERMISSION_PATTERNS,
    GOOGLE_CALENDAR_PERMISSION_PATTERNS,
    GOOGLE_CALENDAR_PRE_TOOL_MATCHERS,
)

BOT_DIR = os.getenv("BOT_DIR", os.path.dirname(os.path.abspath(__file__)))
VAULT_PATH = os.getenv("VAULT_PATH", "/home/user/vault")
SYSTEM_PROMPT_PATH = resolve_system_prompt_path(VAULT_PATH, os.getenv("SYSTEM_PROMPT_PATH"))
CONTEXT_PATH = os.getenv("CONTEXT_PATH", f"{VAULT_PATH}/System/ATLAS-Context.md")


def _shell_command(program: str, *args: str) -> str:
    """Build a shell command with safely quoted arguments."""
    import shlex

    return " ".join(shlex.quote(part) for part in (program, *args))


CHANNEL_SETTINGS = {
    "hooks": {
        "SessionStart": [
            {
                "hooks": [
                    {"type": "command", "command": _shell_command("cat", SYSTEM_PROMPT_PATH)},
                    {"type": "command", "command": _shell_command("cat", CONTEXT_PATH)},
                    {"type": "command", "command": "echo '\n---\n# Session Context'"},
                    {
                        "type": "command",
                        "command": "TZ='America/Los_Angeles' date '+**Current Time:** %A, %B %d, %Y %H:%M %Z'",
                    },
                    {
                        "type": "command",
                        "command": os.path.join(BOT_DIR, "hooks", "tasks_summary.sh"),
                    },
                    {
                        "type": "command",
                        "command": os.path.join(BOT_DIR, "hooks", "recent_changes.sh"),
                    },
                    {
                        "type": "command",
                        "command": os.path.join(BOT_DIR, "hooks", "recent_summaries.sh"),
                    },
                    {
                        "type": "command",
                        "command": os.path.join(BOT_DIR, "hooks", "librarian_context.sh"),
                    },
                ]
            }
        ],
        "PreToolUse": [
            {
                "matcher": matcher,
                "hooks": [
                    {
                        "type": "command",
                        "command": os.path.join(BOT_DIR, "hooks", "calendar_context.sh"),
                    }
                ],
            }
            for matcher in GOOGLE_CALENDAR_PRE_TOOL_MATCHERS
        ],
    }
}

CHANNEL_PERMISSIONS = {
    "permissions": {
        "allow": [
            "Read(*)",
            "Write(*)",
            "Edit(*)",
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
            *GOOGLE_CALENDAR_PERMISSION_PATTERNS,
            *GMAIL_PERMISSION_PATTERNS,
            "mcp__garmin__*",
        ]
    }
}


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Run a one-shot ATLAS agent prompt")
    parser.add_argument("--session-dir", required=True, help="Session directory to run from")
    parser.add_argument(
        "--prompt", required=True, help="Prompt text to send to the active provider"
    )
    parser.add_argument("--model", default=None, help="Optional model override")
    parser.add_argument(
        "--timeout",
        default=180,
        type=int,
        help="Timeout in seconds for the agent run",
    )
    args = parser.parse_args()

    try:
        result = await run_session_prompt(
            session_dir=args.session_dir,
            prompt=args.prompt,
            bot_dir=BOT_DIR,
            vault_path=VAULT_PATH,
            system_prompt_path=SYSTEM_PROMPT_PATH,
            context_path=CONTEXT_PATH,
            channel_settings=CHANNEL_SETTINGS,
            channel_permissions=CHANNEL_PERMISSIONS,
            model=args.model,
            timeout=args.timeout,
        )
    except Exception as e:
        print(json.dumps({"result": "", "error": str(e)}))
        return 1

    print(json.dumps({"result": result}))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
