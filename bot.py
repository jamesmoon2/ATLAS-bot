"""ATLAS Bot - Discord bot wrapping Claude Code CLI."""

import asyncio
import json
import os
import shutil
from typing import Any

import discord
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

VAULT_PATH = os.getenv("VAULT_PATH", "/home/user/vault")
SESSIONS_DIR = os.getenv("SESSIONS_DIR", "./sessions")
BOT_DIR = os.getenv("BOT_DIR", os.path.dirname(os.path.abspath(__file__)))
SYSTEM_PROMPT_PATH = os.getenv("SYSTEM_PROMPT_PATH", f"{VAULT_PATH}/System/claude.md")
MAX_RESPONSE_LENGTH = 1900

# Claude settings for each channel session (built dynamically from env vars)
CHANNEL_SETTINGS: dict[str, Any] = {
    "hooks": {
        "SessionStart": [
            {
                "hooks": [
                    {"type": "command", "command": f"cat {SYSTEM_PROMPT_PATH}"},
                    {"type": "command", "command": "echo '\n---\n# Session Context'"},
                    {"type": "command", "command": "date '+**Current:** %A, %B %d, %Y %H:%M %Z'"},
                    {"type": "command", "command": f"{BOT_DIR}/hooks/tasks_summary.sh"},
                    {"type": "command", "command": f"{BOT_DIR}/hooks/recent_changes.sh"},
                ]
            }
        ]
    }
}

CHANNEL_PERMISSIONS: dict[str, Any] = {
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
            "Bash(which:*)",
            "Bash(file:*)",
            "Bash(stat:*)",
            "Bash(du:*)",
            "Bash(df:*)",
            "Bash(mv:*)",
            "Bash(mkdir:*)",
            "Bash(done)",
        ]
    }
}


def ensure_channel_session(channel_id: int) -> str:
    """Create and configure a session directory for a channel."""
    channel_dir = os.path.join(SESSIONS_DIR, str(channel_id))
    claude_dir = os.path.join(channel_dir, ".claude")

    os.makedirs(claude_dir, exist_ok=True)

    # Write settings.json (hooks)
    settings_path = os.path.join(claude_dir, "settings.json")
    if not os.path.exists(settings_path):
        with open(settings_path, "w") as f:
            json.dump(CHANNEL_SETTINGS, f, indent=2)

    # Write settings.local.json (permissions)
    local_settings_path = os.path.join(claude_dir, "settings.local.json")
    if not os.path.exists(local_settings_path):
        with open(local_settings_path, "w") as f:
            json.dump(CHANNEL_PERMISSIONS, f, indent=2)

    return channel_dir


def reset_channel_session(channel_id: int) -> bool:
    """Delete a channel's session directory to start fresh."""
    channel_dir = os.path.join(SESSIONS_DIR, str(channel_id))
    if os.path.exists(channel_dir):
        shutil.rmtree(channel_dir)
        return True
    return False


async def run_claude(channel_id: int, message_content: str) -> str:
    """Run Claude with session continuity for this channel."""
    try:
        channel_dir = ensure_channel_session(channel_id)

        # Tools allowed for vault file operations
        allowed_tools = "Read,Write,Edit,Glob,Grep,Bash"

        process = await asyncio.create_subprocess_exec(
            "claude",
            "--continue",
            "--print",
            "--allowedTools",
            allowed_tools,
            "-p",
            message_content,
            cwd=channel_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "ANTHROPIC_DISABLE_PROMPT_CACHING": "1"},
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=600,  # 10 minute timeout
        )

        response = stdout.decode().strip()
        if not response and stderr:
            response = f"Error: {stderr.decode().strip()}"

        return response if response else "No response from Claude."
    except asyncio.TimeoutError:
        process.kill()
        return "Request timed out after 10 minutes."
    except Exception as e:
        return f"Error: {str(e)}"


@client.event
async def on_ready():
    print(f"ATLAS online as {client.user}")
    for guild in client.guilds:
        print(f"Connected to: {guild.name}")
        for channel in guild.text_channels:
            print(f"  Channel: {channel.name}")


@client.event
async def on_message(message):
    print(f"Message received: {message.author} in #{message.channel.name}: {message.content[:50]}")

    if message.author == client.user:
        return

    is_mentioned = client.user.mentioned_in(message)
    is_atlas_channel = message.channel.name.lower() == "atlas"

    print(f"  Mentioned: {is_mentioned}, Atlas channel: {is_atlas_channel}")

    if not (is_mentioned or is_atlas_channel):
        return

    content = message.content
    for mention in message.mentions:
        content = content.replace(f"<@{mention.id}>", "").strip()
        content = content.replace(f"<@!{mention.id}>", "").strip()

    # Handle reset command
    if content.lower() in ("!reset", "reset", "!clear", "clear"):
        if reset_channel_session(message.channel.id):
            await message.channel.send("Session cleared. Starting fresh.")
        else:
            await message.channel.send("No session to clear.")
        return

    if not content:
        await message.channel.send("What do you need?")
        return

    print(f"  Processing: {content[:50]}")

    async with message.channel.typing():
        response = await run_claude(message.channel.id, content)

    print(f"  Response length: {len(response)}")

    if len(response) <= MAX_RESPONSE_LENGTH:
        await message.channel.send(response)
    else:
        chunks = [
            response[i : i + MAX_RESPONSE_LENGTH]
            for i in range(0, len(response), MAX_RESPONSE_LENGTH)
        ]
        for chunk in chunks:
            await message.channel.send(chunk)


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("DISCORD_TOKEN not found")
        exit(1)
    client.run(token)
