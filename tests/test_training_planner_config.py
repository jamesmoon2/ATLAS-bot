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


def test_weekly_training_planner_job_prompt_mentions_training_state():
    jobs = json.loads((ROOT / "cron" / "jobs.json").read_text(encoding="utf-8"))
    weekly_job = next(job for job in jobs["jobs"] if job["id"] == "weekly_training_planner")

    assert "{vault_path}/Areas/Health/Training-State.md" in weekly_job["prompt"]
    assert "{vault_path}/Areas/Health/Workout-Logs/" in weekly_job["prompt"]
    assert "authoritative reference for week detection" in weekly_job["prompt"]
    assert "{current_datetime}" in weekly_job["prompt"]
