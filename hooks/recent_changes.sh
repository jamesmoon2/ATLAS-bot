#!/bin/bash
# Recent Changes Hook - Shows recently modified vault files

VAULT="${VAULT_PATH:-/home/user/vault}"

echo "## Recent Changes (24h)"
find "$VAULT" -name "*.md" -mtime -1 -type f 2>/dev/null | \
    grep -v ".obsidian" | \
    grep -v "Apple Notes" | \
    sed "s|$VAULT/||" | \
    head -10

# If nothing found
if [ $(find "$VAULT" -name "*.md" -mtime -1 -type f 2>/dev/null | grep -v ".obsidian" | grep -v "Apple Notes" | wc -l) -eq 0 ]; then
    echo "No changes in last 24 hours."
fi
