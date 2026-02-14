#!/usr/bin/env python3
"""
Send a message to Discord channel using bot credentials.
The bot will forward this as if it came from the user, triggering ATLAS response.

Usage:
    python send_message.py "Your message here"
"""

import asyncio
import os
import sys
from pathlib import Path

import discord
from dotenv import load_dotenv

# Load environment
BOT_DIR = Path(__file__).parent
load_dotenv(BOT_DIR / ".env")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))


async def send_message(content: str) -> bool:
    """Send message to Discord channel via bot."""
    intents = discord.Intents.default()
    intents.message_content = True

    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        try:
            channel = client.get_channel(CHANNEL_ID)
            if not channel:
                print(f"Error: Could not find channel {CHANNEL_ID}")
                await client.close()
                return

            await channel.send(content)
            print(f"Message sent to channel {CHANNEL_ID}")
            await client.close()
        except Exception as e:
            print(f"Error sending message: {e}")
            await client.close()

    try:
        await client.start(DISCORD_TOKEN)
        return True
    except Exception as e:
        print(f"Error connecting to Discord: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python send_message.py 'Your message here'")
        sys.exit(1)

    message = " ".join(sys.argv[1:])
    success = asyncio.run(send_message(message))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
