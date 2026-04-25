"""ATLAS Bot - Discord bot wrapping the configured agent harness."""

import asyncio
import json
import os
import re
import signal
import uuid
from datetime import datetime, timezone

import discord
from dotenv import load_dotenv

from agent_runner import (
    build_prompt_with_attachments,
    clear_provider_private_session_state,
    get_agent_provider,
    get_user_selectable_models,
    prepare_session_dir,
    resolve_model_for_provider,
    resolve_system_prompt_path,
    run_channel_message,
)
from atlas_config import build_channel_permissions, build_channel_settings
from atlas_utils import atomic_write_json, atomic_write_text
from channel_configs import ChannelConfig, get_channel_config, render_channel_role_context
from med_config import find_med_by_content

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

client = discord.Client(intents=intents)

VAULT_PATH = os.getenv("VAULT_PATH", "/home/user/vault")
SESSIONS_DIR = os.getenv("SESSIONS_DIR", "./sessions")
BOT_DIR = os.getenv("BOT_DIR", os.path.dirname(os.path.abspath(__file__)))
SYSTEM_PROMPT_PATH = resolve_system_prompt_path(VAULT_PATH, os.getenv("SYSTEM_PROMPT_PATH"))
CONTEXT_PATH = os.getenv("CONTEXT_PATH", f"{VAULT_PATH}/System/ATLAS-Context.md")
MAX_RESPONSE_LENGTH = 1900

# Supported media types for agent attachment handling (images + PDFs)
SUPPORTED_MEDIA = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf"}

# Per-channel concurrency locks to prevent simultaneous agent runs
channel_locks: dict[int, asyncio.Lock] = {}


def get_channel_lock(channel_id: int) -> asyncio.Lock:
    """Get or create an asyncio.Lock for a channel."""
    if channel_id not in channel_locks:
        channel_locks[channel_id] = asyncio.Lock()
    return channel_locks[channel_id]


def _sanitize_attachment_filename(filename: str) -> str:
    """Collapse unsafe attachment path characters into a safe basename."""
    basename = os.path.basename(filename.replace("\\", "/"))
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", basename).strip("._")
    return safe_name or "attachment"


def get_reaction_timestamp() -> str:
    """Return the current UTC timestamp for a reaction confirmation."""
    return datetime.now(timezone.utc).isoformat()


# Session settings for each channel session (built dynamically from env vars)
CHANNEL_SETTINGS = build_channel_settings(
    bot_dir=BOT_DIR,
    system_prompt_path=SYSTEM_PROMPT_PATH,
    context_path=CONTEXT_PATH,
)

CHANNEL_PERMISSIONS = build_channel_permissions()


def _build_session_settings(channel_dir: str) -> dict:
    role_path = os.path.join(channel_dir, "ATLAS-Channel-Role.md")
    return build_channel_settings(
        bot_dir=BOT_DIR,
        system_prompt_path=SYSTEM_PROMPT_PATH,
        context_path=CONTEXT_PATH,
        channel_role_path=role_path,
    )


def ensure_channel_session(
    channel_id: int,
    *,
    channel_name: str = "",
    channel_config: ChannelConfig | None = None,
) -> str:
    """Create and configure a session directory for a channel."""
    channel_dir = os.path.join(SESSIONS_DIR, str(channel_id))
    resolved_config = channel_config or get_channel_config(
        channel_id=channel_id,
        channel_name=channel_name,
    )
    default_model = resolved_config.default_model if resolved_config else "opus"
    role_context = render_channel_role_context(resolved_config, channel_name=channel_name)
    prepare_session_dir(
        channel_dir,
        bot_dir=BOT_DIR,
        system_prompt_path=SYSTEM_PROMPT_PATH,
        context_path=CONTEXT_PATH,
        channel_settings=_build_session_settings(channel_dir),
        channel_permissions=CHANNEL_PERMISSIONS,
        channel_role_context=role_context,
        channel_id=channel_id,
        channel_name=channel_name or None,
        channel_key=resolved_config.key if resolved_config else None,
        default_model=default_model,
    )
    return channel_dir


def reset_channel_session(channel_id: int) -> bool:
    """Delete a channel's session directory and related provider session artifacts."""
    channel_dir = os.path.join(SESSIONS_DIR, str(channel_id))

    cleared = False

    # Clear local session directory
    if os.path.exists(channel_dir):
        import shutil

        shutil.rmtree(channel_dir, ignore_errors=True)
        cleared = True

    # Clear external provider-managed session storage.
    if clear_provider_private_session_state(channel_dir):
        cleared = True

    return cleared


