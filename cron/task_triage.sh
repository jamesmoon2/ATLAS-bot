#!/bin/bash
# Task Triage Agent - Daily 9:00 PM PST
# Flags overdue tasks, blockers, and quick wins

set -euo pipefail

export TZ="America/Los_Angeles"

CHANNEL_ID="${DISCORD_CHANNEL_ID:?DISCORD_CHANNEL_ID not set}"
BOT_DIR="${BOT_DIR:?BOT_DIR not set}"
VAULT_PATH="${VAULT_PATH:?VAULT_PATH not set}"
SESSION_DIR="${BOT_DIR}/sessions/${CHANNEL_ID}"
STATE_FILE="${VAULT_PATH}/System/agent-state.json"

echo "=== Task Triage Agent: $(date) ==="

# Ensure state file exists
if [ ! -f "${STATE_FILE}" ]; then
    echo '{"task_triage": {"last_run": null, "flagged_tasks": []}}' > "${STATE_FILE}"
fi

# Use Claude Code to analyze tasks
cd "${SESSION_DIR}"

TRIAGE_PROMPT="Analyze the task list and generate a triage report.

## Instructions

1. Read ${VAULT_PATH}/1. Tasks.md
2. Parse all tasks with due dates
3. Categorize:
   - **Overdue >3 days:** Tasks due 3+ days ago
   - **Blockers:** Tasks with dependencies or waiting states
   - **Quick wins:** Tasks <15 min effort
   - **Stalled:** No progress indicators, long-standing

4. Output format:

---
**Task Triage Report — $(date +%Y-%m-%d)**

**Overdue (>3 days):**
- [ ] Task description (due YYYY-MM-DD) — X days overdue
  → Notes: [Any blocking context]

**Blockers:**
- [ ] Task description — Waiting on: [dependency]

**Quick Wins (<15 min):**
- [ ] Task 1
- [ ] Task 2

**Stalled (no recent progress):**
- [ ] Task description (due YYYY-MM-DD) — Last activity: [estimate]
  → Recommendation: [defer/delete/batch]

**Summary:** X overdue, Y blocked, Z quick wins available

---

If no tasks flagged in any category, output:
\"Task Triage Report — $(date +%Y-%m-%d)

All tasks current. No overdue items, blockers, or quick wins flagged.\"

Be concise. Only include sections with content."

# Run Claude Code with timeout
timeout 180s claude --output-format json -p "${TRIAGE_PROMPT}" > /tmp/task_triage_$(date +%Y%m%d).json 2>&1 || {
    echo "Error: Task triage failed or timed out"
    exit 1
}

# Extract result from JSON
REPORT=$(jq -r '.result' /tmp/task_triage_$(date +%Y%m%d).json 2>/dev/null || echo "Failed to parse report")

# Output to console
echo "${REPORT}"

# Send to Discord (if webhook configured)
if [ -n "${DISCORD_WEBHOOK_URL:-}" ]; then
    curl -X POST "${DISCORD_WEBHOOK_URL}" \
        -H "Content-Type: application/json" \
        -d "{\"username\": \"ATLAS Task Triage\", \"content\": $(echo "${REPORT}" | jq -Rs .)}" \
        2>/dev/null || echo "Discord notification failed"
fi

# Update state file
jq --arg timestamp "$(date -Iseconds)" \
   '.task_triage.last_run = $timestamp' \
   "${STATE_FILE}" > /tmp/agent-state-new.json && mv /tmp/agent-state-new.json "${STATE_FILE}"

echo "=== Task triage complete ==="
