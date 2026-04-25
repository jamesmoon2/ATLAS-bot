#!/bin/bash
# Archive session and reset for next day
# Runs at 11:59 PM PST via cron (4 minutes after summary request)

set -euo pipefail

export TZ="America/Los_Angeles"

DATE=$(date +%Y-%m-%d)
BOT_DIR="${BOT_DIR:?BOT_DIR not set}"
SESSIONS_ROOT="${BOT_DIR}/sessions"

echo "=== ATLAS Session Archive: ${DATE} ==="

archive_session() {
    local session_dir="$1"
    local channel_id
    local archive_dir
    local provider_private_dir
    local claude_projects_root
    local claude_project_dir

    channel_id=$(basename "${session_dir}")
    archive_dir="${session_dir}/.archive/${DATE}"
    provider_private_dir="${archive_dir}/provider-private"

    echo "--- Archiving session ${channel_id} ---"

    # 1. Create archive directory
    mkdir -p "${archive_dir}"
    mkdir -p "${provider_private_dir}"

    # 2. Archive current session harness config/state
    if [ -d "${session_dir}/.claude" ]; then
        echo "Archiving .claude directory for ${channel_id}..."
        # Preserve symlinks like `.claude/skills` instead of recursively copying their targets.
        cp -a "${session_dir}/.claude" "${archive_dir}/"
    else
        echo "No .claude directory found for ${channel_id}"
    fi

    # 2b. Archive ATLAS-managed session helper files if present
    for helper in \
        AGENTS.md \
        ATLAS-Calendar-Context.md \
        ATLAS-Channel-Role.md \
        ATLAS-Garmin-Workout-Helper.md \
        ATLAS-Workout-Postwrite.md \
        ATLAS-Session.json \
        .atlas-codex-session-started; do
        if [ -e "${session_dir}/${helper}" ]; then
            cp -a "${session_dir}/${helper}" "${archive_dir}/"
        fi
    done

    # 3. Archive provider-private persisted session state if present
    claude_projects_root="${HOME}/.claude/projects"
    claude_project_dir=""
    if [ -d "${claude_projects_root}" ]; then
        claude_project_dir=$(
            find "${claude_projects_root}" -path "*sessions-${channel_id}*" -type d -print -quit 2>/dev/null || true
        )
    fi
    if [ -n "${claude_project_dir}" ] && [ -d "${claude_project_dir}" ]; then
        echo "Archiving Claude project directory for ${channel_id}..."
        cp -a "${claude_project_dir}" "${provider_private_dir}/claude-project"
    else
        echo "No Claude project directory found for ${channel_id}"
    fi

    # 4. Reset session harness config (will be recreated on next message)
    echo "Resetting session ${channel_id}..."
    if [ -d "${session_dir}/.claude" ]; then
        rm -rf "${session_dir}/.claude"
        echo "Session ${channel_id} reset complete"
    else
        echo "No .claude directory to reset for ${channel_id}"
    fi

    # 5. Reset Codex session helper files
    rm -f \
        "${session_dir}/AGENTS.md" \
        "${session_dir}/ATLAS-Calendar-Context.md" \
        "${session_dir}/ATLAS-Channel-Role.md" \
        "${session_dir}/ATLAS-Garmin-Workout-Helper.md" \
        "${session_dir}/ATLAS-Workout-Postwrite.md" \
        "${session_dir}/ATLAS-Session.json" \
        "${session_dir}/.atlas-codex-session-started"

    echo "--- Archive complete: ${archive_dir} ---"
}

if [ ! -d "${SESSIONS_ROOT}" ]; then
    echo "No sessions directory found: ${SESSIONS_ROOT}"
    exit 0
fi

found=0
for session_dir in "${SESSIONS_ROOT}"/*/; do
    [ -d "${session_dir}" ] || continue
    if [ -d "${session_dir}/.claude" ]; then
        found=1
        archive_session "${session_dir%/}"
    fi
done

if [ "${found}" -eq 0 ]; then
    echo "No active session directories found to archive"
fi

echo "=== Session archive sweep complete ==="
