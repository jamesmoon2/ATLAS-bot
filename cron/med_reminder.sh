#!/bin/bash
# Medication Reminder Agent
# Runs at 5 AM and 8 PM daily; checks meds.json for what's due now.

set -euo pipefail

VAULT_PATH="${VAULT_PATH:?VAULT_PATH not set}"
BOT_DIR="${BOT_DIR:?BOT_DIR not set}"
STATE_FILE="${VAULT_PATH}/System/agent-state.json"
CONFIG="${BOT_DIR}/meds.json"

# Current day/hour in PST
export TZ="America/Los_Angeles"
DAY=$(date +%u)  # 1=Mon … 7=Sun
HOUR=$(date +%-H)  # 0-23, no leading zero

# Find matching medication from config
MED_JSON=$(jq --argjson day "$DAY" --argjson hour "$HOUR" \
  '[.medications[] | . as $med | .schedule[] | select(.day == $day and .hour == $hour) | {name: $med.name, location: $med.location, label: .label}] | first // empty' \
  "$CONFIG")

if [ -z "$MED_JSON" ]; then
    echo "NO_ALERT"
    exit 0
fi

MED=$(echo "$MED_JSON" | jq -r '.name')
LABEL=$(echo "$MED_JSON" | jq -r '.label')
LOCATION=$(echo "$MED_JSON" | jq -r '.location // empty')

# Build reminder message
TIMING="this morning"
echo "$LABEL" | grep -q "PM" && TIMING="tonight"

REMINDER="**Medication Reminder**\n\n${MED} due ${TIMING} (${LABEL})"
if [ -n "$LOCATION" ]; then
    REMINDER="${REMINDER}\n\nLocation: ${LOCATION}"
fi
REMINDER="${REMINDER}\n\nReact with ✅ to log dose."

echo -e "$REMINDER"

# Initialize state if needed
if [ ! -f "${STATE_FILE}" ]; then
    echo '{"med_reminders": {}}' > "${STATE_FILE}"
fi

# Update state file with reminder sent
TIMESTAMP=$(date -Iseconds)
jq --arg med "${MED}" \
   --arg timestamp "${TIMESTAMP}" \
   '.med_reminders[$med] = {last_reminder: $timestamp, confirmed: false}' \
   "${STATE_FILE}" > /tmp/agent-state-new.json && mv /tmp/agent-state-new.json "${STATE_FILE}"
