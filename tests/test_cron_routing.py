"""Tests for cron job channel routing."""

import json
from pathlib import Path


def test_cron_jobs_route_to_expected_channel_webhooks():
    jobs = json.loads((Path(__file__).resolve().parents[1] / "cron" / "jobs.json").read_text())
    url_env_by_id = {
        job["id"]: (job.get("notify") or {}).get("url_env")
        for job in jobs["jobs"]
        if (job.get("notify") or {}).get("type") == "webhook"
    }

    assert url_env_by_id["morning_briefing"] == "DISCORD_WEBHOOK_ATLAS"
    assert url_env_by_id["weekly_training_planner"] == "DISCORD_WEBHOOK_HEALTH"
    assert url_env_by_id["mcp_health_check"] == "DISCORD_WEBHOOK_ATLAS_DEV"
    assert url_env_by_id["ops_watchdog"] == "DISCORD_WEBHOOK_ATLAS_DEV"
    assert url_env_by_id["stale_project_detector"] == "DISCORD_WEBHOOK_PROJECTS"
    assert url_env_by_id["daily_summary"] == "DISCORD_WEBHOOK_BRIEFINGS"
    assert url_env_by_id["session_archive"] == "DISCORD_WEBHOOK_ATLAS_DEV"
    assert url_env_by_id["context_drift"] == "DISCORD_WEBHOOK_PROJECTS"
    assert url_env_by_id["med_reminder"] == "DISCORD_WEBHOOK_HEALTH"
    assert url_env_by_id["med_config_sync"] == "DISCORD_WEBHOOK_HEALTH"
    assert url_env_by_id["health_pattern_monitor"] == "DISCORD_WEBHOOK_HEALTH"
    assert url_env_by_id["librarian_digest"] == "DISCORD_WEBHOOK_PROJECTS"
    assert url_env_by_id["weekly_review"] == "DISCORD_WEBHOOK_BRIEFINGS"
