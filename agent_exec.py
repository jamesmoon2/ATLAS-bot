#!/usr/bin/env python3
"""Run a one-shot ATLAS agent prompt from shell scripts."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from agent_runner import resolve_system_prompt_path, run_session_prompt
from atlas_config import build_channel_permissions, build_channel_settings

BOT_DIR = os.getenv("BOT_DIR", os.path.dirname(os.path.abspath(__file__)))
VAULT_PATH = os.getenv("VAULT_PATH", "/home/user/vault")
SYSTEM_PROMPT_PATH = resolve_system_prompt_path(VAULT_PATH, os.getenv("SYSTEM_PROMPT_PATH"))
CONTEXT_PATH = os.getenv("CONTEXT_PATH", f"{VAULT_PATH}/System/ATLAS-Context.md")


CHANNEL_SETTINGS = build_channel_settings(
    bot_dir=BOT_DIR,
    system_prompt_path=SYSTEM_PROMPT_PATH,
    context_path=CONTEXT_PATH,
)

CHANNEL_PERMISSIONS = build_channel_permissions()


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