async def download_attachments(
    channel_id: int,
    attachments: list,
    *,
    channel_name: str = "",
    channel_config: ChannelConfig | None = None,
) -> list[str]:
    """Download Discord attachments to session directory."""
    if not attachments:
        return []

    channel_dir = ensure_channel_session(
        channel_id,
        channel_name=channel_name,
        channel_config=channel_config,
    )
    attachments_dir = os.path.join(channel_dir, "attachments")
    os.makedirs(attachments_dir, exist_ok=True)

    downloaded = []
    for att in attachments:
        _, ext = os.path.splitext(att.filename)
        if ext.lower() not in SUPPORTED_MEDIA:
            continue

        safe_name = _sanitize_attachment_filename(att.filename)
        unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
        file_path = os.path.join(attachments_dir, unique_name)

        try:
            await att.save(file_path)
            downloaded.append(os.path.abspath(file_path))
        except Exception as e:
            print(f"Failed to download {att.filename}: {e}")

    return downloaded


def build_prompt_with_files(content: str, file_paths: list[str]) -> str:
    """Build a provider-neutral prompt with file references."""
    return build_prompt_with_attachments(content, file_paths)


def build_librarian_prompt(command: str, args: str) -> str:
    """Build a librarian-focused prompt for note recall and review workflows."""
    index_path = os.path.join(VAULT_PATH, "System", "vault-index.json")
    markdown_index_path = os.path.join(VAULT_PATH, "System", "vault-index.md")
    query = args.strip()

    if command == "recall":
        return (
            "Act as ATLAS's second-brain librarian.\n\n"
            f"Use `{index_path}` as the primary map of the vault and `{markdown_index_path}` for a "
            "human-readable overview. Read any relevant notes you need.\n\n"
            f"Recall request: {query}\n\n"
            "Respond with:\n"
            "1. The most relevant notes or areas to inspect\n"
            "2. A concise synthesis of what the vault says\n"
            "3. Any open loops or contradictions you notice\n"
            "4. Suggested next notes to open if context is missing"
        )

    prompts = {
        "open-loops": (
            "Act as ATLAS's second-brain librarian.\n\n"
            f"Use `{index_path}` and related notes to summarize the user's current open loops. "
            "Prioritize unresolved tasks, waiting states, and notes with Next Actions / Unresolved / "
            "Waiting On / TBD sections. Group the result by theme and keep it concise."
        ),
        "recent-notes": (
            "Act as ATLAS's second-brain librarian.\n\n"
            f"Use `{index_path}` to identify the most recently updated notes. Read the most relevant "
            "recent notes and summarize what changed, why it matters, and any follow-up worth doing."
        ),
        "orphan-notes": (
            "Act as ATLAS's second-brain librarian.\n\n"
            f"Use `{index_path}` to identify orphan notes. Read the highest-priority orphan notes and "
            "report which ones should be linked, archived, merged, or ignored."
        ),
        "librarian": (
            "Act as ATLAS's second-brain librarian.\n\n"
            f"Use `{index_path}` as the primary vault map. Provide a compact librarian digest covering "
            "recent note activity, open loops, orphan notes, stale notes, and the 3 highest-value "
            "cleanup or synthesis actions."
        ),
    }
    return prompts[command]


async def send_chunked_response(channel, response: str) -> None:
    """Send a response, splitting it to fit Discord message limits."""
    if len(response) <= MAX_RESPONSE_LENGTH:
        await channel.send(response)
        return

    chunks = [
        response[i : i + MAX_RESPONSE_LENGTH] for i in range(0, len(response), MAX_RESPONSE_LENGTH)
    ]
    for chunk in chunks:
        await channel.send(chunk)


def strip_bot_mentions(content: str, mentions: list) -> str:
    """Remove Discord mention syntax from message content."""
    stripped_content = content
    for mention in mentions:
        stripped_content = stripped_content.replace(f"<@{mention.id}>", "").strip()
        stripped_content = stripped_content.replace(f"<@!{mention.id}>", "").strip()
    return stripped_content


