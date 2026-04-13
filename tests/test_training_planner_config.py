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
    assert "atlas__google_calendar__get_profile" in morning_job["allowed_tools"]
    assert "atlas__google_calendar__search_events" in weekly_job["allowed_tools"]
    assert "atlas__google_calendar__create_event" in weekly_job["allowed_tools"]
    assert "atlas__google_calendar__delete_event" in weekly_job["allowed_tools"]
    assert "atlas__google_calendar__get_profile" in health_job["allowed_tools"]
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
