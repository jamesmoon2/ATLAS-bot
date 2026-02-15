"""ATLAS Bot - Discord bot wrapping Claude Code CLI."""

import asyncio
import json
import os
import shutil
import signal
import uuid
from typing import Any

import discord
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

client = discord.Client(intents=intents)

VAULT_PATH = os.getenv("VAULT_PATH", "/home/user/vault")
SESSIONS_DIR = os.getenv("SESSIONS_DIR", "./sessions")
BOT_DIR = os.getenv("BOT_DIR", os.path.dirname(os.path.abspath(__file__)))
SYSTEM_PROMPT_PATH = os.getenv("SYSTEM_PROMPT_PATH", f"{VAULT_PATH}/System/claude.md")
CONTEXT_PATH = os.getenv("CONTEXT_PATH", f"{VAULT_PATH}/System/ATLAS-Context.md")
MAX_RESPONSE_LENGTH = 1900

# Supported media types for Claude Code Read tool (images + PDFs)
SUPPORTED_MEDIA = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf"}

# Per-channel concurrency locks to prevent simultaneous Claude processes
channel_locks: dict[int, asyncio.Lock] = {}


def get_channel_lock(channel_id: int) -> asyncio.Lock:
    """Get or create an asyncio.Lock for a channel."""
    if channel_id not in channel_locks:
        channel_locks[channel_id] = asyncio.Lock()
    return channel_locks[channel_id]


# Claude settings for each channel session (built dynamically from env vars)
CHANNEL_SETTINGS: dict[str, Any] = {
    "hooks": {
        "SessionStart": [
            {
                "hooks": [
                    {"type": "command", "command": f"cat {SYSTEM_PROMPT_PATH}"},
                    {"type": "command", "command": f"cat {CONTEXT_PATH}"},
                    {"type": "command", "command": "echo '\n---\n# Session Context'"},
                    {
                        "type": "command",
                        "command": "TZ='America/Los_Angeles' date '+**Current Time:** %A, %B %d, %Y %H:%M %Z'",
                    },
                    {"type": "command", "command": f"{BOT_DIR}/hooks/tasks_summary.sh"},
                    {"type": "command", "command": f"{BOT_DIR}/hooks/recent_changes.sh"},
                    {"type": "command", "command": f"{BOT_DIR}/hooks/recent_summaries.sh"},
                ]
            }
        ],
        "PreToolUse": [
            {
                "matcher": "mcp__google-calendar__create-event",
                "hooks": [{"type": "command", "command": f"{BOT_DIR}/hooks/calendar_context.sh"}],
            },
            {
                "matcher": "mcp__google-calendar__update-event",
                "hooks": [{"type": "command", "command": f"{BOT_DIR}/hooks/calendar_context.sh"}],
            },
        ],
        "PostToolUse": [
            {
                "matcher": "Write(**Workout-Logs/20*.md)",
                "hooks": [{"type": "command", "command": f"{BOT_DIR}/hooks/workout_oura_data.sh"}],
            }
        ],
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
            "mcp__garmin__*",
        ]
    }
}


def ensure_channel_session(channel_id: int) -> str:
    """Create and configure a session directory for a channel."""
    channel_dir = os.path.join(SESSIONS_DIR, str(channel_id))
    claude_dir = os.path.join(channel_dir, ".claude")

    os.makedirs(claude_dir, exist_ok=True)

    # Write settings.json (hooks) - always overwrite to pick up code changes
    settings_path = os.path.join(claude_dir, "settings.json")
    with open(settings_path, "w") as f:
        json.dump(CHANNEL_SETTINGS, f, indent=2)

    # Write settings.local.json (permissions) - always overwrite to pick up code changes
    local_settings_path = os.path.join(claude_dir, "settings.local.json")
    with open(local_settings_path, "w") as f:
        json.dump(CHANNEL_PERMISSIONS, f, indent=2)

    # Create skills symlink if it doesn't exist
    skills_symlink = os.path.join(claude_dir, "skills")
    skills_target = os.path.expanduser("~/.claude/skills")
    if not os.path.exists(skills_symlink) and os.path.exists(skills_target):
        os.symlink(skills_target, skills_symlink)

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
        shutil.rmtree(channel_dir, ignore_errors=True)
        cleared = True

    # Clear Claude's session storage
    if os.path.exists(claude_session_dir):
        shutil.rmtree(claude_session_dir)
        cleared = True

    return cleared


