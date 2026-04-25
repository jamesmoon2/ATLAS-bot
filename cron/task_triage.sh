#!/bin/bash
# Retired: project/task triage now belongs in cron/jobs.json via cron/dispatcher.py.

set -euo pipefail

echo "cron/task_triage.sh is retired."
echo "Use cron/jobs.json prompt jobs routed through cron/dispatcher.py."
exit 1
