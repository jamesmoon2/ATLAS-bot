#!/bin/bash
# Tasks Summary Hook - Shows overdue and due-today tasks
# Note: Central task view is at $TASKS_FILE_PATH (1. Tasks.md in vault root)
# This hook searches actual task items in project/daily files

VAULT="${VAULT_PATH:-/home/user/vault}"
TASKS_FILE="${TASKS_FILE_PATH:-$VAULT/1. Tasks.md}"
TODAY=$(date +%Y-%m-%d)

echo "## Tasks"

# Due today
TODAY_TASKS=$(grep -r "📅 $TODAY" "$VAULT" --include="*.md" 2>/dev/null | grep "\- \[ \]" | sed 's/.*- \[ \]/- /' | head -5)
if [ -n "$TODAY_TASKS" ]; then
    echo "**Due Today:**"
    echo "$TODAY_TASKS"
fi

# Overdue - find tasks with dates before today
OVERDUE=$(grep -rP "📅 \d{4}-\d{2}-\d{2}" "$VAULT" --include="*.md" 2>/dev/null | grep "\- \[ \]" | while IFS= read -r line; do
    task_date=$(echo "$line" | grep -oP "📅 \K\d{4}-\d{2}-\d{2}")
    if [[ -n "$task_date" && "$task_date" < "$TODAY" ]]; then
        echo "$line" | sed 's/.*- \[ \]/- /'
    fi
done | head -5)

if [ -n "$OVERDUE" ]; then
    echo "**Overdue:**"
    echo "$OVERDUE"
fi

# If nothing found
if [ -z "$TODAY_TASKS" ] && [ -z "$OVERDUE" ]; then
    echo "No tasks due today or overdue."
fi