def build_help_text() -> str:
    """Build the Discord help text for the current provider."""
    available_models = ", ".join(get_user_selectable_models())
    current_provider = get_agent_provider()
    return (
        "**ATLAS Commands**\n\n"
        "**!help** - Show this message\n"
        "**!model** - Show current model\n"
        f"**!model <model>** - Switch model (provider: {current_provider}; available: {available_models})\n"
        "**!recall <query>** - Search your vault like a librarian\n"
        "**!recent-notes** - Summarize recently updated notes\n"
        "**!open-loops** - Review unresolved tasks and waiting states\n"
        "**!orphan-notes** - Find notes that need links or cleanup\n"
        "**!librarian** - Generate a compact second-brain digest\n"
        "**!reset** - Clear session and start fresh\n\n"
        "Or just send a message and I'll respond."
    )


async def handle_reset_command(message, content: str) -> bool:
    """Handle reset/clear commands. Returns whether a command was handled."""
    if content.lower() not in ("!reset", "reset", "!clear", "clear"):
        return False

    if reset_channel_session(message.channel.id):
        await message.channel.send("Session cleared. Starting fresh.")
    else:
        await message.channel.send("No session to clear.")
    return True


async def handle_help_command(message, content: str) -> bool:
    """Handle help commands. Returns whether a command was handled."""
    if content.lower() not in ("!help", "help"):
        return False

    await message.channel.send(build_help_text())
    return True


async def handle_model_command(
    message,
    content: str,
    channel_config: ChannelConfig | None = None,
) -> bool:
    """Handle model commands. Returns whether a command was handled."""
    if not content.lower().startswith("!model"):
        return False

    parts = content.split()
    available_models = get_user_selectable_models()
    if len(parts) == 1:
        current = get_channel_model(message.channel.id, channel_config)
        await message.channel.send(f"Current model: {current} (provider: {get_agent_provider()})")
        return True

    if len(parts) == 2:
        model = parts[1].lower()
        if model in available_models:
            set_channel_model(
                message.channel.id,
                model,
                channel_config=channel_config,
                channel_name=message.channel.name,
            )
            await message.channel.send(f"Switched to {model}.")
            return True

        valid_models = ", ".join(available_models)
        await message.channel.send(f"Invalid model. Available now: {valid_models}")
        return True

    return False


async def handle_librarian_command(
    message,
    content: str,
    channel_config: ChannelConfig | None = None,
) -> bool:
    """Handle librarian commands. Returns whether a command was handled."""
    librarian_commands = {
        "!recall": "recall",
        "!open-loops": "open-loops",
        "!recent-notes": "recent-notes",
        "!orphan-notes": "orphan-notes",
        "!librarian": "librarian",
    }
    lowered_content = content.lower()
    for prefix, command_name in librarian_commands.items():
        if lowered_content != prefix and not lowered_content.startswith(prefix + " "):
            continue

        args = content[len(prefix) :].strip()
        if command_name == "recall" and not args:
            await message.channel.send("Usage: !recall <query>")
            return True

        prompt = build_librarian_prompt(command_name, args)
        print(f"  Librarian command: {command_name}")

        lock = get_channel_lock(message.channel.id)
        if lock.locked():
            await message.channel.send("Processing your previous message, one moment...")

        async with message.channel.typing():
            async with lock:
                response = await run_agent(
                    message.channel.id,
                    prompt,
                    channel_name=message.channel.name,
                    channel_config=channel_config,
                )

        await send_chunked_response(message.channel, response)
        return True

    return False


def get_channel_model(channel_id: int, channel_config: ChannelConfig | None = None) -> str:
    """Get the model preference for a channel."""
    channel_dir = os.path.join(SESSIONS_DIR, str(channel_id))
    model_file = os.path.join(channel_dir, "model.txt")
    if os.path.exists(model_file):
        with open(model_file) as f:
            return resolve_model_for_provider(f.read().strip())
    default_model = channel_config.default_model if channel_config else "opus"
    return resolve_model_for_provider(default_model)


def set_channel_model(
    channel_id: int,
    model: str,
    channel_config: ChannelConfig | None = None,
    channel_name: str = "",
) -> None:
    """Set the model preference for a channel."""
    channel_dir = ensure_channel_session(
        channel_id,
        channel_name=channel_name,
        channel_config=channel_config,
    )
    model_file = os.path.join(channel_dir, "model.txt")
    atomic_write_text(model_file, model)


async def run_claude(channel_id: int, message_content: str) -> str:
    """Run the active provider with session continuity for this channel.

    Returns:
        str: response_text
    """
    return await run_agent(channel_id, message_content)


