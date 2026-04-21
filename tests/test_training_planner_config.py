"""Regression checks for weekly training planner configuration."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_weekly_training_planner_skill_uses_explicit_health_paths():
    skill_text = (ROOT / ".claude" / "skills" / "weekly-training-planner.md").read_text(
        encoding="utf-8"
    )

    assert "/home/jmooney/vault/Areas/Health/Training-State.md" in skill_text
    assert "/home/jmooney/vault/Areas/Health/Workout-Logs/" in skill_text
    assert "Current Time:**` value provided in the prompt" in skill_text
    assert "**Summary:** `Workout: [Type]`" in skill_text
    assert "Strength Time:** Default 5:40 AM - 6:40 AM" in skill_text
    assert "Cardio Time:** Default 5:40 AM - 6:20 AM" in skill_text
    assert "Saturday Mobility/Core/Rehab:** 8:00 AM - 8:45 AM" in skill_text
    assert "colorId `11`" in skill_text
    assert "colorId `7`" in skill_text
    assert "colorId `6`" in skill_text
    assert "America/Los_Angeles" in skill_text
    assert "include weights for every prescribed movement" in skill_text
    assert "Analyze the last 2-4 comparable sessions" in skill_text
    assert (
        "Use the last successful logged load as a baseline input, not an automatic prescription"
        in skill_text
    )
    assert "progress, hold, or regress the load" in skill_text
    assert "Week 4 deloads should usually hold or slightly reduce loads" in skill_text
    assert "not blind last-log copy" in skill_text
    assert "Never create a weightlifting calendar event with missing loads" in skill_text
    assert "high-level coaching decision, not data transcription" in skill_text
    assert "@ 90 lbs" in skill_text
    assert "@ BW" in skill_text
    assert "@ Band" in skill_text
    assert "Saturday is **Mobility, Core & Rehab**, not a rest day" in skill_text
    assert "Sunday is the default rest day" in skill_text
    assert "mcp__google-calendar__" not in skill_text


def test_weekly_training_planner_job_prompt_mentions_training_state():
    jobs = json.loads((ROOT / "cron" / "jobs.json").read_text(encoding="utf-8"))
    weekly_job = next(job for job in jobs["jobs"] if job["id"] == "weekly_training_planner")

    assert "{vault_path}/Areas/Health/Training-State.md" in weekly_job["prompt"]
    assert "{vault_path}/Areas/Health/Workout-Logs/" in weekly_job["prompt"]
    assert "authoritative reference for week detection" in weekly_job["prompt"]
    assert "{current_datetime}" in weekly_job["prompt"]


def test_calendar_skills_are_provider_agnostic():
    morning_skill = (ROOT / ".claude" / "skills" / "morning-briefing.md").read_text(
        encoding="utf-8"
    )
    weekly_skill = (ROOT / ".claude" / "skills" / "weekly-training-planner.md").read_text(
        encoding="utf-8"
    )

    assert "mcp__google-calendar__" not in morning_skill
    assert "mcp__google-calendar__" not in weekly_skill
    assert "**Current Time:**" in morning_skill


def test_calendar_jobs_use_atlas_mcp_aliases():
    jobs = json.loads((ROOT / "cron" / "jobs.json").read_text(encoding="utf-8"))

    morning_job = next(job for job in jobs["jobs"] if job["id"] == "morning_briefing")
    weekly_job = next(job for job in jobs["jobs"] if job["id"] == "weekly_training_planner")
    health_job = next(job for job in jobs["jobs"] if job["id"] == "mcp_health_check")

    assert "atlas__google_calendar__search_events" in morning_job["allowed_tools"]
    assert "atlas__google_calendar__probe_auth" in morning_job["allowed_tools"]
    assert "atlas__google_calendar__search_events" in weekly_job["allowed_tools"]
    assert "atlas__google_calendar__create_event" in weekly_job["allowed_tools"]
    assert "atlas__google_calendar__delete_event" in weekly_job["allowed_tools"]
    assert "atlas__google_calendar__probe_auth" in health_job["allowed_tools"]
    assert "atlas__gmail__list_labels" in health_job["allowed_tools"]


def test_date_sensitive_cron_skills_use_prompt_time_and_unattended_guidance():
    morning_briefing = (ROOT / ".claude" / "skills" / "morning-briefing.md").read_text(
        encoding="utf-8"
    )
    daily_summary = (ROOT / ".claude" / "skills" / "daily-summary.md").read_text(encoding="utf-8")
    health_monitor = (ROOT / ".claude" / "skills" / "health-pattern-monitor.md").read_text(
        encoding="utf-8"
    )
    second_brain = (ROOT / ".claude" / "skills" / "second-brain-librarian.md").read_text(
        encoding="utf-8"
    )
    weekly_review = (ROOT / ".claude" / "skills" / "weekly-review.md").read_text(encoding="utf-8")
    weekly_training = (ROOT / ".claude" / "skills" / "weekly-training-planner.md").read_text(
        encoding="utf-8"
    )

    assert "**Current Time:**" in morning_briefing
    assert "**Current Time:**" in daily_summary
    assert "**Current Time:**" in health_monitor
    assert "**Current Time:**" in weekly_review
    assert "**Current Time:**" in weekly_training
    assert "unattended scheduled job" in morning_briefing
    assert "unattended scheduled job" in daily_summary
    assert "unattended scheduled job" in health_monitor
    assert "unattended scheduled job" in second_brain
    assert "unattended scheduled job" in weekly_review
    assert "unattended scheduled job" in weekly_training


def test_silent_oura_context_job_allows_empty_output():
    jobs = json.loads((ROOT / "cron" / "jobs.json").read_text(encoding="utf-8"))
    oura_job = next(job for job in jobs["jobs"] if job["id"] == "oura_context_update")

    assert oura_job["empty_output_ok"] is True


def test_health_jobs_include_whoop_tools():
    jobs = json.loads((ROOT / "cron" / "jobs.json").read_text(encoding="utf-8"))
    target_ids = {
        "morning_briefing",
        "weekly_training_planner",
        "oura_context_update",
        "health_pattern_monitor",
        "weekly_review",
    }

    for job in jobs["jobs"]:
        if job["id"] not in target_ids:
            continue
        assert "mcp__whoop__get_daily_sleep" in job["allowed_tools"]
        assert "mcp__whoop__get_daily_recovery" in job["allowed_tools"]
        assert "mcp__whoop__get_daily_cycle" in job["allowed_tools"]


def test_health_skills_reference_oura_and_whoop_data():
    morning_skill = (ROOT / ".claude" / "skills" / "morning-briefing.md").read_text(
        encoding="utf-8"
    )
    health_monitor = (ROOT / ".claude" / "skills" / "health-pattern-monitor.md").read_text(
        encoding="utf-8"
    )
    weekly_review = (ROOT / ".claude" / "skills" / "weekly-review.md").read_text(encoding="utf-8")
    weekly_training = (ROOT / ".claude" / "skills" / "weekly-training-planner.md").read_text(
        encoding="utf-8"
    )

    for skill_text in (morning_skill, health_monitor, weekly_review, weekly_training):
        assert "mcp__oura__" in skill_text
        assert "mcp__whoop__" in skill_text


def test_librarian_digest_job_prefers_preloaded_index_and_medium_reasoning():
    jobs = json.loads((ROOT / "cron" / "jobs.json").read_text(encoding="utf-8"))
    librarian_job = next(job for job in jobs["jobs"] if job["id"] == "librarian_digest")

    assert librarian_job["reasoning_effort"] == "medium"
    assert librarian_job["timeout_seconds"] == 300
    assert librarian_job["allowed_tools"] == ["Read", "Glob"]
    assert "Generate a concise second-brain librarian digest" in librarian_job["prompt"]
    assert "preloaded vault index as the primary source" in librarian_job["prompt"]
    assert "{current_datetime}" in librarian_job["prompt"]


def test_morning_briefing_job_uses_medium_reasoning_and_longer_timeout():
    jobs = json.loads((ROOT / "cron" / "jobs.json").read_text(encoding="utf-8"))
    morning_job = next(job for job in jobs["jobs"] if job["id"] == "morning_briefing")

    assert morning_job["reasoning_effort"] == "medium"
    assert morning_job["timeout_seconds"] == 300


def test_daily_summary_job_uses_medium_reasoning_and_longer_timeout():
    jobs = json.loads((ROOT / "cron" / "jobs.json").read_text(encoding="utf-8"))
    daily_summary_job = next(job for job in jobs["jobs"] if job["id"] == "daily_summary")

    assert daily_summary_job["reasoning_effort"] == "medium"
    assert daily_summary_job["timeout_seconds"] == 300
    assert "Work efficiently:" in daily_summary_job["prompt"]


def test_med_config_sync_job_stays_lightweight_and_ignores_future_protocols():
    jobs = json.loads((ROOT / "cron" / "jobs.json").read_text(encoding="utf-8"))
    med_sync_job = next(job for job in jobs["jobs"] if job["id"] == "med_config_sync")

    assert med_sync_job["reasoning_effort"] == "low"
    assert med_sync_job["timeout_seconds"] == 120
    assert "Treat planned future medications" in med_sync_job["prompt"]
    assert "output `NO_ALERT` and nothing else" in med_sync_job["prompt"]


def test_session_archive_runs_after_daily_summary_headroom():
    jobs = json.loads((ROOT / "cron" / "jobs.json").read_text(encoding="utf-8"))
    archive_job = next(job for job in jobs["jobs"] if job["id"] == "session_archive")

    assert archive_job["schedule"] == "5 0 * * *"


def test_context_drift_uses_shared_prompt_runner_with_concise_output():
    jobs = json.loads((ROOT / "cron" / "jobs.json").read_text(encoding="utf-8"))
    context_drift_job = next(job for job in jobs["jobs"] if job["id"] == "context_drift")

    assert "command" not in context_drift_job
    assert context_drift_job["model"] == "sonnet"
    assert context_drift_job["reasoning_effort"] == "medium"
    assert context_drift_job["timeout_seconds"] == 300
    assert context_drift_job["allowed_tools"] == ["Read", "Glob"]
    assert "Discord-friendly" in context_drift_job["prompt"]
    assert "{current_datetime}" in context_drift_job["prompt"]
