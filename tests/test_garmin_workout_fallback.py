"""Tests for the repo-native Garmin workout fallback."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

import garmin_workout_fallback as garmin_fallback


class _FakeGarminClient:
    def __init__(self, responses: dict[str, object], *, profile: dict[str, object] | None = None):
        self._responses = responses
        self._profile = profile or {"displayName": "display-name"}

    @property
    def profile(self) -> dict[str, object]:
        return self._profile

    def connectapi(self, path: str, method: str = "GET", **kwargs: object) -> object:
        del method, kwargs
        response = self._responses[path]
        if isinstance(response, Exception):
            raise response
        return response


def test_fetch_workout_snapshot_success_path(tmp_path):
    client = _FakeGarminClient(
        {
            "/mobile-gateway/heartRate/forDate/2026-04-15": {
                "ActivitiesForDay": {
                    "payload": [
                        {
                            "activityId": 111,
                            "activityName": "Morning Walk",
                            "startTimeLocal": "2026-04-15T06:00:00.0",
                            "startTimeGMT": "2026-04-15T13:00:00.0",
                            "activityType": {"typeKey": "walking"},
                            "duration": 1200,
                            "averageHR": 95,
                            "calories": 120,
                        },
                        {
                            "activityId": 222,
                            "activityName": "Strength",
                            "startTimeLocal": "2026-04-15T18:30:00.0",
                            "startTimeGMT": "2026-04-16T01:30:00.0",
                            "activityType": {"typeKey": "strength_training"},
                            "duration": 2635.765,
                            "averageHR": 117,
                            "calories": 397,
                        },
                    ]
                }
            },
            "/activity-service/activity/222": {
                "activityId": 222,
                "activityName": "Strength",
                "activityTypeDTO": {"typeKey": "strength_training"},
                "summaryDTO": {
                    "startTimeLocal": "2026-04-15T18:30:00.0",
                    "startTimeGMT": "2026-04-16T01:30:00.0",
                    "duration": 2635.765,
                    "calories": 397,
                    "averageHR": 117,
                    "maxHR": 169,
                    "trainingEffect": 2.4,
                    "aerobicTrainingEffect": 2.4,
                    "anaerobicTrainingEffect": 2.1,
                    "trainingEffectLabel": "ANAEROBIC_CAPACITY",
                    "activityTrainingLoad": 66.07,
                    "differenceBodyBattery": -5,
                },
            },
            "/metrics-service/metrics/trainingreadiness/2026-04-15": [
                {
                    "score": 44,
                    "level": "LOW",
                    "timestampLocal": "2026-04-15T19:15:00.0",
                    "recoveryTime": 720,
                    "acuteLoad": 240,
                    "sleepScore": 67,
                    "hrvWeeklyAverage": 27,
                    "inputContext": "AFTER_POST_EXERCISE_RESET",
                },
                {
                    "score": 58,
                    "level": "MODERATE",
                    "timestampLocal": "2026-04-15T06:01:00.0",
                    "recoveryTime": 1,
                    "acuteLoad": 155,
                    "sleepScore": 67,
                    "hrvWeeklyAverage": 27,
                    "inputContext": "AFTER_WAKEUP_RESET",
                },
            ],
            "/hrv-service/hrv/2026-04-15": {
                "hrvSummary": {
                    "status": "BALANCED",
                    "weeklyAvg": 27,
                    "lastNightAvg": 29,
                    "lastNight5MinHigh": 45,
                }
            },
            "/wellness-service/wellness/dailySleepData/display-name": {
                "dailySleepDTO": {
                    "sleepTimeSeconds": 26040,
                    "sleepStartTimestampLocal": "2026-04-14T22:00:00.0",
                    "sleepEndTimestampLocal": "2026-04-15T05:14:00.0",
                    "avgHeartRate": 74,
                    "sleepScores": {"overall": {"value": 67}},
                }
            },
            "/activity-service/activity/222/hrTimeInZones": [
                {"zoneNumber": 1, "secsInZone": 364.392, "zoneLowBoundary": 92},
                {"zoneNumber": 2, "secsInZone": 1089.36, "zoneLowBoundary": 110},
            ],
            "/wellness-service/wellness/bodyBattery/events/2026-04-15": [
                {
                    "activityId": 222,
                    "event": {"bodyBatteryImpact": -5},
                }
            ],
        }
    )

    snapshot = garmin_fallback.fetch_workout_snapshot(
        activity_date="2026-04-15",
        auth_home=tmp_path,
        client=client,
    )

    assert snapshot.activity_id == 222
    assert snapshot.activity_name == "Strength"
    assert snapshot.activity_type == "strength_training"
    assert snapshot.start_time == "2026-04-15T18:30:00.0"
    assert snapshot.duration_seconds == pytest.approx(2635.765)
    assert snapshot.duration_human == "43:56"
    assert snapshot.average_heart_rate == pytest.approx(117.0)
    assert snapshot.max_heart_rate == pytest.approx(169.0)
    assert snapshot.calories == pytest.approx(397.0)
    assert snapshot.aerobic_training_effect == pytest.approx(2.4)
    assert snapshot.anaerobic_training_effect == pytest.approx(2.1)
    assert snapshot.training_load == pytest.approx(66.07)
    assert snapshot.body_battery_impact == -5
    assert snapshot.readiness is not None
    assert snapshot.readiness.score == 58
    assert snapshot.readiness.level == "MODERATE"
    assert snapshot.hrv is not None
    assert snapshot.hrv.status == "BALANCED"
    assert snapshot.sleep is not None
    assert snapshot.sleep.score == 67
    assert [zone.zone for zone in snapshot.hr_zones] == [1, 2]
    assert snapshot.selected_from_count == 2
    assert snapshot.warnings == []


def test_fetch_workout_snapshot_missing_tokens_fails_fast(tmp_path):
    with pytest.raises(garmin_fallback.GarminTokensMissingError) as exc_info:
        garmin_fallback.fetch_workout_snapshot(activity_date="2026-04-15", auth_home=tmp_path)

    assert "oauth1_token.json" in str(exc_info.value)
    assert exc_info.value.hint is not None


def test_build_client_ignores_stale_refresh_metadata(tmp_path, monkeypatch):
    auth_home = Path(tmp_path)
    (auth_home / "oauth1_token.json").write_text(
        json.dumps({"oauth_token": "a", "oauth_token_secret": "b"}),
        encoding="utf-8",
    )
    (auth_home / "oauth2_token.json").write_text(
        json.dumps({"refresh_token_expires_at": time.time() - 30}),
        encoding="utf-8",
    )

    class _LoadedClient:
        def load(self, path: str) -> None:
            assert path == str(auth_home)

    class _FakeGarthHttp:
        @staticmethod
        def Client() -> _LoadedClient:
            return _LoadedClient()

    def fake_import_module(name: str):
        assert name == "garth.http"
        return _FakeGarthHttp

    monkeypatch.setattr(garmin_fallback.importlib, "import_module", fake_import_module)

    client = garmin_fallback._build_client(auth_home)

    assert isinstance(client, _LoadedClient)


def test_choose_garmin_workout_source_prefers_mcp_tools(tmp_path):
    plan = garmin_fallback.choose_garmin_workout_source(
        ["Read", "mcp__garmin__get_activity"],
        bot_dir=str(tmp_path),
    )

    assert plan.mode == "mcp"
    assert plan.mcp_tools == garmin_fallback.GARMIN_ACTIVITY_TOOL_NAMES
    assert plan.fallback_command == ()


def test_choose_garmin_workout_source_falls_back_to_repo_helper(tmp_path):
    plan = garmin_fallback.choose_garmin_workout_source(
        ["Read", "Write"],
        bot_dir=str(tmp_path),
    )

    assert plan.mode == "fallback"
    assert plan.mcp_tools == ()
    assert plan.fallback_command == (
        "python3",
        str(tmp_path / "garmin_workout_fallback.py"),
    )
