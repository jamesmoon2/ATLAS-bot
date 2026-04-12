#!/bin/bash
# Librarian Context Hook - inject a compact vault snapshot at session start

set -euo pipefail

INDEX_PATH="${VAULT_PATH:?VAULT_PATH not set}/System/vault-index.json"

if [ ! -f "${INDEX_PATH}" ]; then
    echo "## Librarian Snapshot"
    echo "Vault index not available yet."
    exit 0
fi

python3 - "${INDEX_PATH}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


index_path = Path(sys.argv[1])

try:
    data = json.loads(index_path.read_text(encoding="utf-8"))
except Exception:
    print("## Librarian Snapshot")
    print("Vault index is unreadable.")
    raise SystemExit(0)

notes = data.get("notes", [])
recent_notes = sorted(notes, key=lambda note: note.get("last_modified", ""), reverse=True)[:5]
open_loops = [note for note in notes if note.get("status", {}).get("has_open_loops")][:5]
stale_notes = [note for note in notes if note.get("status", {}).get("is_stale")][:5]

print("## Librarian Snapshot")
print("")

print("**Recent Notes**")
if recent_notes:
    for note in recent_notes:
        print(f"- {note['path']}")
else:
    print("- None")

print("")
print("**Open Loops**")
if open_loops:
    for note in open_loops:
        print(f"- {note['path']} ({note.get('task_open_count', 0)} open tasks)")
else:
    print("- None")

print("")
print("**Needs Review**")
if stale_notes:
    now = parse_dt(data.get("generated_at", datetime.now(timezone.utc).isoformat()))
    for note in stale_notes:
        last_modified = parse_dt(note["last_modified"])
        age_days = (now - last_modified).days
        print(f"- {note['path']} ({age_days} days stale)")
else:
    print("- None")
PY
