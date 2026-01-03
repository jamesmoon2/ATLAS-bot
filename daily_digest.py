#!/usr/bin/env python3
"""
ATLAS Daily Digest
Generates a morning briefing using Claude Code and posts to Discord.
"""

import asyncio
import os
import sys
from datetime import datetime

import aiohttp
from dotenv import load_dotenv

load_dotenv()

VAULT_PATH = os.getenv("VAULT_PATH", "/home/user/vault")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

DIGEST_PROMPT = """Generate a brief daily digest for James. Today is {date}.

Review the vault and provide:

1. **Tasks Due** - Any tasks with today's date or overdue (check for 📅 dates in markdown files)
2. **Active Projects** - Quick status on projects in /Projects/ that have recent activity
3. **Stale Items** - Anything that hasn't been touched in 2+ weeks that might need attention
4. **Upcoming** - Anything due in the next 7 days

Keep it concise - this is a morning briefing, not a report. Use bullet points.
If there's nothing notable in a category, skip it.

End with one actionable recommendation for the day.
"""


async def run_claude(prompt: str) -> str:
    """Run Claude Code and return the response."""
    try:
        process = await asyncio.create_subprocess_exec(
            "claude",
            "--print",
            "-p",
            prompt,
            cwd=VAULT_PATH,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "ANTHROPIC_DISABLE_PROMPT_CACHING": "1"},
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)

        response = stdout.decode().strip()
        if not response and stderr:
            return f"Error generating digest: {stderr.decode().strip()}"

        return response if response else "No digest generated."
    except asyncio.TimeoutError:
        return "Digest generation timed out."
    except Exception as e:
        return f"Error: {str(e)}"


async def send_to_discord(content: str) -> bool:
    """Send message to Discord via webhook."""
    if not WEBHOOK_URL:
        print("ERROR: DISCORD_WEBHOOK_URL not set", file=sys.stderr)
        return False

    # Discord has a 2000 char limit per message
    chunks = [content[i : i + 1900] for i in range(0, len(content), 1900)]

    async with aiohttp.ClientSession() as session:
        for i, chunk in enumerate(chunks):
            payload = {"content": chunk, "username": "ATLAS Daily Digest"}
            async with session.post(WEBHOOK_URL, json=payload) as resp:
                if resp.status != 204:
                    print(f"Discord webhook failed: {resp.status}", file=sys.stderr)
                    return False

            # Small delay between chunks
            if i < len(chunks) - 1:
                await asyncio.sleep(0.5)

    return True


async def main():
    today = datetime.now().strftime("%A, %B %d, %Y")
    prompt = DIGEST_PROMPT.format(date=today)

    print(f"Generating digest for {today}...")

    digest = await run_claude(prompt)

    # Add header
    header = f"**Daily Digest — {today}**\n\n"
    full_message = header + digest

    # Print to stdout (useful for testing)
    print(full_message)
    print("\n---")

    # Send to Discord if webhook is configured
    if WEBHOOK_URL:
        success = await send_to_discord(full_message)
        if success:
            print("Posted to Discord successfully.")
        else:
            print("Failed to post to Discord.", file=sys.stderr)
            sys.exit(1)
    else:
        print("DISCORD_WEBHOOK_URL not set - skipping Discord post.")


if __name__ == "__main__":
    asyncio.run(main())
