"""Unit tests for Garmin normalization helpers."""

from __future__ import annotations

from src.garmin_mcp.tools import (
    curate_activities_by_date,
    curate_activities_for_date,
    curate_activity,
    curate_body_battery_events,
    curate_hrv_data,
    curate_training_readiness,
)


def test_curate_activities_for_date_keeps_expected_fields() -> None:
    payload = {
        "ActivitiesForDay": {
            "payload": [
                {
                    "activityId": 123,
                    "activityName": "Morning Run",
                    "activityType": {"typeKey": "running"},
                    "startTimeLocal": "2026-04-21T07:00:00.0",
                    "duration": 1800,
                    "averageHR": 144,
                },
            ],
        },
    }

    curated = curate_activities_for_date("2026-04-21", payload)

    assert curated["count"] == 1
    assert curated["activities"][0]["id"] == 123
    assert curated["activities"][0]["type"] == "running"
    assert curated["activities"][0]["avg_hr_bpm"] == 144


def test_curate_activities_by_date_tracks_range_and_filter() -> None:
    curated = curate_activities_by_date(
        "2026-04-20",
        "2026-04-21",
        [
            {
                "activityId": 123,
                "activityName": "Morning Run",
                "activityType": {"typeKey": "running"},
            },
        ],
        "running",
    )

    assert curated["date_range"] == {"start": "2026-04-20", "end": "2026-04-21"}
    assert curated["activity_type"] == "running"
    assert curated["activities"][0]["name"] == "Morning Run"


def test_curate_activity_surfaces_training_load_and_body_battery() -> None:
    curated = curate_activity(
        {
            "activityId": 456,
            "activityName": "Strength",
            "activityTypeDTO": {"typeKey": "strength_training", "parentTypeId": 17},
            "summaryDTO": {
                "startTimeLocal": "2026-04-21T18:00:00.0",
                "duration": 2400,
                "averageHR": 121,
                "activityTrainingLoad": 54.2,
                "differenceBodyBattery": -6,
            },
            "metadataDTO": {"lapCount": 3},
        },
    )

    assert curated["id"] == 456
    assert curated["type"] == "strength_training"
    assert curated["training_load"] == 54.2
    assert curated["body_battery_impact"] == -6
    assert curated["lap_count"] == 3


def test_curate_training_readiness_handles_list_payloads() -> None:
    curated = curate_training_readiness(
        "2026-04-21",
        [
            {
                "calendarDate": "2026-04-21",
                "timestampLocal": "2026-04-21T06:15:00.0",
                "inputContext": "AFTER_WAKEUP_RESET",
                "score": 72,
                "level": "HIGH",
                "sleepScore": 88,
            },
        ],
    )

    assert curated["entries"][0]["context"] == "AFTER_WAKEUP_RESET"
    assert curated["entries"][0]["score"] == 72
    assert curated["entries"][0]["sleep_score"] == 88


def test_curate_hrv_data_handles_missing_payload() -> None:
    assert curate_hrv_data("2026-04-21", None) == {"date": "2026-04-21"}


def test_curate_body_battery_events_compacts_event_fields() -> None:
    curated = curate_body_battery_events(
        "2026-04-21",
        [
            {
                "activityId": 777,
                "event": {
                    "eventType": "RECORDED_ACTIVITY",
                    "bodyBatteryImpact": -12,
                    "startTimestampLocal": "2026-04-21T18:00:00.0",
                },
            },
        ],
    )

    assert curated["events"][0]["activity_id"] == 777
    assert curated["events"][0]["event_type"] == "RECORDED_ACTIVITY"
    assert curated["events"][0]["body_battery_impact"] == -12
