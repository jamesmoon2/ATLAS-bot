"""Garmin MCP tool implementations for ATLAS."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import Context

if TYPE_CHECKING:
    from src.garmin_api.client import GarminAPIClient

_api_client: Any | None = None


def set_api_client(client: GarminAPIClient) -> None:
    """Inject the Garmin API client for tool calls."""
    global _api_client
    _api_client = client


def _client() -> GarminAPIClient:
    if _api_client is None:  # pragma: no cover - startup guard
        raise RuntimeError("Garmin API client has not been initialized.")
    return _api_client


def _clean_mapping(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


def curate_activities_for_date(date: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Convert Garmin's raw per-day activity payload into a stable compact shape."""
    activities_for_day = payload.get("ActivitiesForDay")
    if not isinstance(activities_for_day, dict):
        return {"date": date, "count": 0, "activities": []}

    raw_activities = activities_for_day.get("payload")
    if not isinstance(raw_activities, list):
        return {"date": date, "count": 0, "activities": []}

    curated_activities = [
        _clean_mapping(
            {
                "id": activity.get("activityId"),
                "name": activity.get("activityName"),
                "type": (activity.get("activityType") or {}).get("typeKey"),
                "start_time": activity.get("startTimeLocal"),
                "start_time_gmt": activity.get("startTimeGMT"),
                "distance_meters": activity.get("distance"),
                "duration_seconds": activity.get("duration"),
                "calories": activity.get("calories"),
                "avg_hr_bpm": activity.get("averageHR"),
                "max_hr_bpm": activity.get("maxHR"),
                "steps": activity.get("steps"),
                "lap_count": activity.get("lapCount"),
                "moderate_intensity_minutes": activity.get("moderateIntensityMinutes"),
                "vigorous_intensity_minutes": activity.get("vigorousIntensityMinutes"),
            },
        )
        for activity in raw_activities
        if isinstance(activity, dict)
    ]

    return {
        "date": date,
        "count": len(curated_activities),
        "activities": curated_activities,
    }


def curate_activities_by_date(
    start_date: str,
    end_date: str,
    payload: list[dict[str, Any]],
    activity_type: str | None = None,
) -> dict[str, Any]:
    """Compact a date-range activity query into a stable response shape."""
    curated_activities = [
        _clean_mapping(
            {
                "id": activity.get("activityId"),
                "name": activity.get("activityName"),
                "type": (activity.get("activityType") or {}).get("typeKey"),
                "start_time": activity.get("startTimeLocal"),
                "distance_meters": activity.get("distance"),
                "duration_seconds": activity.get("duration"),
                "calories": activity.get("calories"),
                "avg_hr_bpm": activity.get("averageHR"),
                "max_hr_bpm": activity.get("maxHR"),
                "steps": activity.get("steps"),
            },
        )
        for activity in payload
    ]

    result = {
        "count": len(curated_activities),
        "date_range": {"start": start_date, "end": end_date},
        "activities": curated_activities,
    }
    if activity_type:
        result["activity_type"] = activity_type
    return result


