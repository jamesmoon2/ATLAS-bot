#!/bin/bash
# Retired: context drift now runs through cron/jobs.json via cron/dispatcher.py.

set -euo pipefail

echo "cron/context_drift.sh is retired."
echo "Use: python3 cron/dispatcher.py --run-now context_drift"
exit 1
