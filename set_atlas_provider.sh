#!/bin/bash
#
# Switch the ATLAS agent provider in .env and optionally restart services.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ATLAS_ENV_FILE:-${SCRIPT_DIR}/.env}"
RESTART_SCRIPT="${ATLAS_RESTART_SCRIPT:-${SCRIPT_DIR}/restart_atlas_services.sh}"

DEFAULT_CLAUDE_MODEL="${ATLAS_DEFAULT_CLAUDE_MODEL:-opus}"
DEFAULT_CODEX_MODEL="${ATLAS_DEFAULT_CODEX_MODEL:-gpt-5.4}"
DEFAULT_CODEX_REASONING="${ATLAS_DEFAULT_CODEX_REASONING:-xhigh}"

usage() {
    cat <<'EOF'
Usage:
  set_atlas_provider.sh <claude|codex> [--no-restart]

Examples:
  set_atlas_provider.sh codex
  set_atlas_provider.sh claude --no-restart

Behavior:
  - updates ATLAS_AGENT_PROVIDER in .env
  - preserves existing provider-specific defaults if already set
  - adds sensible defaults when missing
  - restarts ATLAS services unless --no-restart is supplied
EOF
}

replace_or_append() {
    local file="$1"
    local key="$2"
    local value="$3"
    local tmp_file

    tmp_file="$(mktemp)"
    awk -v key="$key" -v value="$value" '
        BEGIN { updated = 0 }
        index($0, key "=") == 1 && updated == 0 {
            print key "=" value
            updated = 1
            next
        }
        { print }
        END {
            if (updated == 0) {
                print key "=" value
            }
        }
    ' "$file" > "$tmp_file"
    mv "$tmp_file" "$file"
}

ensure_setting() {
    local file="$1"
    local key="$2"
    local value="$3"

    if ! grep -q "^${key}=" "$file"; then
        replace_or_append "$file" "$key" "$value"
    fi
}

provider=""
restart_services=true

for arg in "$@"; do
    case "$arg" in
        claude|codex)
            provider="$arg"
            ;;
        --no-restart)
            restart_services=false
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [ -z "$provider" ]; then
    usage >&2
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "Env file not found: $ENV_FILE" >&2
    exit 1
fi

replace_or_append "$ENV_FILE" "ATLAS_AGENT_PROVIDER" "$provider"
ensure_setting "$ENV_FILE" "ATLAS_CLAUDE_MODEL" "$DEFAULT_CLAUDE_MODEL"
ensure_setting "$ENV_FILE" "ATLAS_CODEX_MODEL" "$DEFAULT_CODEX_MODEL"
ensure_setting "$ENV_FILE" "ATLAS_CODEX_REASONING_EFFORT" "$DEFAULT_CODEX_REASONING"

echo "ATLAS provider set to: $provider"
echo "Env file updated: $ENV_FILE"

if [ "$restart_services" = true ]; then
    if [ ! -x "$RESTART_SCRIPT" ]; then
        echo "Restart script is missing or not executable: $RESTART_SCRIPT" >&2
        exit 1
    fi

    echo
    "$RESTART_SCRIPT"
else
    echo
    echo "Restart skipped. Run ${RESTART_SCRIPT} when you're ready."
fi
