#!/usr/bin/env python3
"""
ATLAS Cron Job Dispatcher

Runs every minute via cron, checks jobs.json for due jobs, and executes them
via Claude Code CLI. Supports webhook notifications or silent logging.

Usage:
    python dispatcher.py                    # Normal mode - run due jobs
    python dispatcher.py --run-now JOB_ID   # Force run a specific job
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
import aiohttp
from croniter import croniter

# Load environment variables from .env file
BOT_DIR = Path(__file__).parent.parent
load_dotenv(BOT_DIR / ".env")

# Paths
BOT_DIR = Path(__file__).parent.parent
CRON_DIR = Path(__file__).parent
JOBS_FILE = CRON_DIR / "jobs.json"
STATE_FILE = CRON_DIR / "state" / "last_runs.json"
LOGS_DIR = BOT_DIR / "logs" / "cron"


def log(message: str) -> None:
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def load_state() -> dict:
    """Load last run times from state file."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(state: dict) -> None:
    """Persist last run times."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def is_job_due(job: dict, state: dict, now: datetime) -> bool:
    """Check if job should run based on schedule and last run."""
    from datetime import timedelta

    job_id = job["id"]
    tz = ZoneInfo(job.get("timezone", "UTC"))
    now_tz = now.astimezone(tz)

    # Start from 2 minutes ago and find the next scheduled time after that
    two_mins_ago = now_tz - timedelta(minutes=2)
    cron = croniter(job["schedule"], two_mins_ago)
    next_scheduled = cron.get_next(datetime)

    # Check if that scheduled time is in the past (meaning it's due) and within our window
    time_since_scheduled = (now_tz - next_scheduled).total_seconds()
    if time_since_scheduled < 0 or time_since_scheduled > 120:
        return False  # Not in execution window

    # Check if we've already run for this scheduled time
    last_run_str = state.get(job_id)
    if last_run_str:
        try:
            last_run = datetime.fromisoformat(last_run_str)
            # If last run was after or at the scheduled time, skip
            if last_run >= next_scheduled:
                return False
        except ValueError:
            pass  # Invalid timestamp, proceed with run

    return True


async def run_claude(job: dict) -> tuple[str, bool]:
    """Execute Claude CLI with job prompt. Returns (output, success)."""
    allowed_tools = ",".join(job.get("allowed_tools", ["Read"]))
    timeout = job.get("timeout_seconds", 180)
    model = job.get("model", "sonnet")

    # Inject current datetime into prompt (in job's timezone)
    tz = ZoneInfo(job.get("timezone", "America/Los_Angeles"))
    now = datetime.now(tz)
    prompt = job["prompt"].replace(
        "{current_datetime}",
        now.strftime("%A, %B %d, %Y at %I:%M %p %Z")
    )

    try:
        process = await asyncio.create_subprocess_exec(
            "claude",
            "--print",
            "--model",
            model,
            "--allowedTools",
            allowed_tools,
            "-p",
            prompt,
            cwd=str(CRON_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "ANTHROPIC_DISABLE_PROMPT_CACHING": "1"},
        )

        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)

        output = stdout.decode().strip()
        if not output and stderr:
            error_msg = stderr.decode().strip()
            # Filter out common non-error stderr messages
            if "error" in error_msg.lower() or "failed" in error_msg.lower():
                return f"Error: {error_msg}", False

        return output or "No response generated.", bool(output)

    except asyncio.TimeoutError:
        process.kill()
        return f"Job timed out after {timeout} seconds.", False
    except Exception as e:
        return f"Error: {str(e)}", False


async def send_webhook(content: str, notify_config: dict) -> bool:
    """Send to Discord webhook."""
    url = os.getenv(notify_config.get("url_env", "DISCORD_WEBHOOK_URL"))
    if not url:
        log(f"Webhook URL not found in env: {notify_config.get('url_env')}")
        return False

    username = notify_config.get("username", "ATLAS Cron")

    # Discord has 2000 char limit, use 1900 to be safe
    chunks = [content[i : i + 1900] for i in range(0, len(content), 1900)]

    try:
        async with aiohttp.ClientSession() as session:
            for chunk in chunks:
                async with session.post(
                    url, json={"content": chunk, "username": username}
                ) as resp:
                    if resp.status not in (200, 204):
                        log(f"Webhook failed with status {resp.status}")
                        return False
                await asyncio.sleep(0.5)  # Rate limiting
        return True
    except Exception as e:
        log(f"Webhook error: {e}")
        return False


async def execute_job(job: dict) -> bool:
    """Run a single job. Returns success status."""
    job_id = job["id"]
    job_name = job.get("name", job_id)
    log_file = LOGS_DIR / f"{job_id}.log"

    timestamp = datetime.now().isoformat()
    log_entry = f"\n{'=' * 60}\n[{timestamp}] Running: {job_name}\n{'=' * 60}\n"

    log(f"Executing job: {job_name}")

    output, success = await run_claude(job)
    log_entry += f"\nOutput:\n{output}\n"

    # Handle notification
    notify = job.get("notify", {})
    notify_type = notify.get("type", "silent")

    if notify_type == "webhook" and success:
        today = datetime.now().strftime("%A, %B %d, %Y")
        header = f"**{job_name}** - {today}\n\n"
        webhook_success = await send_webhook(header + output, notify)
        log_entry += f"\nWebhook: {'sent' if webhook_success else 'failed'}\n"
        log(f"Webhook {'sent' if webhook_success else 'failed'} for {job_name}")
    elif notify_type == "silent":
        log_entry += "\nNotification: silent (logged only)\n"

    # Write to job-specific log
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a") as f:
        f.write(log_entry)

    return success


async def main(run_now: str | None = None):
    """Main dispatcher - check all jobs and run those that are due."""
    if not JOBS_FILE.exists():
        log(f"Jobs file not found: {JOBS_FILE}")
        sys.exit(1)

    try:
        config = json.loads(JOBS_FILE.read_text())
    except json.JSONDecodeError as e:
        log(f"Invalid jobs.json: {e}")
        sys.exit(1)

    state = load_state()
    now = datetime.now(ZoneInfo("UTC"))

    jobs = config.get("jobs", [])
    if not jobs:
        log("No jobs defined")
        return

    for job in jobs:
        job_id = job.get("id")
        if not job_id:
            log("Skipping job without id")
            continue

        # If --run-now specified, only run that job (skip enabled/due checks)
        if run_now:
            if job_id != run_now:
                continue
            log(f"Force-running job: {job_id}")
        else:
            if not job.get("enabled", True):
                continue
            if not is_job_due(job, state, now):
                continue

        # Save state BEFORE executing to prevent race condition with next cron invocation
        # (job may take longer than 1 minute, causing duplicate runs)
        tz = ZoneInfo(job.get("timezone", "UTC"))
        state[job_id] = now.astimezone(tz).isoformat()
        save_state(state)

        success = await execute_job(job)
        if success:
            log(f"Job {job_id} completed successfully")
        else:
            # Job failed - clear state so it retries on next cron cycle
            del state[job_id]
            save_state(state)
            log(f"Job {job_id} failed - will retry next run")

    # If --run-now was specified but job wasn't found
    if run_now and not any(j.get("id") == run_now for j in jobs):
        log(f"Job not found: {run_now}")
        log(f"Available jobs: {[j.get('id') for j in jobs]}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ATLAS Cron Job Dispatcher")
    parser.add_argument(
        "--run-now",
        metavar="JOB_ID",
        help="Force run a specific job immediately (bypasses schedule and enabled checks)",
    )
    args = parser.parse_args()

    asyncio.run(main(run_now=args.run_now))
