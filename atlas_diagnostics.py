"""Operational diagnostics shared by Discord commands and cron watchdogs."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parent
CRON_STATE_FILE = BOT_DIR / "cron" / "state" / "last_runs.json"
CRON_JOBS_FILE = BOT_DIR / "cron" / "jobs.json"
DEFAULT_ORPHAN_HELPER_MIN_SECONDS = 60 * 60

MCP_HELPER_PATTERNS = (
    "mcp_server.py",
    "weather-mcp",
    "google-calendar-mcp",
    "gmail-mcp",
)


@dataclass(frozen=True)
class ProcessInfo:
    """One process row from ps."""

    pid: int
    ppid: int
    pgid: int
    sid: int
    stat: str
    elapsed_seconds: int
    cmd: str


@dataclass(frozen=True)
class ServiceStatus:
    """Important systemd state for a unit."""

    scope: str
    name: str
    active_state: str
    sub_state: str
    unit_file_state: str
    main_pid: int
    load_state: str
    error: str | None = None

    @property
    def is_active(self) -> bool:
        return self.active_state == "active"

    @property
    def is_enabled(self) -> bool:
        return self.unit_file_state == "enabled"

    @property
    def is_masked(self) -> bool:
        return self.load_state == "masked" or self.unit_file_state == "masked"


@dataclass(frozen=True)
class CronJobStatus:
    """Summarized cron job state."""

    job_id: str
    name: str
    enabled: bool
    failures: int
    last_run: str | None
    disabled_after_failures: bool


@dataclass(frozen=True)
class DiagnosticsSnapshot:
    """Point-in-time ATLAS operational diagnostics."""

    provider: str
    bot_processes: tuple[ProcessInfo, ...]
    orphan_mcp_helpers: tuple[ProcessInfo, ...]
    system_service: ServiceStatus
    user_service: ServiceStatus
    cron_jobs: tuple[CronJobStatus, ...]

    @property
    def warnings(self) -> tuple[str, ...]:
        warnings: list[str] = []
        if len(self.bot_processes) != 1:
            warnings.append(f"Bot process count is {len(self.bot_processes)}; expected 1.")
        if not self.system_service.is_active:
            warnings.append("System atlas-bot.service is not active.")
        if not self.system_service.is_enabled:
            warnings.append("System atlas-bot.service is not enabled.")
        if self.user_service.is_active:
            warnings.append("User atlas-bot.service is active; this creates duplicate bot risk.")
        if self.user_service.error is None and not self.user_service.is_masked:
            warnings.append("User atlas-bot.service is not masked.")
        if self.orphan_mcp_helpers:
            warnings.append(f"{len(self.orphan_mcp_helpers)} orphan MCP helper(s) detected.")
        failed_jobs = [job for job in self.cron_jobs if job.failures > 0]
        if failed_jobs:
            warnings.append(f"{len(failed_jobs)} cron job(s) have recorded failures.")
        disabled_jobs = [job for job in self.cron_jobs if job.disabled_after_failures]
        if disabled_jobs:
            warnings.append(f"{len(disabled_jobs)} cron job(s) are disabled after failures.")
        return tuple(warnings)

    @property
    def is_ok(self) -> bool:
        return not self.warnings


def _run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def parse_elapsed_seconds(value: str) -> int:
    """Parse ps etime strings such as DD-HH:MM:SS, HH:MM:SS, or MM:SS."""
    days = 0
    remainder = value.strip()
    if "-" in remainder:
        day_part, remainder = remainder.split("-", 1)
        try:
            days = int(day_part)
        except ValueError:
            days = 0

    parts = [int(part) for part in remainder.split(":") if part.isdigit()]
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours = 0
        minutes, seconds = parts
    elif len(parts) == 1:
        hours = 0
        minutes = 0
        seconds = parts[0]
    else:
        return 0
    return (((days * 24) + hours) * 60 + minutes) * 60 + seconds


def parse_ps_output(output: str) -> tuple[ProcessInfo, ...]:
    """Parse ps output from `ps -eo pid,ppid,pgid,sid,stat,etime,cmd`."""
    processes: list[ProcessInfo] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("PID "):
            continue
        parts = line.split(None, 6)
        if len(parts) < 7:
            continue
        try:
            pid, ppid, pgid, sid = (int(parts[index]) for index in range(4))
        except ValueError:
            continue
        processes.append(
            ProcessInfo(
                pid=pid,
                ppid=ppid,
                pgid=pgid,
                sid=sid,
                stat=parts[4],
                elapsed_seconds=parse_elapsed_seconds(parts[5]),
                cmd=parts[6],
            )
        )
    return tuple(processes)


def get_processes() -> tuple[ProcessInfo, ...]:
    """Return current process table rows needed for ATLAS diagnostics."""
    result = _run_command(["ps", "-eo", "pid,ppid,pgid,sid,stat,etime,cmd"])
    return parse_ps_output(result.stdout)


def is_bot_process(process: ProcessInfo) -> bool:
    return "bot.py" in process.cmd and "python" in process.cmd


def is_mcp_helper_process(process: ProcessInfo) -> bool:
    return any(pattern in process.cmd for pattern in MCP_HELPER_PATTERNS)


def ancestor_pids(process: ProcessInfo, process_by_pid: dict[int, ProcessInfo]) -> set[int]:
    """Return known ancestor PIDs for a process."""
    ancestors: set[int] = set()
    current = process
    while current.ppid and current.ppid in process_by_pid and current.ppid not in ancestors:
        ancestors.add(current.ppid)
        current = process_by_pid[current.ppid]
    return ancestors


def get_bot_processes(processes: tuple[ProcessInfo, ...] | None = None) -> tuple[ProcessInfo, ...]:
    rows = processes if processes is not None else get_processes()
    return tuple(process for process in rows if is_bot_process(process))


def get_orphan_mcp_helpers(
    processes: tuple[ProcessInfo, ...] | None = None,
    *,
    orphan_min_seconds: int = DEFAULT_ORPHAN_HELPER_MIN_SECONDS,
) -> tuple[ProcessInfo, ...]:
    """Return long-running MCP helpers that are not descendants of a live bot process."""
    rows = processes if processes is not None else get_processes()
    process_by_pid = {process.pid: process for process in rows}
    bot_pids = {process.pid for process in get_bot_processes(rows)}
    helpers: list[ProcessInfo] = []
    for process in rows:
        if not is_mcp_helper_process(process):
            continue
        if process.elapsed_seconds < orphan_min_seconds:
            continue
        if ancestor_pids(process, process_by_pid) & bot_pids:
            continue
        helpers.append(process)
    return tuple(helpers)


def _parse_systemctl_show(
    output: str, *, scope: str, name: str, error: str | None = None
) -> ServiceStatus:
    values: dict[str, str] = {}
    for line in output.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    try:
        main_pid = int(values.get("MainPID", "0") or "0")
    except ValueError:
        main_pid = 0
    return ServiceStatus(
        scope=scope,
        name=name,
        active_state=values.get("ActiveState", "unknown"),
        sub_state=values.get("SubState", "unknown"),
        unit_file_state=values.get("UnitFileState", "unknown"),
        main_pid=main_pid,
        load_state=values.get("LoadState", "unknown"),
        error=error,
    )


def get_service_status(name: str = "atlas-bot.service", *, user: bool = False) -> ServiceStatus:
    args = ["systemctl"]
    scope = "user" if user else "system"
    if user:
        args.append("--user")
    args.extend(
        [
            "show",
            name,
            "-p",
            "ActiveState",
            "-p",
            "SubState",
            "-p",
            "UnitFileState",
            "-p",
            "MainPID",
            "-p",
            "LoadState",
        ]
    )
    result = _run_command(args)
    error = result.stderr.strip() or None
    return _parse_systemctl_show(result.stdout, scope=scope, name=name, error=error)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def get_cron_job_statuses(
    *,
    jobs_file: Path = CRON_JOBS_FILE,
    state_file: Path = CRON_STATE_FILE,
) -> tuple[CronJobStatus, ...]:
    jobs_config = _load_json(jobs_file)
    state = _load_json(state_file)
    statuses: list[CronJobStatus] = []
    for job in jobs_config.get("jobs", []):
        job_id = job.get("id")
        if not job_id:
            continue
        job_state = state.get(job_id, {})
        if isinstance(job_state, str):
            last_run = job_state
            failures = 0
        elif isinstance(job_state, dict):
            last_run = job_state.get("last_run")
            try:
                failures = int(job_state.get("failures", 0) or 0)
            except (TypeError, ValueError):
                failures = 0
        else:
            last_run = None
            failures = 0
        statuses.append(
            CronJobStatus(
                job_id=job_id,
                name=job.get("name", job_id),
                enabled=bool(job.get("enabled", True)),
                failures=failures,
                last_run=last_run,
                disabled_after_failures=failures >= 3,
            )
        )
    return tuple(statuses)


def build_diagnostics_snapshot(
    *,
    orphan_min_seconds: int = DEFAULT_ORPHAN_HELPER_MIN_SECONDS,
) -> DiagnosticsSnapshot:
    processes = get_processes()
    return DiagnosticsSnapshot(
        provider=os.getenv("ATLAS_AGENT_PROVIDER", "claude"),
        bot_processes=get_bot_processes(processes),
        orphan_mcp_helpers=get_orphan_mcp_helpers(
            processes,
            orphan_min_seconds=orphan_min_seconds,
        ),
        system_service=get_service_status("atlas-bot.service"),
        user_service=get_service_status("atlas-bot.service", user=True),
        cron_jobs=get_cron_job_statuses(),
    )


def _format_process(process: ProcessInfo) -> str:
    command = process.cmd
    if len(command) > 95:
        command = command[:92] + "..."
    return f"`{process.pid}` {command}"


def format_status_report(
    snapshot: DiagnosticsSnapshot,
    *,
    channel_label: str,
    model: str,
    channel_resolution: str,
) -> str:
    """Render a compact Discord status report."""
    status = "OK" if snapshot.is_ok else "Attention Needed"
    failed_jobs = [job for job in snapshot.cron_jobs if job.failures > 0]
    disabled_jobs = [job for job in snapshot.cron_jobs if job.disabled_after_failures]
    lines = [
        f"**ATLAS Status: {status}**",
        "",
        f"Provider/model: `{snapshot.provider}` / `{model}`",
        f"Channel: {channel_label} ({channel_resolution})",
        f"Bot processes: `{len(snapshot.bot_processes)}`",
        f"System service: `{snapshot.system_service.active_state}/{snapshot.system_service.sub_state}` "
        f"(`{snapshot.system_service.unit_file_state}`)",
        f"User service: `{snapshot.user_service.active_state}/{snapshot.user_service.sub_state}` "
        f"(`{snapshot.user_service.unit_file_state}`)",
        f"MCP helpers: `{len(snapshot.orphan_mcp_helpers)}` orphaned",
        f"Cron: `{len(snapshot.cron_jobs)}` jobs, `{len(failed_jobs)}` with failures, "
        f"`{len(disabled_jobs)}` disabled",
    ]
    if snapshot.warnings:
        lines.extend(["", "**Warnings**", *[f"- {warning}" for warning in snapshot.warnings]])
    if snapshot.orphan_mcp_helpers:
        lines.extend(
            [
                "",
                "**Orphan MCP Helpers**",
                *[f"- {_format_process(process)}" for process in snapshot.orphan_mcp_helpers[:5]],
            ]
        )
        if len(snapshot.orphan_mcp_helpers) > 5:
            lines.append(f"- ...and {len(snapshot.orphan_mcp_helpers) - 5} more")
    if failed_jobs:
        lines.extend(
            [
                "",
                "**Cron Failures**",
                *[
                    f"- `{job.job_id}`: {job.failures} failure(s), last run `{job.last_run or 'never'}`"
                    for job in failed_jobs[:5]
                ],
            ]
        )
    return "\n".join(lines)


def format_watchdog_report(snapshot: DiagnosticsSnapshot) -> str:
    """Render the silent-unless-noteworthy cron watchdog output."""
    if snapshot.is_ok:
        return "NO_ALERT"
    lines = ["**ATLAS Ops Watchdog: Attention Needed**", ""]
    lines.extend(f"- {warning}" for warning in snapshot.warnings)
    if snapshot.bot_processes:
        lines.extend(["", "**Bot Processes**"])
        lines.extend(f"- {_format_process(process)}" for process in snapshot.bot_processes[:8])
    if snapshot.orphan_mcp_helpers:
        lines.extend(["", "**Orphan MCP Helpers**"])
        lines.extend(
            f"- {_format_process(process)}" for process in snapshot.orphan_mcp_helpers[:10]
        )
        if len(snapshot.orphan_mcp_helpers) > 10:
            lines.append(f"- ...and {len(snapshot.orphan_mcp_helpers) - 10} more")
    disabled_jobs = [job for job in snapshot.cron_jobs if job.disabled_after_failures]
    if disabled_jobs:
        lines.extend(["", "**Disabled Cron Jobs**"])
        lines.extend(f"- `{job.job_id}` ({job.failures} failures)" for job in disabled_jobs)
    failed_jobs = [
        job for job in snapshot.cron_jobs if job.failures > 0 and not job.disabled_after_failures
    ]
    if failed_jobs:
        lines.extend(["", "**Cron Jobs With Failures**"])
        lines.extend(f"- `{job.job_id}` ({job.failures} failure(s))" for job in failed_jobs[:10])
    return "\n".join(lines)
