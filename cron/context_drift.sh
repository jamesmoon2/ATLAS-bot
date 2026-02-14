#!/bin/bash
# Context Drift Detector - Weekly Sunday 8:00 AM PST
# Compares Decision-Log decisions to actual execution

set -euo pipefail

export TZ="America/Los_Angeles"

CHANNEL_ID="${DISCORD_CHANNEL_ID:?DISCORD_CHANNEL_ID not set}"
SESSION_DIR="${BOT_DIR}/sessions/${CHANNEL_ID}"
STATE_FILE="${VAULT_PATH}/System/agent-state.json"
DECISION_LOG="${VAULT_PATH}/Areas/Decision-Log.md"

echo "=== Context Drift Detector: $(date) ==="

# Ensure state file exists
if [ ! -f "${STATE_FILE}" ]; then
    echo '{"context_drift": {"last_run": null}}' > "${STATE_FILE}"
fi

# Use Claude Code to analyze drift
cd "${SESSION_DIR}"

DRIFT_PROMPT="Analyze context drift between stated decisions and actual execution.

## Instructions

1. Read ${DECISION_LOG}
2. Read recent daily summaries from ${VAULT_PATH}/Daily/ (last 7 days)
3. Read Training-State.md, active project files, task lists

4. Identify mismatches:
   - Decisions stating intent vs actual behavior
   - Goals set vs progress made
   - Plans declared vs execution reality
   - Only flag patterns >7 days (ignore short-term variance)

5. Output format:

---
**Context Drift Check — Week of $(date +%Y-%m-%d)**

**Decision vs Execution Mismatches:**

**Decision (YYYY-MM-DD):** \"[What was decided]\"
**Reality:** [What actually happened or didn't happen]
**Duration:** X days
→ **Action:** [Recommendation: update decision, adjust execution, or acknowledge drift]

---

**Alignment Check:**
- [X] decisions with execution matching intent
- [Y] decisions flagged for drift

---

If no drift detected, output:
\"Context Drift Check — Week of $(date +%Y-%m-%d)

All recent decisions align with execution. No drift detected.\"

Be precise. Only flag meaningful patterns, not day-to-day variance."

# Run Claude Code with timeout
timeout 240s claude --output-format json -p "${DRIFT_PROMPT}" > /tmp/context_drift_$(date +%Y%m%d).json 2>&1 || {
    echo "Error: Context drift analysis failed or timed out"
    exit 1
}

# Extract result from JSON
REPORT=$(jq -r '.result' /tmp/context_drift_$(date +%Y%m%d).json 2>/dev/null || echo "Failed to parse report")

# Output to console
echo "${REPORT}"

# Send to Discord (if webhook configured)
if [ -n "${DISCORD_WEBHOOK_URL:-}" ]; then
    curl -X POST "${DISCORD_WEBHOOK_URL}" \
        -H "Content-Type: application/json" \
        -d "{\"username\": \"ATLAS Context Drift\", \"content\": $(echo "${REPORT}" | jq -Rs .)}" \
        2>/dev/null || echo "Discord notification failed"
fi

# Update state file
jq --arg timestamp "$(date -Iseconds)" \
   '.context_drift.last_run = $timestamp' \
   "${STATE_FILE}" > /tmp/agent-state-new.json && mv /tmp/agent-state-new.json "${STATE_FILE}"

echo "=== Context drift check complete ==="
