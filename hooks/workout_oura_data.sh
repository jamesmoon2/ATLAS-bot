#!/bin/bash
# Hook: Fetch Oura + WHOOP data and prompt Training-State update
# Triggered on Write tool for files matching Workout-Logs pattern

set -euo pipefail

# Get the file path from the agent tool-use context
FILE_PATH="$1"

# Only run if this is a workout log file
if [[ ! "$FILE_PATH" =~ Workout-Logs/[0-9]{4}-[0-9]{2}-[0-9]{2}\.md$ ]]; then
    exit 0
fi

# Extract date from filename (YYYY-MM-DD)
DATE=$(basename "$FILE_PATH" .md)

echo "📊 Post-workout checklist for $DATE:"
echo ""
echo "1. **Fetch Oura + WHOOP data** (append to workout log):"
echo "   - Sleep score (get_daily_sleep for $DATE)"
echo "   - Readiness score (get_daily_readiness for $DATE)"
echo "   - Activity score (get_daily_activity for $DATE)"
echo "   - NOTE: Oura API returns CONTRIBUTOR SCORES (0-100), not raw biometrics"
echo "   - Label as: 'HRV Balance: XX/100' and 'RHR: XX/100' (not actual BPM/ms)"
echo "   - WHOOP sleep (get_daily_sleep for $DATE)"
echo "   - WHOOP recovery (get_daily_recovery for $DATE)"
echo "   - WHOOP cycle/strain (get_daily_cycle for $DATE)"
echo "   - Label WHOOP metrics by their native names: Sleep Performance, Recovery, Strain"
echo ""
echo "2. **Update Training-State.md:**"
echo "   - Update today's entry in the 'This Week' status section"
echo "   - Update Progress Markers (if lifts progressed)"
echo "   - Update Fatigue Indicators (RPE, recovery time, notes)"
echo "   - Add to Adjustments Queue (what to change next session)"
echo "   - Update Last Week section if week rolled over"
echo ""
echo "3. **Update Daily Note** (optional):"
echo "   - Add workout note or link: [[Workout-Logs/$DATE|Workout]]"
echo "   - Add 1-2 bullet key takeaways"
