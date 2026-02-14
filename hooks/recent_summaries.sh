#!/bin/bash
# Inject last 3 days of ATLAS conversation summaries into session context
# Used by .claude/settings.json SessionStart hook

VAULT_DAILY="${VAULT_PATH:?VAULT_PATH not set}/Daily"

# Check if Daily directory exists
if [ ! -d "${VAULT_DAILY}" ]; then
    echo "## Recent Activity"
    echo "No daily summaries found yet."
    exit 0
fi

# Find last 3 ATLAS summary files (sorted by date, newest first)
SUMMARIES=$(find "${VAULT_DAILY}" -name "*-atlas-summary.md" -type f 2>/dev/null | sort -r | head -3)

if [ -z "${SUMMARIES}" ]; then
    echo "## Recent Activity"
    echo "No recent summaries available."
    exit 0
fi

echo "## Recent Activity (Last 3 Days)"
echo ""

# Output each summary with date header
while IFS= read -r file; do
    # Extract date from filename (YYYY-MM-DD-atlas-summary.md)
    filename=$(basename "$file")
    date="${filename%-atlas-summary.md}"

    echo "### ${date}"
    cat "$file"
    echo ""
done <<< "${SUMMARIES}"
