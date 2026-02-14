#!/bin/bash
# Medication Reminder Agent
# Runs 4x/week at scheduled dose times

set -euo pipefail

STATE_FILE="${VAULT_PATH}/System/agent-state.json"
MED_LOG="${VAULT_PATH}/Areas/Health/Medications.md"

# Determine which medication is due based on day/time (PST)
export TZ="America/Los_Angeles"
DAY=$(date +%u)  # 1=Mon, 3=Wed, 4=Thu, 6=Sat
HOUR=$(date +%H)

# Initialize state if needed
if [ ! -f "${STATE_FILE}" ]; then
    echo '{"med_reminders": {}}' > "${STATE_FILE}"
fi

# Determine medication and dose
if [ "$DAY" -eq 3 ] && [ "$HOUR" -eq 5 ]; then
    MED="Medrol 5mg"
    REMINDER="**Medication Reminder**\n\nMedrol 5mg due this morning (Wed AM)\n\nLocation: Fridge\n\nReact with ✅ to log dose."
elif [ "$DAY" -eq 6 ] && [ "$HOUR" -eq 20 ]; then
    MED="Medrol 5mg"
    REMINDER="**Medication Reminder**\n\nMedrol 5mg due tonight (Sat PM)\n\nLocation: Fridge\n\nReact with ✅ to log dose."
elif [ "$DAY" -eq 1 ] && [ "$HOUR" -eq 5 ]; then
    MED="Vitaplex + Neupro 300 units"
    REMINDER="**Medication Reminder**\n\nVitaplex + Neupro 300 units due this morning (Mon AM)\n\nLocation: [Location TBD]\n\nReact with ✅ to log dose."
elif [ "$DAY" -eq 4 ] && [ "$HOUR" -eq 20 ]; then
    MED="Vitaplex"
    REMINDER="**Medication Reminder**\n\nVitaplex due tonight (Thu PM)\n\nLocation: [Location TBD]\n\nReact with ✅ to log dose."
else
    echo "No medication reminder scheduled for this time"
    exit 0
fi

echo "=== Medication Reminder: ${MED} at $(date) ==="

# Send to Discord (if webhook configured)
if [ -n "${DISCORD_WEBHOOK_URL:-}" ]; then
    curl -X POST "${DISCORD_WEBHOOK_URL}" \
        -H "Content-Type: application/json" \
        -d "{\"username\": \"ATLAS Medication\", \"content\": \"${REMINDER}\"}" \
        2>/dev/null || echo "Discord notification failed"
    echo "Reminder sent to Discord"
else
    echo "DISCORD_WEBHOOK_URL not set, skipping notification"
fi

# Update state file with reminder sent
TIMESTAMP=$(date -Iseconds)
jq --arg med "${MED}" \
   --arg timestamp "${TIMESTAMP}" \
   '.med_reminders[$med] = {last_reminder: $timestamp, confirmed: false}' \
   "${STATE_FILE}" > /tmp/agent-state-new.json && mv /tmp/agent-state-new.json "${STATE_FILE}"

echo "=== Medication reminder complete ==="

# Note: Auto-logging from ✅ reaction requires webhook handler in bot.py
# This script only sends the reminder
