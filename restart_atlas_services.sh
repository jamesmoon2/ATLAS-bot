#!/bin/bash
#
# Restart the ATLAS bot service and the cron daemon with one command.
#

set -euo pipefail

BOT_SERVICE="${ATLAS_BOT_SERVICE:-atlas-bot.service}"
CRON_SERVICE="${ATLAS_CRON_SERVICE:-cron.service}"
SYSTEMCTL_BIN="${SYSTEMCTL_BIN:-systemctl}"

if ! command -v "${SYSTEMCTL_BIN}" >/dev/null 2>&1; then
    echo "systemctl not found: ${SYSTEMCTL_BIN}" >&2
    exit 1
fi

run_systemctl() {
    if [ "$(id -u)" -eq 0 ]; then
        "${SYSTEMCTL_BIN}" "$@"
        return
    fi

    if sudo -n true >/dev/null 2>&1; then
        sudo "${SYSTEMCTL_BIN}" "$@"
        return
    fi

    sudo "${SYSTEMCTL_BIN}" "$@"
}

print_service_status() {
    local service="$1"
    local active_state sub_state active_since

    active_state="$(run_systemctl show "${service}" -p ActiveState --value)"
    sub_state="$(run_systemctl show "${service}" -p SubState --value)"
    active_since="$(run_systemctl show "${service}" -p ActiveEnterTimestamp --value)"

    printf "%s: %s/%s" "${service}" "${active_state}" "${sub_state}"
    if [ -n "${active_since}" ]; then
        printf " (since %s)" "${active_since}"
    fi
    printf "\n"
}

echo "Restarting ${BOT_SERVICE}..."
run_systemctl restart "${BOT_SERVICE}"

echo "Restarting ${CRON_SERVICE}..."
run_systemctl restart "${CRON_SERVICE}"

echo
print_service_status "${BOT_SERVICE}"
print_service_status "${CRON_SERVICE}"