async def download_attachments(channel_id: int, attachments: list) -> list[str]:
    """Download Discord attachments to session directory."""
    if not attachments:
        return []

    channel_dir = ensure_channel_session(channel_id)
    attachments_dir = os.path.join(channel_dir, "attachments")
    os.makedirs(attachments_dir, exist_ok=True)

    downloaded = []
    for att in attachments:
        _, ext = os.path.splitext(att.filename)
        if ext.lower() not in SUPPORTED_MEDIA:
            continue

        unique_name = f"{uuid.uuid4().hex[:8]}_{att.filename}"
        file_path = os.path.join(attachments_dir, unique_name)

        try:
            await att.save(file_path)
            downloaded.append(os.path.abspath(file_path))
        except Exception as e:
            print(f"Failed to download {att.filename}: {e}")

    return downloaded


def build_prompt_with_files(content: str, file_paths: list[str]) -> str:
    """Build prompt with file references for Claude to read."""
    if not file_paths:
        return content

    files_section = "\n\n[Attached files - use Read tool to view:]\n"
    for path in file_paths:
        files_section += f"- {path}\n"

    return (content or "Please analyze the attached file(s).") + files_section


def get_channel_model(channel_id: int) -> str:
    """Get the model preference for a channel, default to sonnet."""
    channel_dir = os.path.join(SESSIONS_DIR, str(channel_id))
    model_file = os.path.join(channel_dir, "model.txt")
    if os.path.exists(model_file):
        with open(model_file) as f:
            return f.read().strip()
    return "opus"  # default


def set_channel_model(channel_id: int, model: str) -> None:
    """Set the model preference for a channel."""
    channel_dir = ensure_channel_session(channel_id)
    model_file = os.path.join(channel_dir, "model.txt")
    with open(model_file, "w") as f:
        f.write(model)


async def run_claude(channel_id: int, message_content: str) -> str:
    """Run Claude with session continuity for this channel.

    Returns:
        str: response_text
    """
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
            "--output-format",
            "json",
            "--allowedTools",
            allowed_tools,
            "-p",
            message_content,
            cwd=channel_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={k: v for k, v in os.environ.items() if k != "CLAUDECODE"},
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=600,  # 10 minute timeout
        )

        # Parse JSON response
        try:
            data = json.loads(stdout.decode())
            response = data.get("result", "")
            print(f"  modelUsage: {data.get('modelUsage', 'NOT FOUND')}")

            if not response and stderr:
                response = f"Error: {stderr.decode().strip()}"

            return response if response else "No response from Claude."
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
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

    if message.author.bot:
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

    # Handle help command
    if content.lower() in ("!help", "help"):
        help_text = (
            "**ATLAS Commands**\n\n"
            "**!help** - Show this message\n"
            "**!model** - Show current model\n"
            "**!model sonnet|opus** - Switch model\n"
            "**!reset** - Clear session and start fresh\n\n"
            "Or just send a message and I'll respond."
        )
        await message.channel.send(help_text)
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

    # Download attachments (images, PDFs, etc.)
    downloaded_files = []
    if message.attachments:
        downloaded_files = await download_attachments(message.channel.id, message.attachments)
        if downloaded_files:
            print(f"  Downloaded {len(downloaded_files)} attachment(s)")

    # Build prompt with file references
    prompt = build_prompt_with_files(content, downloaded_files)

    # Check if we have something to process
    if not content and not downloaded_files:
        await message.channel.send("What do you need?")
        return

    print(f"  Processing: {prompt[:50]}")

    lock = get_channel_lock(message.channel.id)
    if lock.locked():
        await message.channel.send("Processing your previous message, one moment...")

    async with message.channel.typing():
        async with lock:
            response = await run_claude(message.channel.id, prompt)

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


