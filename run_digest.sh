#!/bin/bash
# Wrapper script for cron - loads environment and runs digest
# Usage: Set BOT_DIR environment variable or run from bot directory

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_DIR="${BOT_DIR:-$SCRIPT_DIR}"

cd "$BOT_DIR"
source "$BOT_DIR/.env" 2>/dev/null
export DISCORD_WEBHOOK_URL
export VAULT_PATH

# Activate venv and run
source "$BOT_DIR/venv/bin/activate"
python "$BOT_DIR/daily_digest.py" >> "$BOT_DIR/digest.log" 2>&1
