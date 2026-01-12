#!/bin/bash
# Calendar Context Hook - Injects clear date/time before calendar operations
# Prevents day-of-week confusion when scheduling events

export TZ='America/Los_Angeles'

echo "## Date Reference"
echo "- **Today:** $(date '+%A, %B %d, %Y')"
echo "- **Tomorrow (T+1):** $(date -d '+1 day' '+%A, %B %d, %Y')"
echo "- **T+2:** $(date -d '+2 days' '+%A, %B %d, %Y')"
echo "- **T+3:** $(date -d '+3 days' '+%A, %B %d, %Y')"
echo "- **T+7 (next week):** $(date -d '+7 days' '+%A, %B %d, %Y')"
echo "- **Current time:** $(date '+%H:%M %Z')"