async def log_medication_dose(med_name: str, timestamp: str) -> bool:
    """Log medication dose to Medications.md file.

    Args:
        med_name: Name of medication (e.g., "Medrol 5mg", "Vitaplex + Neupro 300 units", "Vitaplex")
        timestamp: ISO timestamp of dose

    Returns:
        bool: True if logged successfully
    """
    try:
        from datetime import datetime

        med_file = f"{VAULT_PATH}/Areas/Health/Medications.md"

        # Read current file
        if not os.path.exists(med_file):
            print(f"Warning: {med_file} does not exist")
            return False

        with open(med_file) as f:
            lines = f.readlines()

        # Format timestamp
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        date_str = dt.strftime("%Y-%m-%d")
        day_of_week = dt.strftime("%a %p")  # e.g., "Wed AM"

        # Determine which table to append to and format entry
        if "Medrol" in med_name:
            # Find Medrol dosing table and append
            table_marker = "## Dosing Log"
            entry = f"| {date_str} | 2mg | — | {day_of_week} | Auto-logged via ✅ |\n"
        else:  # Vitaplex
            # Find Vitaplex dosing table and append
            table_marker = "### Dosing Log"  # Vitaplex section uses h3
            # Parse medication components
            if "Neupro" in med_name:
                entry = (
                    f"| {date_str} | Vitaplex + Neupro | {day_of_week} | Auto-logged via ✅ |\n"
                )
            else:
                entry = f"| {date_str} | Vitaplex | {day_of_week} | Auto-logged via ✅ |\n"

        # Find insertion point (after last table row before next section)
        insert_index = None
        in_correct_section = False
        for i, line in enumerate(lines):
            if table_marker in line and (
                "Medrol" in med_name
                and "## Dosing Log" in line
                or "Medrol" not in med_name
                and "### Dosing Log" in line
            ):
                in_correct_section = True
            elif in_correct_section and line.startswith("|"):
                insert_index = i + 1  # After this table row
            elif in_correct_section and line.strip() == "---":
                # End of table section
                break

        if insert_index is None:
            print(f"Could not find insertion point for {med_name}")
            return False

        # Insert the new entry
        lines.insert(insert_index, entry)

        # Write back
        with open(med_file, "w") as f:
            f.writelines(lines)

        print(f"Logged dose: {med_name} at {date_str} ({day_of_week})")
        return True

    except Exception as e:
        print(f"Error logging medication: {e}")
        import traceback

        traceback.print_exc()
        return False


@client.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    """Handle reactions to bot messages for auto-logging."""

    # Ignore bot's own reactions
    if user.bot:
        return

    # Only process checkmark reactions
    if str(reaction.emoji) != "✅":
        return

    # Only process reactions to bot messages
    if reaction.message.author != client.user:
        return

    # Check if this is a medication reminder message
    content = reaction.message.content
    if "Medication Reminder" not in content:
        return

    print(f"Checkmark reaction from {user.name} on medication reminder")

    # Parse medication name from message
    med_name = None
    if "Medrol 5mg" in content:
        med_name = "Medrol 5mg"
    elif "Vitaplex + Neupro 300 units" in content:
        med_name = "Vitaplex + Neupro 300 units"
    elif "Vitaplex" in content:
        med_name = "Vitaplex"

    if not med_name:
        print("Could not parse medication name from reminder")
        return

    # Get timestamp (use reaction time)
    timestamp = reaction.message.created_at.isoformat()

    # Log the dose
    success = await log_medication_dose(med_name, timestamp)

    if success:
        # Update agent state to mark as confirmed
        state_file = f"{VAULT_PATH}/System/agent-state.json"
        try:
            with open(state_file) as f:
                state = json.load(f)

            if med_name not in state.get("med_reminders", {}):
                state.setdefault("med_reminders", {})[med_name] = {}

            state["med_reminders"][med_name]["confirmed"] = True
            state["med_reminders"][med_name]["confirmed_at"] = timestamp

            with open(state_file, "w") as f:
                json.dump(state, f, indent=2)

            print(f"Updated agent state for {med_name}")

        except Exception as e:
            print(f"Error updating agent state: {e}")

        # React to acknowledge
        await reaction.message.add_reaction("📝")


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("DISCORD_TOKEN not found")
        exit(1)

    def handle_signal(sig, _frame):
        print(f"Received signal {signal.Signals(sig).name}, shutting down...")
        asyncio.get_event_loop().create_task(client.close())

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    client.run(token)
