#!/bin/bash
# Archive session and reset for next day
# Runs at 11:59 PM PST via cron (4 minutes after summary request)

set -euo pipefail

export TZ="America/Los_Angeles"

DATE=$(date +%Y-%m-%d)
CHANNEL_ID="${DISCORD_CHANNEL_ID:?DISCORD_CHANNEL_ID not set}"
SESSION_DIR="${BOT_DIR}/sessions/${CHANNEL_ID}"
ARCHIVE_DIR="${SESSION_DIR}/.archive/${DATE}"

echo "=== ATLAS Session Archive: ${DATE} ==="

# 1. Create archive directory
mkdir -p "${ARCHIVE_DIR}"

# 2. Archive current session (.claude directory)
if [ -d "${SESSION_DIR}/.claude" ]; then
    echo "Archiving .claude directory..."
    cp -r "${SESSION_DIR}/.claude" "${ARCHIVE_DIR}/"
else
    echo "No .claude directory found to archive"
fi

# 3. Archive Claude Code project directory
CLAUDE_PROJECT_DIR=$(find ~/.claude/projects/ -path "*sessions-${CHANNEL_ID}*" -type d 2>/dev/null | head -1)
if [ -n "${CLAUDE_PROJECT_DIR}" ] && [ -d "${CLAUDE_PROJECT_DIR}" ]; then
    echo "Archiving Claude project directory..."
    cp -r "${CLAUDE_PROJECT_DIR}" "${ARCHIVE_DIR}/claude-project"
else
    echo "No Claude project directory found to archive"
fi

# 4. Reset session (remove .claude directory - will be recreated on next message)
echo "Resetting session..."
if [ -d "${SESSION_DIR}/.claude" ]; then
    rm -rf "${SESSION_DIR}/.claude"
    echo "Session reset complete"
else
    echo "No .claude directory to reset"
fi

echo "=== Archive complete: ${ARCHIVE_DIR} ==="
echo "=== Session reset for next day ==="
