#!/bin/bash
# Calendar Context Hook - Injects clear date/time before calendar operations
# Prevents day-of-week confusion when scheduling events

export TZ='America/Los_Angeles'

echo "## Calendar Date Reference (Pacific Time)"
echo ""
echo "**Current time:** $(date '+%H:%M %Z on %A, %B %d, %Y')"
echo ""
echo "Use these exact ISO dates for calendar API calls:"
echo ""
echo "| Day | Date | ISO (for API) |"
echo "|-----|------|---------------|"
echo "| Today | $(date '+%A, %b %d') | \`$(date '+%Y-%m-%d')\` |"
echo "| Tomorrow | $(date -d '+1 day' '+%A, %b %d') | \`$(date -d '+1 day' '+%Y-%m-%d')\` |"
echo "| $(date -d '+2 days' '+%A') | $(date -d '+2 days' '+%A, %b %d') | \`$(date -d '+2 days' '+%Y-%m-%d')\` |"
echo "| $(date -d '+3 days' '+%A') | $(date -d '+3 days' '+%A, %b %d') | \`$(date -d '+3 days' '+%Y-%m-%d')\` |"
echo "| $(date -d '+4 days' '+%A') | $(date -d '+4 days' '+%A, %b %d') | \`$(date -d '+4 days' '+%Y-%m-%d')\` |"
echo "| $(date -d '+5 days' '+%A') | $(date -d '+5 days' '+%A, %b %d') | \`$(date -d '+5 days' '+%Y-%m-%d')\` |"
echo "| $(date -d '+6 days' '+%A') | $(date -d '+6 days' '+%A, %b %d') | \`$(date -d '+6 days' '+%Y-%m-%d')\` |"
echo ""
echo "**IMPORTANT:** Always use timeZone: \"America/Los_Angeles\" in calendar API calls."
