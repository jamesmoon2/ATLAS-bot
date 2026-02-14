#!/bin/bash
# Daily summary request for ATLAS bot
# Runs at 11:55 PM PST via cron
# Sends summary request to ATLAS, who generates it before archive at 11:59

set -euo pipefail

export TZ="America/Los_Angeles"

DATE=$(date +%Y-%m-%d)
VAULT_PATH="${VAULT_PATH:?VAULT_PATH not set}"
BOT_DIR="${BOT_DIR:?BOT_DIR not set}"
VAULT_DAILY="${VAULT_PATH}/Daily"

echo "=== ATLAS Daily Summary Request: ${DATE} ==="

# Send summary request to ATLAS via Discord
echo "Sending summary request to ATLAS..."

SUMMARY_PROMPT="Review today's conversation history (${DATE}) and create a structured summary. Write it to ${VAULT_DAILY}/${DATE}-atlas-summary.md with these sections:

## Tasks Created
List any new tasks mentioned or created today.

## Decisions
Key decisions made (reference Decision-Log.md format if decisions were logged).

## Files Modified
List files that were created or significantly modified.

## Conversations
Brief bullet points of main topics discussed (2-4 bullets max).

## Unresolved
Any threads left incomplete or questions pending.

Be concise. Use bullet points. Skip sections if nothing to report."

# Send via Discord bot (ATLAS will respond and write summary)
cd "${BOT_DIR}"
python3 send_message.py "${SUMMARY_PROMPT}"

echo "=== Summary request sent to ATLAS at 23:55 PST ==="
echo "=== Archive and reset will run at 23:59 PST ==="
