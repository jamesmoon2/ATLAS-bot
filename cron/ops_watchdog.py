#!/usr/bin/env python3
"""Silent-unless-needed ATLAS process and cron hygiene watchdog."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parents[1]
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from atlas_diagnostics import build_diagnostics_snapshot, format_watchdog_report  # noqa: E402

STATE_FILE = BOT_DIR / "cron" / "state" / "ops_watchdog.json"
DEFAULT_REPEAT_SECONDS = 6 * 60 * 60


def _orphan_min_seconds() -> int:
    raw_value = os.getenv("ATLAS_OPS_WATCHDOG_ORPHAN_MIN_SECONDS", "").strip()
    if not raw_value:
        return 60 * 60
    try:
        return max(0, int(raw_value))
    except ValueError:
        return 60 * 60


def _repeat_seconds() -> int:
    raw_value = os.getenv("ATLAS_OPS_WATCHDOG_REPEAT_SECONDS", "").strip()
    if not raw_value:
        return DEFAULT_REPEAT_SECONDS
    try:
        return max(0, int(raw_value))
    except ValueError:
        return DEFAULT_REPEAT_SECONDS


def _snapshot_fingerprint(snapshot) -> str:
    disabled_jobs = sorted(job.job_id for job in snapshot.cron_jobs if job.disabled_after_failures)
    failed_jobs = sorted(job.job_id for job in snapshot.cron_jobs if job.failures > 0)
    orphan_pids = sorted(process.pid for process in snapshot.orphan_mcp_helpers)
    bot_pids = sorted(process.pid for process in snapshot.bot_processes)
    warning_text = sorted(snapshot.warnings)
    return "|".join(
        [
            f"warnings={warning_text}",
            f"bots={bot_pids}",
            f"orphans={orphan_pids}",
            f"failed_jobs={failed_jobs}",
            f"disabled_jobs={disabled_jobs}",
        ]
    )


def _read_state(state_file: Path) -> dict:
    if not state_file.exists():
        return {}
    try:
        import json

        return json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_state(state_file: Path, *, fingerprint: str, now: float) -> None:
    import json

    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps({"fingerprint": fingerprint, "last_alert": now}, indent=2) + "\n",
        encoding="utf-8",
    )


def render_watchdog_output(
    snapshot,
    *,
    state_file: Path = STATE_FILE,
    now: float | None = None,
    repeat_seconds: int | None = None,
) -> str:
    report = format_watchdog_report(snapshot)
    if report == "NO_ALERT":
        try:
            state_file.unlink(missing_ok=True)
        except OSError:
            pass
        return report

    current_time = time.time() if now is None else now
    repeat_window = _repeat_seconds() if repeat_seconds is None else repeat_seconds
    fingerprint = _snapshot_fingerprint(snapshot)
    previous_state = _read_state(state_file)
    previous_alert = float(previous_state.get("last_alert", 0) or 0)
    if (
        previous_state.get("fingerprint") == fingerprint
        and current_time - previous_alert < repeat_window
    ):
        return "NO_ALERT"

    try:
        _write_state(state_file, fingerprint=fingerprint, now=current_time)
    except OSError:
        pass
    return report


def main() -> int:
    try:
        snapshot = build_diagnostics_snapshot(orphan_min_seconds=_orphan_min_seconds())
        print(render_watchdog_output(snapshot))
        return 0
    except Exception as exc:
        print(f"**ATLAS Ops Watchdog: FAILED**\n\n{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