def curate_activity(activity: dict[str, Any]) -> dict[str, Any]:
    """Compact Garmin activity detail payloads into ATLAS-friendly fields."""
    summary = activity.get("summaryDTO") or {}
    activity_type = activity.get("activityTypeDTO") or {}
    metadata = activity.get("metadataDTO") or {}

    return _clean_mapping(
        {
            "id": activity.get("activityId"),
            "name": activity.get("activityName"),
            "type": activity_type.get("typeKey"),
            "parent_type": activity_type.get("parentTypeId"),
            "start_time_local": summary.get("startTimeLocal"),
            "start_time_gmt": summary.get("startTimeGMT"),
            "duration_seconds": summary.get("duration"),
            "moving_duration_seconds": summary.get("movingDuration"),
            "elapsed_duration_seconds": summary.get("elapsedDuration"),
            "distance_meters": summary.get("distance"),
            "avg_speed_mps": summary.get("averageSpeed"),
            "max_speed_mps": summary.get("maxSpeed"),
            "avg_hr_bpm": summary.get("averageHR"),
            "max_hr_bpm": summary.get("maxHR"),
            "min_hr_bpm": summary.get("minHR"),
            "calories": summary.get("calories"),
            "bmr_calories": summary.get("bmrCalories"),
            "avg_cadence": summary.get("averageRunCadence"),
            "max_cadence": summary.get("maxRunCadence"),
            "avg_stride_length_cm": summary.get("strideLength"),
            "avg_ground_contact_time_ms": summary.get("groundContactTime"),
            "avg_vertical_oscillation_cm": summary.get("verticalOscillation"),
            "steps": summary.get("steps"),
            "avg_power_watts": summary.get("averagePower"),
            "max_power_watts": summary.get("maxPower"),
            "normalized_power_watts": summary.get("normalizedPower"),
            "training_effect": summary.get("trainingEffect"),
            "aerobic_training_effect": summary.get("aerobicTrainingEffect"),
            "anaerobic_training_effect": summary.get("anaerobicTrainingEffect"),
            "training_effect_label": summary.get("trainingEffectLabel"),
            "training_load": summary.get("activityTrainingLoad"),
            "moderate_intensity_minutes": summary.get("moderateIntensityMinutes"),
            "vigorous_intensity_minutes": summary.get("vigorousIntensityMinutes"),
            "recovery_hr_bpm": summary.get("recoveryHeartRate"),
            "body_battery_impact": summary.get("differenceBodyBattery"),
            "workout_feel": summary.get("directWorkoutFeel"),
            "workout_rpe": summary.get("directWorkoutRpe"),
            "lap_count": metadata.get("lapCount"),
            "has_splits": metadata.get("hasSplits"),
            "device_manufacturer": metadata.get("manufacturer"),
        },
    )


