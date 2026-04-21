"""Unit tests for WHOOP daily normalization helpers."""

from __future__ import annotations

from datetime import date

from src.whoop_mcp.tools import (
    normalize_cycle_record,
    normalize_recovery_record,
    normalize_sleep_record,
    normalize_workout_record,
    select_cycle_for_day,
    select_primary_sleep,
    select_recovery_for_day,
)


def test_select_primary_sleep_uses_local_end_date_and_ignores_naps() -> None:
    records = [
        {
            "id": "nap",
            "start": "2026-04-17T20:00:00Z",
            "end": "2026-04-17T20:20:00Z",
            "nap": True,
            "score": {"stage_summary": {"total_in_bed_time_milli": 1_200_000}},
        },
        {
            "id": "main-sleep",
            "start": "2026-04-17T05:00:00Z",
            "end": "2026-04-17T14:00:00Z",
            "nap": False,
            "score": {"stage_summary": {"total_in_bed_time_milli": 28_800_000}},
        },
    ]

    selected = select_primary_sleep(records, date(2026, 4, 17))

    assert selected is not None
    assert selected["id"] == "main-sleep"


def test_select_recovery_for_day_matches_local_end_date() -> None:
    records = [
        {
            "id": "recovery-1",
            "created_at": "2026-04-17T14:00:00Z",
            "score": {"recovery_score": 61},
        },
    ]

    selected = select_recovery_for_day(records, date(2026, 4, 17))

    assert selected is not None
    assert selected["id"] == "recovery-1"


def test_select_cycle_for_day_uses_overlap() -> None:
    records = [
        {
            "id": 1,
            "start": "2026-04-16T13:00:00Z",
            "end": "2026-04-17T12:00:00Z",
            "score": {"strain": 10.4},
        },
        {
            "id": 2,
            "start": "2026-04-17T12:00:00Z",
            "end": "2026-04-18T11:00:00Z",
            "score": {"strain": 15.2},
        },
    ]

    selected = select_cycle_for_day(records, date(2026, 4, 17))

    assert selected is not None
    assert selected["id"] == 2


def test_normalize_sleep_record_surfaces_key_percentages() -> None:
    normalized = normalize_sleep_record(
        {
            "id": "sleep-1",
            "start": "2026-04-17T05:00:00Z",
            "end": "2026-04-17T13:00:00Z",
            "nap": False,
            "score_state": "SCORED",
            "score": {
                "sleep_performance_percentage": 91.2,
                "sleep_consistency_percentage": 84.7,
                "sleep_efficiency_percentage": 93.1,
                "respiratory_rate": 14.8,
                "stage_summary": {
                    "total_in_bed_time_milli": 28_800_000,
                    "total_awake_time_milli": 3_600_000,
                    "total_no_data_time_milli": 0,
                    "total_light_sleep_time_milli": 12_600_000,
                    "total_slow_wave_sleep_time_milli": 5_400_000,
                    "total_rem_sleep_time_milli": 5_400_000,
                    "sleep_cycle_count": 5,
                    "disturbance_count": 2,
                },
            },
        },
        date(2026, 4, 17),
    )

    assert normalized["sleep_performance"] == 91.2
    assert normalized["asleep_hours"] == 7.0
    assert normalized["sleep_cycles"] == 5


def test_normalize_recovery_record_surfaces_hrv_and_rhr() -> None:
    normalized = normalize_recovery_record(
        {
            "id": "recovery-1",
            "cycle_id": 12345,
            "sleep_id": "sleep-1",
            "created_at": "2026-04-17T13:00:00Z",
            "score_state": "SCORED",
            "score": {
                "recovery_score": 67,
                "resting_heart_rate": 55,
                "hrv_rmssd_milli": 34.6,
                "spo2_percentage": 97.1,
                "skin_temp_celsius": 33.1,
            },
        },
        date(2026, 4, 17),
    )

    assert normalized["recovery_score"] == 67
    assert normalized["cycle_id"] == 12345
    assert normalized["resting_heart_rate_bpm"] == 55
    assert normalized["hrv_rmssd_ms"] == 34.6


def test_normalize_cycle_record_surfaces_strain() -> None:
    normalized = normalize_cycle_record(
        {
            "id": 22,
            "start": "2026-04-17T12:00:00Z",
            "end": "2026-04-18T11:00:00Z",
            "score_state": "SCORED",
            "score": {
                "strain": 14.8,
                "kilojoule": 955.4,
                "average_heart_rate": 73,
                "max_heart_rate": 161,
            },
        },
        date(2026, 4, 17),
    )

    assert normalized["cycle_id"] == 22
    assert normalized["strain"] == 14.8
    assert normalized["max_heart_rate_bpm"] == 161


def test_normalize_workout_record_surfaces_duration() -> None:
    normalized = normalize_workout_record(
        {
            "id": "workout-1",
            "sport_name": "Running",
            "sport_id": 1,
            "start": "2026-04-17T15:00:00Z",
            "end": "2026-04-17T16:00:00Z",
            "score_state": "SCORED",
            "score": {
                "strain": 12.4,
                "average_heart_rate": 145,
                "max_heart_rate": 173,
                "kilojoule": 642.2,
            },
        },
    )

    assert normalized["date"] == "2026-04-17"
    assert normalized["duration_minutes"] == 60.0
    assert normalized["strain"] == 12.4