async def run_agent(
    channel_id: int,
    message_content: str,
    attachment_paths: list[str] | None = None,
    *,
    channel_name: str = "",
    channel_config: ChannelConfig | None = None,
) -> str:
    """Run the configured agent provider for this channel."""
    try:
        resolved_config = channel_config or get_channel_config(
            channel_id=channel_id,
            channel_name=channel_name,
        )
        channel_dir = ensure_channel_session(
            channel_id,
            channel_name=channel_name,
            channel_config=resolved_config,
        )
        model = get_channel_model(channel_id, resolved_config)
        channel_settings = _build_session_settings(channel_dir)
        return await run_channel_message(
            channel_id=channel_id,
            prompt=message_content,
            attachment_paths=attachment_paths or [],
            channel_dir=channel_dir,
            model=model,
            bot_dir=BOT_DIR,
            vault_path=VAULT_PATH,
            system_prompt_path=SYSTEM_PROMPT_PATH,
            context_path=CONTEXT_PATH,
            channel_settings=channel_settings,
        )
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
    channel_config = get_channel_config(
        channel_id=message.channel.id,
        channel_name=message.channel.name,
    )
    is_configured_channel = channel_config is not None and channel_config.auto_activate

    print(f"  Mentioned: {is_mentioned}, Configured channel: {is_configured_channel}")

    if not (is_mentioned or is_configured_channel):
        return

    content = strip_bot_mentions(message.content, message.mentions)

    if await handle_reset_command(message, content):
        return

    if await handle_help_command(message, content):
        return

    if await handle_model_command(message, content, channel_config):
        return

    if await handle_librarian_command(message, content, channel_config):
        return

    # Download attachments (images, PDFs, etc.)
    downloaded_files = []
    if message.attachments:
        downloaded_files = await download_attachments(
            message.channel.id,
            message.attachments,
            channel_name=message.channel.name,
            channel_config=channel_config,
        )
        if downloaded_files:
            print(f"  Downloaded {len(downloaded_files)} attachment(s)")

    # Check if we have something to process
    if not content and not downloaded_files:
        await message.channel.send("What do you need?")
        return

    prompt = content
    preview = prompt or "[attachments only]"
    print(f"  Processing: {preview[:50]}")

    lock = get_channel_lock(message.channel.id)
    if lock.locked():
        await message.channel.send("Processing your previous message, one moment...")

    async with message.channel.typing():
        async with lock:
            response = await run_agent(
                message.channel.id,
                prompt,
                downloaded_files,
                channel_name=message.channel.name,
                channel_config=channel_config,
            )

    print(f"  Response length: {len(response)}")

    await send_chunked_response(message.channel, response)


async def log_medication_dose(med_name: str, timestamp: str) -> bool:
    """Log medication dose to Medications.md file.

    Args:
        med_name: Name of medication (e.g., "Medrol 5mg", "Vitaplex + Neupro 300 units", "Vitaplex")
        timestamp: ISO timestamp of dose

    Returns:
        bool: True if logged successfully
    """
    try:
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

        # Look up medication config
        med = find_med_by_content(med_name)
        if not med:
            print(f"Unknown medication: {med_name}")
            return False

        table_marker = med["vault_table_marker"]
        entry = (
            med["entry_format"].format(
                date=date_str, day_label=day_of_week, source="Auto-logged via ✅"
            )
            + "\n"
        )

        # Find insertion point (after last table row before next section)
        insert_index = None
        in_correct_section = False
        for i, line in enumerate(lines):
            if line.startswith(table_marker) and not line.startswith(table_marker + "#"):
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
        atomic_write_text(med_file, "".join(lines))

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

    # Only process reactions to bot or webhook messages
    is_bot_message = reaction.message.author == client.user
    is_webhook = reaction.message.webhook_id is not None
    if not (is_bot_message or is_webhook):
        return

    # Check if this is a medication reminder message
    content = reaction.message.content
    if "Medication Reminder" not in content:
        return

    print(f"Checkmark reaction from {user.name} on medication reminder")

    # Parse medication name from message
    med = find_med_by_content(content)
    med_name = med["name"] if med else None

    if not med_name:
        print("Could not parse medication name from reminder")
        return

    # Discord does not expose a per-reaction timestamp here, so record confirmation time.
    timestamp = get_reaction_timestamp()

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

            atomic_write_json(state_file, state)

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
