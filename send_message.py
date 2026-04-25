#!/usr/bin/env python3
"""
Send a message to Discord channel using bot credentials.
The bot will forward this as if it came from the user, triggering ATLAS response.

Usage:
    python send_message.py "Your message here"
    python send_message.py --channel health "Your message here"
    python send_message.py --channel-id 123456789 "Your message here"
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

import discord
from dotenv import load_dotenv

from channel_configs import get_channel_config_by_key, normalize_channel_key

# Load environment
BOT_DIR = Path(__file__).parent
load_dotenv(BOT_DIR / ".env")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))


def _env_channel_id_for_name(channel_name: str) -> int:
    config = get_channel_config_by_key(channel_name, honor_allowlist=False)
    if config is None or config.channel_id_env is None:
        return 0
    try:
        return int(os.getenv(config.channel_id_env, "0"))
    except ValueError:
        return 0


def _find_channel_by_name(client, channel_name: str):
    target_name = normalize_channel_key(channel_name)
    matches = []
    for guild in getattr(client, "guilds", []):
        for channel in getattr(guild, "text_channels", []):
            if normalize_channel_key(getattr(channel, "name", "")) == target_name:
                matches.append(channel)

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Error: Multiple channels named #{target_name}; use --channel-id")
    else:
        print(f"Error: Could not find channel named #{target_name}")
    return None


async def send_message(
    content: str,
    *,
    channel_id: int | None = None,
    channel_name: str | None = None,
) -> bool:
    """Send message to Discord channel via bot."""
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN is not configured")
        return False

    if channel_id is not None:
        target_channel_id = channel_id
    elif channel_name:
        target_channel_id = _env_channel_id_for_name(channel_name)
    else:
        target_channel_id = CHANNEL_ID

    if target_channel_id <= 0 and not channel_name:
        print(
            "Error: channel is not configured; use --channel, --channel-id, or DISCORD_CHANNEL_ID"
        )
        return False

    intents = discord.Intents.default()
    intents.message_content = True

    client = discord.Client(intents=intents)
    sent = False

    @client.event
    async def on_ready():
        nonlocal sent
        try:
            channel = client.get_channel(target_channel_id) if target_channel_id > 0 else None
            if not channel and channel_name:
                channel = _find_channel_by_name(client, channel_name)
            if not channel:
                target = channel_name or str(target_channel_id)
                print(f"Error: Could not find channel {target}")
                return

            await channel.send(content)
            sent = True
            print(f"Message sent to channel {getattr(channel, 'id', target_channel_id)}")
        except Exception as e:
            print(f"Error sending message: {e}")
        finally:
            await client.close()

    try:
        await client.start(DISCORD_TOKEN)
        return sent
    except Exception as e:
        print(f"Error connecting to Discord: {e}")
        return False


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a message to a Discord channel.")
    parser.add_argument("--channel", help="Configured channel key or Discord channel name")
    parser.add_argument("--channel-id", type=int, help="Discord channel ID")
    parser.add_argument("message", nargs="+", help="Message text to send")
    return parser.parse_args(argv)


def main():
    if len(sys.argv) < 2:
        print("Usage: python send_message.py [--channel NAME|--channel-id ID] 'Your message here'")
        sys.exit(1)

    args = _parse_args(sys.argv[1:])
    message = " ".join(args.message)
    success = asyncio.run(
        send_message(
            message,
            channel_id=args.channel_id,
            channel_name=args.channel,
        )
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
