#!/bin/bash
# Archive session and reset for next day
# Runs at 11:59 PM PST via cron (4 minutes after summary request)

set -euo pipefail

export TZ="America/Los_Angeles"

DATE=$(date +%Y-%m-%d)
CHANNEL_ID="${DISCORD_CHANNEL_ID:?DISCORD_CHANNEL_ID not set}"
BOT_DIR="${BOT_DIR:?BOT_DIR not set}"
SESSION_DIR="${BOT_DIR}/sessions/${CHANNEL_ID}"
ARCHIVE_DIR="${SESSION_DIR}/.archive/${DATE}"

echo "=== ATLAS Session Archive: ${DATE} ==="

# 1. Create archive directory
mkdir -p "${ARCHIVE_DIR}"

# 2. Archive current session harness config/state (.claude directory)
if [ -d "${SESSION_DIR}/.claude" ]; then
    echo "Archiving .claude directory..."
    cp -r "${SESSION_DIR}/.claude" "${ARCHIVE_DIR}/"
else
    echo "No .claude directory found to archive"
fi

# 2b. Archive Codex session helper files if present
for helper in AGENTS.md ATLAS-Calendar-Context.md ATLAS-Workout-Postwrite.md .atlas-codex-session-started; do
    if [ -e "${SESSION_DIR}/${helper}" ]; then
        cp -r "${SESSION_DIR}/${helper}" "${ARCHIVE_DIR}/"
    fi
done

# 3. Archive Claude-specific persisted session state if present
CLAUDE_PROJECTS_ROOT="${HOME}/.claude/projects"
CLAUDE_PROJECT_DIR=""
if [ -d "${CLAUDE_PROJECTS_ROOT}" ]; then
    CLAUDE_PROJECT_DIR=$(
        find "${CLAUDE_PROJECTS_ROOT}" -path "*sessions-${CHANNEL_ID}*" -type d -print -quit 2>/dev/null || true
    )
fi
if [ -n "${CLAUDE_PROJECT_DIR}" ] && [ -d "${CLAUDE_PROJECT_DIR}" ]; then
    echo "Archiving Claude project directory..."
    cp -r "${CLAUDE_PROJECT_DIR}" "${ARCHIVE_DIR}/claude-project"
else
    echo "No Claude project directory found to archive"
fi

# 4. Reset session harness config (will be recreated on next message)
echo "Resetting session..."
if [ -d "${SESSION_DIR}/.claude" ]; then
    rm -rf "${SESSION_DIR}/.claude"
    echo "Session reset complete"
else
    echo "No .claude directory to reset"
fi

# 5. Reset Codex session helper files
rm -f "${SESSION_DIR}/AGENTS.md" \
    "${SESSION_DIR}/ATLAS-Calendar-Context.md" \
    "${SESSION_DIR}/ATLAS-Workout-Postwrite.md" \
    "${SESSION_DIR}/.atlas-codex-session-started"

echo "=== Archive complete: ${ARCHIVE_DIR} ==="
echo "=== Session reset for next day ==="
