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
                    {"type": "command", "command": "TZ='America/Los_Angeles' date '+**Current:** %A, %B %d, %Y %H:%M %Z'"},
                    {"type": "command", "command": f"{BOT_DIR}/hooks/tasks_summary.sh"},
                    {"type": "command", "command": f"{BOT_DIR}/hooks/recent_changes.sh"},
                ]
            }
        ],
        "PreToolUse": [
            {
                "matcher": "mcp__google-calendar__create-event",
                "hooks": [
                    {"type": "command", "command": f"{BOT_DIR}/hooks/calendar_context.sh"}
                ]
            },
            {
                "matcher": "mcp__google-calendar__update-event",
                "hooks": [
                    {"type": "command", "command": f"{BOT_DIR}/hooks/calendar_context.sh"}
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
    """Delete a channel's session directory and Claude's session storage."""
    channel_dir = os.path.join(SESSIONS_DIR, str(channel_id))

    # Also clear Claude's session storage in ~/.claude/projects/
    # Claude stores sessions based on the working directory path
    abs_channel_dir = os.path.abspath(channel_dir)
    claude_project_name = abs_channel_dir.replace("/", "-")
    claude_projects_dir = os.path.expanduser("~/.claude/projects")
    claude_session_dir = os.path.join(claude_projects_dir, claude_project_name)

    cleared = False

    # Clear local session directory
    if os.path.exists(channel_dir):
        shutil.rmtree(channel_dir)
        cleared = True

    # Clear Claude's session storage
    if os.path.exists(claude_session_dir):
        shutil.rmtree(claude_session_dir)
        cleared = True

    return cleared


def get_channel_model(channel_id: int) -> str:
    """Get the model preference for a channel, default to sonnet."""
    channel_dir = os.path.join(SESSIONS_DIR, str(channel_id))
    model_file = os.path.join(channel_dir, "model.txt")
    if os.path.exists(model_file):
        with open(model_file, "r") as f:
            return f.read().strip()
    return "sonnet"  # default


def set_channel_model(channel_id: int, model: str) -> None:
    """Set the model preference for a channel."""
    channel_dir = ensure_channel_session(channel_id)
    model_file = os.path.join(channel_dir, "model.txt")
    with open(model_file, "w") as f:
        f.write(model)


async def run_claude(channel_id: int, message_content: str) -> str:
    """Run Claude with session continuity for this channel."""
    try:
        channel_dir = ensure_channel_session(channel_id)
        model = get_channel_model(channel_id)

        # Tools allowed for vault file operations
        allowed_tools = "Read,Write,Edit,Glob,Grep,Bash"

        process = await asyncio.create_subprocess_exec(
            "claude",
            "--model",
            model,
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

    # Handle model command
    if content.lower().startswith("!model"):
        parts = content.split()
        if len(parts) == 1:
            # Show current model
            current = get_channel_model(message.channel.id)
            await message.channel.send(f"Current model: {current}")
            return
        elif len(parts) == 2:
            model = parts[1].lower()
            if model in ("sonnet", "opus"):
                set_channel_model(message.channel.id, model)
                await message.channel.send(f"Switched to {model}.")
                return
            else:
                await message.channel.send("Invalid model. Use: !model sonnet or !model opus")
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