def curate_activity_splits(activity_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Compact Garmin activity split payloads."""
    laps = payload.get("lapDTOs")
    if not isinstance(laps, list):
        laps = []

    return {
        "activity_id": payload.get("activityId", activity_id),
        "lap_count": len(laps),
        "laps": [
            _clean_mapping(
                {
                    "lap_number": lap.get("lapIndex"),
                    "start_time": lap.get("startTimeGMT"),
                    "distance_meters": lap.get("distance"),
                    "duration_seconds": lap.get("duration"),
                    "avg_speed_mps": lap.get("averageSpeed"),
                    "max_speed_mps": lap.get("maxSpeed"),
                    "avg_hr_bpm": lap.get("averageHR"),
                    "max_hr_bpm": lap.get("maxHR"),
                    "calories": lap.get("calories"),
                    "avg_cadence": lap.get("averageRunCadence"),
                    "avg_power_watts": lap.get("averagePower"),
                    "intensity_type": lap.get("intensityType"),
                },
            )
            for lap in laps
            if isinstance(lap, dict)
        ],
    }


def curate_hr_time_in_zones(activity_id: int, payload: list[dict[str, Any]]) -> dict[str, Any]:
    """Compact Garmin HR zone payloads."""
    return {
        "activity_id": activity_id,
        "zones": [
            _clean_mapping(
                {
                    "zone": entry.get("zoneNumber"),
                    "seconds": entry.get("secsInZone"),
                    "low_boundary_bpm": entry.get("zoneLowBoundary"),
                    "high_boundary_bpm": entry.get("zoneHighBoundary"),
                },
            )
            for entry in payload
            if isinstance(entry, dict)
        ],
    }


def curate_stats(date: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Compact Garmin daily stats into an ATLAS-friendly summary."""
    return _clean_mapping(
        {
            "date": payload.get("calendarDate", date),
            "total_steps": payload.get("totalSteps"),
            "daily_step_goal": payload.get("dailyStepGoal"),
            "distance_meters": payload.get("totalDistanceMeters"),
            "floors_ascended": payload.get("floorsAscended"),
            "floors_descended": payload.get("floorsDescended"),
            "total_calories": payload.get("totalKilocalories"),
            "active_calories": payload.get("activeKilocalories"),
            "bmr_calories": payload.get("bmrKilocalories"),
            "highly_active_seconds": payload.get("highlyActiveSeconds"),
            "active_seconds": payload.get("activeSeconds"),
            "sedentary_seconds": payload.get("sedentarySeconds"),
            "sleeping_seconds": payload.get("sleepingSeconds"),
            "moderate_intensity_minutes": payload.get("moderateIntensityMinutes"),
            "vigorous_intensity_minutes": payload.get("vigorousIntensityMinutes"),
            "intensity_minutes_goal": payload.get("intensityMinutesGoal"),
            "min_heart_rate_bpm": payload.get("minHeartRate"),
            "max_heart_rate_bpm": payload.get("maxHeartRate"),
            "resting_heart_rate_bpm": payload.get("restingHeartRate"),
            "last_7_days_avg_resting_hr": payload.get("lastSevenDaysAvgRestingHeartRate"),
            "avg_stress_level": payload.get("averageStressLevel"),
            "max_stress_level": payload.get("maxStressLevel"),
            "stress_qualifier": payload.get("stressQualifier"),
            "body_battery_charged": payload.get("bodyBatteryChargedValue"),
            "body_battery_drained": payload.get("bodyBatteryDrainedValue"),
            "body_battery_highest": payload.get("bodyBatteryHighestValue"),
            "body_battery_lowest": payload.get("bodyBatteryLowestValue"),
            "body_battery_current": payload.get("bodyBatteryMostRecentValue"),
            "avg_spo2_percent": payload.get("averageSpo2"),
            "lowest_spo2_percent": payload.get("lowestSpo2"),
            "avg_waking_respiration": payload.get("avgWakingRespirationValue"),
            "highest_respiration": payload.get("highestRespirationValue"),
            "lowest_respiration": payload.get("lowestRespirationValue"),
        },
    )


def curate_sleep_data(date: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Compact Garmin sleep payloads."""
    daily_sleep = payload.get("dailySleepDTO") or {}
    return _clean_mapping(
        {
            "date": date,
            "sleep_time_seconds": daily_sleep.get("sleepTimeSeconds"),
            "sleep_start_local": daily_sleep.get("sleepStartTimestampLocal"),
            "sleep_end_local": daily_sleep.get("sleepEndTimestampLocal"),
            "avg_heart_rate_bpm": daily_sleep.get("avgHeartRate"),
            "sleep_score": ((daily_sleep.get("sleepScores") or {}).get("overall") or {}).get(
                "value",
            ),
            "sleep_efficiency": daily_sleep.get("sleepEfficiency"),
            "restless_moment_count": daily_sleep.get("restlessMomentsCount"),
            "awake_count": daily_sleep.get("awakeCount"),
            "unmeasurable_sleep_seconds": daily_sleep.get("unmeasurableSleepSeconds"),
        },
    )


def curate_hrv_data(date: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    """Compact Garmin HRV payloads."""
    if not payload:
        return {"date": date}
    summary = payload.get("hrvSummary") or {}
    return _clean_mapping(
        {
            "date": date,
            "status": summary.get("status"),
            "weekly_avg": summary.get("weeklyAvg"),
            "last_night_avg": summary.get("lastNightAvg"),
            "last_night_high_5_min": summary.get("lastNight5MinHigh"),
        },
    )


def curate_training_readiness(
    date: str,
    payload: dict[str, Any] | list[dict[str, Any]],
) -> dict[str, Any]:
    """Compact Garmin training readiness payloads."""
    entries = payload if isinstance(payload, list) else [payload]
    curated_entries = [
        _clean_mapping(
            {
                "date": entry.get("calendarDate", date),
                "timestamp": entry.get("timestampLocal"),
                "context": entry.get("inputContext"),
                "level": entry.get("level"),
                "score": entry.get("score"),
                "feedback": entry.get("feedbackShort"),
                "sleep_score": entry.get("sleepScore"),
                "sleep_factor_percent": entry.get("sleepScoreFactorPercent"),
                "sleep_factor_feedback": entry.get("sleepScoreFactorFeedback"),
                "recovery_time_minutes": entry.get("recoveryTime"),
                "recovery_factor_percent": entry.get("recoveryTimeFactorPercent"),
                "recovery_factor_feedback": entry.get("recoveryTimeFactorFeedback"),
                "training_load_factor_percent": entry.get("acwrFactorPercent"),
                "training_load_feedback": entry.get("acwrFactorFeedback"),
                "acute_load": entry.get("acuteLoad"),
                "hrv_factor_percent": entry.get("hrvFactorPercent"),
                "hrv_factor_feedback": entry.get("hrvFactorFeedback"),
                "hrv_weekly_avg": entry.get("hrvWeeklyAverage"),
                "stress_history_factor_percent": entry.get("stressHistoryFactorPercent"),
                "stress_history_feedback": entry.get("stressHistoryFactorFeedback"),
                "sleep_history_factor_percent": entry.get("sleepHistoryFactorPercent"),
                "sleep_history_feedback": entry.get("sleepHistoryFactorFeedback"),
            },
        )
        for entry in entries
        if isinstance(entry, dict)
    ]
    return {"date": date, "entries": curated_entries}


def curate_body_battery(
    start_date: str,
    end_date: str,
    payload: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compact Garmin body battery daily report payloads."""
    return {
        "start_date": start_date,
        "end_date": end_date,
        "days": [
            _clean_mapping(
                {
                    "date": entry.get("calendarDate"),
                    "body_battery_high": entry.get("bodyBatteryHighestValue"),
                    "body_battery_low": entry.get("bodyBatteryLowestValue"),
                    "body_battery_charged": entry.get("bodyBatteryChargedValue"),
                    "body_battery_drained": entry.get("bodyBatteryDrainedValue"),
                    "body_battery_end": entry.get("bodyBatteryMostRecentValue"),
                },
            )
            for entry in payload
            if isinstance(entry, dict)
        ],
    }


def curate_body_battery_events(date: str, payload: list[dict[str, Any]]) -> dict[str, Any]:
    """Compact Garmin body battery event payloads."""
    return {
        "date": date,
        "events": [
            _clean_mapping(
                {
                    "activity_id": entry.get("activityId"),
                    "event_type": (entry.get("event") or {}).get("eventType"),
                    "body_battery_impact": (entry.get("event") or {}).get("bodyBatteryImpact"),
                    "start_timestamp_local": (entry.get("event") or {}).get("startTimestampLocal"),
                    "end_timestamp_local": (entry.get("event") or {}).get("endTimestampLocal"),
                },
            )
            for entry in payload
            if isinstance(entry, dict)
        ],
    }


async def get_activities_fordate_tool(context: Context, date: str) -> dict[str, Any]:
    """Get activities for a specific date in Garmin Connect."""
    del context
    return curate_activities_for_date(date, _client().get_activities_fordate(date))


async def get_activities_by_date_tool(
    context: Context,
    start_date: str,
    end_date: str,
    activity_type: str = "",
) -> dict[str, Any]:
    """Get activities between two dates with an optional Garmin activity type filter."""
    del context
    normalized_type = activity_type or None
    return curate_activities_by_date(
        start_date,
        end_date,
        _client().get_activities_by_date(start_date, end_date, normalized_type),
        normalized_type,
    )


async def get_activity_tool(context: Context, activity_id: int) -> dict[str, Any]:
    """Get Garmin activity details for a specific activity id."""
    del context
    return curate_activity(_client().get_activity(activity_id))


async def get_activity_splits_tool(context: Context, activity_id: int) -> dict[str, Any]:
    """Get Garmin activity split details for a specific activity id."""
    del context
    return curate_activity_splits(activity_id, _client().get_activity_splits(activity_id))


async def get_activity_hr_in_timezones_tool(context: Context, activity_id: int) -> dict[str, Any]:
    """Get time spent in heart-rate zones for an activity."""
    del context
    return curate_hr_time_in_zones(activity_id, _client().get_activity_hr_in_timezones(activity_id))


async def get_stats_tool(context: Context, date: str) -> dict[str, Any]:
    """Get Garmin daily stats for a date."""
    del context
    return curate_stats(date, _client().get_stats(date))


async def get_sleep_data_tool(context: Context, date: str) -> dict[str, Any]:
    """Get Garmin sleep data for a date."""
    del context
    return curate_sleep_data(date, _client().get_sleep_data(date))


async def get_hrv_data_tool(context: Context, date: str) -> dict[str, Any]:
    """Get Garmin HRV data for a date."""
    del context
    return curate_hrv_data(date, _client().get_hrv_data(date))


async def get_training_readiness_tool(context: Context, date: str) -> dict[str, Any]:
    """Get Garmin training readiness data for a date."""
    del context
    return curate_training_readiness(date, _client().get_training_readiness(date))


async def get_body_battery_tool(
    context: Context,
    start_date: str,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Get Garmin daily body battery summaries for a date or date range."""
    del context
    resolved_end = end_date or start_date
    return curate_body_battery(
        start_date,
        resolved_end,
        _client().get_body_battery(start_date, resolved_end),
    )


async def get_body_battery_events_tool(context: Context, date: str) -> dict[str, Any]:
    """Get Garmin body battery events for a date."""
    del context
    return curate_body_battery_events(date, _client().get_body_battery_events(date))


async def get_profile_tool(context: Context) -> dict[str, str | None]:
    """Verify Garmin auth and return a minimal profile identity."""
    del context
    return {"full_name": _client().get_full_name()}
