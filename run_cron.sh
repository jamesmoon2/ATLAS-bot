#!/bin/bash
#
# ATLAS Cron Dispatcher Wrapper
# This script is called by cron every minute to check and run scheduled jobs.
#
# Crontab entry:
#   * * * * * ${BOT_DIR}/run_cron.sh
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment variables
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi

# Activate virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# Run dispatcher and log output
python "$SCRIPT_DIR/cron/dispatcher.py" >> "$SCRIPT_DIR/logs/cron/dispatcher.log" 2>&1
