"""Tests for shared ATLAS operational diagnostics."""

from __future__ import annotations

import json

import atlas_diagnostics as diagnostics


def _process(pid: int, ppid: int, cmd: str, *, elapsed_seconds: int = 7200):
    return diagnostics.ProcessInfo(
        pid=pid,
        ppid=ppid,
        pgid=pid,
        sid=pid,
        stat="S",
        elapsed_seconds=elapsed_seconds,
        cmd=cmd,
    )


def _service(
    *,
    scope: str,
    active_state: str = "inactive",
    sub_state: str = "dead",
    unit_file_state: str = "disabled",
    load_state: str = "loaded",
    error: str | None = None,
):
    return diagnostics.ServiceStatus(
        scope=scope,
        name="atlas-bot.service",
        active_state=active_state,
        sub_state=sub_state,
        unit_file_state=unit_file_state,
        main_pid=123,
        load_state=load_state,
        error=error,
    )


def test_parse_elapsed_seconds():
    assert diagnostics.parse_elapsed_seconds("01:02") == 62
    assert diagnostics.parse_elapsed_seconds("03:04:05") == 11045
    assert diagnostics.parse_elapsed_seconds("2-03:04:05") == 183845
    assert diagnostics.parse_elapsed_seconds("bad-value") == 0


def test_parse_ps_output():
    output = """\
    PID    PPID    PGID     SID STAT     ELAPSED CMD
     10       1      10      10 Sl         02:03 python bot.py
     11      10      10      10 S       1-00:00:00 python mcp_server.py
    """

    rows = diagnostics.parse_ps_output(output)

    assert len(rows) == 2
    assert rows[0].pid == 10
    assert rows[0].elapsed_seconds == 123
    assert rows[1].cmd == "python mcp_server.py"


def test_get_bot_processes_filters_python_bot():
    rows = (
        _process(10, 1, "/home/jmooney/atlas-bot/venv/bin/python bot.py"),
        _process(11, 1, "python other.py"),
    )

    assert diagnostics.get_bot_processes(rows) == (rows[0],)


def test_get_orphan_mcp_helpers_excludes_live_bot_descendants_and_young_helpers():
    bot = _process(10, 1, "python bot.py")
    attached_helper = _process(11, 10, "python mcp_server.py")
    orphan_helper = _process(20, 1, "npx weather-mcp")
    young_helper = _process(30, 1, "npx google-calendar-mcp", elapsed_seconds=30)
    rows = (bot, attached_helper, orphan_helper, young_helper)

    assert diagnostics.get_orphan_mcp_helpers(rows, orphan_min_seconds=60) == (orphan_helper,)


def test_parse_systemctl_show():
    status = diagnostics._parse_systemctl_show(
        "ActiveState=active\nSubState=running\nUnitFileState=enabled\nMainPID=42\nLoadState=loaded\n",
        scope="system",
        name="atlas-bot.service",
    )

    assert status.is_active
    assert status.is_enabled
    assert not status.is_masked
    assert status.main_pid == 42


def test_get_cron_job_statuses_reads_jobs_and_state(tmp_path):
    jobs_file = tmp_path / "jobs.json"
    state_file = tmp_path / "last_runs.json"
    jobs_file.write_text(
        json.dumps(
            {
                "jobs": [
                    {"id": "ok_job", "name": "OK Job", "enabled": True},
                    {"id": "failed_job", "name": "Failed Job", "enabled": True},
                ]
            }
        ),
        encoding="utf-8",
    )
    state_file.write_text(
        json.dumps(
            {
                "ok_job": "2026-04-26T10:00:00",
                "failed_job": {"last_run": "2026-04-26T10:05:00", "failures": 3},
            }
        ),
        encoding="utf-8",
    )

    statuses = diagnostics.get_cron_job_statuses(jobs_file=jobs_file, state_file=state_file)

    assert statuses[0].last_run == "2026-04-26T10:00:00"
    assert statuses[0].failures == 0
    assert statuses[1].failures == 3
    assert statuses[1].disabled_after_failures


def test_watchdog_report_is_silent_when_snapshot_is_clean():
    snapshot = diagnostics.DiagnosticsSnapshot(
        provider="claude",
        bot_processes=(_process(10, 1, "python bot.py"),),
        orphan_mcp_helpers=(),
        system_service=_service(scope="system", active_state="active", unit_file_state="enabled"),
        user_service=_service(scope="user", unit_file_state="masked", load_state="masked"),
        cron_jobs=(
            diagnostics.CronJobStatus(
                job_id="job",
                name="Job",
                enabled=True,
                failures=0,
                last_run="2026-04-26T10:00:00",
                disabled_after_failures=False,
            ),
        ),
    )

    assert diagnostics.format_watchdog_report(snapshot) == "NO_ALERT"


def test_unavailable_user_systemd_scope_does_not_warn_as_unmasked():
    snapshot = diagnostics.DiagnosticsSnapshot(
        provider="claude",
        bot_processes=(_process(10, 1, "python bot.py"),),
        orphan_mcp_helpers=(),
        system_service=_service(scope="system", active_state="active", unit_file_state="enabled"),
        user_service=_service(
            scope="user",
            active_state="unknown",
            unit_file_state="unknown",
            load_state="unknown",
            error="Failed to connect to bus",
        ),
        cron_jobs=(),
    )

    assert "User atlas-bot.service is not masked." not in snapshot.warnings


def test_status_and_watchdog_reports_include_warnings():
    orphan = _process(20, 1, "npx weather-mcp")
    snapshot = diagnostics.DiagnosticsSnapshot(
        provider="claude",
        bot_processes=(),
        orphan_mcp_helpers=(orphan,),
        system_service=_service(scope="system"),
        user_service=_service(scope="user", active_state="active", unit_file_state="enabled"),
        cron_jobs=(
            diagnostics.CronJobStatus(
                job_id="broken",
                name="Broken",
                enabled=True,
                failures=1,
                last_run="2026-04-26T10:00:00",
                disabled_after_failures=False,
            ),
        ),
    )

    status_report = diagnostics.format_status_report(
        snapshot,
        channel_label="#atlas-dev",
        model="opus",
        channel_resolution="matched configured channel name",
    )
    watchdog_report = diagnostics.format_watchdog_report(snapshot)

    assert "Attention Needed" in status_report
    assert "orphan MCP helper" in status_report
    assert "ATLAS Ops Watchdog" in watchdog_report
    assert "`broken`" in watchdog_report
