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

# Find last 3 daily note files (YYYY-MM-DD.md format, sorted by date, newest first)
# Exclude weekly reviews (YYYY-W##-*.md)
SUMMARIES=$(find "${VAULT_DAILY}" -maxdepth 1 -name "202[0-9]-[0-1][0-9]-[0-3][0-9].md" -type f 2>/dev/null | sort -r | head -3)

if [ -z "${SUMMARIES}" ]; then
    echo "## Recent Activity"
    echo "No recent summaries available."
    exit 0
fi

echo "## Recent Activity (Last 3 Days)"
echo ""

# Output each summary with date header
while IFS= read -r file; do
    # Extract date from filename (YYYY-MM-DD.md)
    filename=$(basename "$file")
    date="${filename%.md}"

    echo "### ${date}"
    cat "$file"
    echo ""
done <<< "${SUMMARIES}"
