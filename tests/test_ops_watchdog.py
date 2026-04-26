"""Tests for the ATLAS ops watchdog cron command."""

from __future__ import annotations

import atlas_diagnostics as diagnostics
from cron import ops_watchdog


def _process(pid: int, cmd: str):
    return diagnostics.ProcessInfo(
        pid=pid,
        ppid=1,
        pgid=pid,
        sid=pid,
        stat="S",
        elapsed_seconds=7200,
        cmd=cmd,
    )


def _service(scope: str, *, active: bool, enabled: bool, masked: bool = False):
    return diagnostics.ServiceStatus(
        scope=scope,
        name="atlas-bot.service",
        active_state="active" if active else "inactive",
        sub_state="running" if active else "dead",
        unit_file_state="masked" if masked else ("enabled" if enabled else "disabled"),
        main_pid=123,
        load_state="masked" if masked else "loaded",
    )


def _snapshot(*, warnings: bool):
    return diagnostics.DiagnosticsSnapshot(
        provider="claude",
        bot_processes=(_process(10, "python bot.py"),),
        orphan_mcp_helpers=(_process(20, "npx weather-mcp"),) if warnings else (),
        system_service=_service("system", active=True, enabled=True),
        user_service=_service("user", active=False, enabled=False, masked=True),
        cron_jobs=(),
    )


def test_orphan_min_seconds_uses_default_for_bad_values(monkeypatch):
    monkeypatch.setenv("ATLAS_OPS_WATCHDOG_ORPHAN_MIN_SECONDS", "not-a-number")

    assert ops_watchdog._orphan_min_seconds() == 60 * 60


def test_render_watchdog_output_suppresses_repeated_identical_alerts(tmp_path):
    state_file = tmp_path / "ops_watchdog.json"
    snapshot = _snapshot(warnings=True)

    first_output = ops_watchdog.render_watchdog_output(
        snapshot,
        state_file=state_file,
        now=1000,
        repeat_seconds=3600,
    )
    second_output = ops_watchdog.render_watchdog_output(
        snapshot,
        state_file=state_file,
        now=1200,
        repeat_seconds=3600,
    )

    assert "ATLAS Ops Watchdog" in first_output
    assert second_output == "NO_ALERT"


def test_render_watchdog_output_realerts_after_repeat_window(tmp_path):
    state_file = tmp_path / "ops_watchdog.json"
    snapshot = _snapshot(warnings=True)

    ops_watchdog.render_watchdog_output(
        snapshot,
        state_file=state_file,
        now=1000,
        repeat_seconds=3600,
    )
    output = ops_watchdog.render_watchdog_output(
        snapshot,
        state_file=state_file,
        now=5000,
        repeat_seconds=3600,
    )

    assert "ATLAS Ops Watchdog" in output


def test_render_watchdog_output_clears_state_when_clean(tmp_path):
    state_file = tmp_path / "ops_watchdog.json"
    ops_watchdog.render_watchdog_output(
        _snapshot(warnings=True),
        state_file=state_file,
        now=1000,
        repeat_seconds=3600,
    )

    output = ops_watchdog.render_watchdog_output(_snapshot(warnings=False), state_file=state_file)

    assert output == "NO_ALERT"
    assert not state_file.exists()


def test_main_prints_watchdog_report(monkeypatch, capsys):
    snapshot = object()
    monkeypatch.setattr(
        ops_watchdog, "build_diagnostics_snapshot", lambda orphan_min_seconds: snapshot
    )
    monkeypatch.setattr(ops_watchdog, "_orphan_min_seconds", lambda: 123)
    monkeypatch.setattr(ops_watchdog, "render_watchdog_output", lambda value: "NO_ALERT")

    assert ops_watchdog.main() == 0
    assert capsys.readouterr().out.strip() == "NO_ALERT"
