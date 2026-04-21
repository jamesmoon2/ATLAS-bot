"""High-level WHOOP MCP tools for ATLAS."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from mcp.server.fastmcp import Context

from src.config import settings
from src.oauth_manager import get_valid_access_token
from src.whoop_api.client import WhoopClient

logger = structlog.get_logger(__name__)


DEFAULT_LOOKBACK_DAYS = 7


def _local_timezone() -> ZoneInfo:
    return ZoneInfo(settings.whoop_local_timezone)


def _parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _to_local(value: str) -> datetime:
    return _parse_iso_datetime(value).astimezone(_local_timezone())


def _round_or_none(value: float | None, digits: int = 2) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    return round(value, digits)


def _millis_to_hours(value: Any) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    return round(value / 3_600_000, 2)


def _resolve_requested_dates(
    start_date: str | None,
    end_date: str | None,
) -> tuple[list[date], datetime, datetime]:
    """Resolve requested dates and their inclusive local-time window."""
    local_tz = _local_timezone()
    today = datetime.now(local_tz).date()

    if start_date is None and end_date is None:
        end_day = today
        start_day = end_day - timedelta(days=DEFAULT_LOOKBACK_DAYS - 1)
    elif start_date is None:
        start_day = end_day = date.fromisoformat(end_date)
    elif end_date is None:
        start_day = end_day = date.fromisoformat(start_date)
    else:
        start_day = date.fromisoformat(start_date)
        end_day = date.fromisoformat(end_date)

    if end_day < start_day:
        raise ValueError("end_date must be on or after start_date")

    days = [start_day + timedelta(days=offset) for offset in range((end_day - start_day).days + 1)]
    window_start = datetime.combine(start_day, time.min, local_tz)
    window_end = datetime.combine(end_day + timedelta(days=1), time.min, local_tz)
    return days, window_start, window_end


def _overlap_seconds(
    start: datetime,
    end: datetime,
    window_start: datetime,
    window_end: datetime,
) -> float:
    latest_start = max(start, window_start)
    earliest_end = min(end, window_end)
    return max((earliest_end - latest_start).total_seconds(), 0.0)


def select_primary_sleep(records: list[dict[str, Any]], target_day: date) -> dict[str, Any] | None:
    """Return the primary WHOOP sleep record for a given local date."""
    candidates: list[tuple[float, datetime, dict[str, Any]]] = []
    for record in records:
        if record.get("nap"):
            continue
        end_value = record.get("end")
        if not isinstance(end_value, str):
            continue
        end_local = _to_local(end_value)
        if end_local.date() != target_day:
            continue
        stage_summary = (record.get("score") or {}).get("stage_summary") or {}
        in_bed_time = stage_summary.get("total_in_bed_time_milli")
        duration_score = float(in_bed_time) if isinstance(in_bed_time, (int, float)) else 0.0
        candidates.append((duration_score, end_local, record))

    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def select_recovery_for_day(
    records: list[dict[str, Any]],
    target_day: date,
) -> dict[str, Any] | None:
    """Return the WHOOP recovery record associated with a given local date."""
    candidates: list[tuple[datetime, float, dict[str, Any]]] = []
    for record in records:
        created_at = record.get("created_at")
        if not isinstance(created_at, str):
            continue
        created_local = _to_local(created_at)
        if created_local.date() != target_day:
            continue
        score = (record.get("score") or {}).get("recovery_score")
        numeric_score = float(score) if isinstance(score, (int, float)) else -1.0
        candidates.append((created_local, numeric_score, record))

    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def select_cycle_for_day(records: list[dict[str, Any]], target_day: date) -> dict[str, Any] | None:
    """Return the WHOOP cycle with the greatest overlap with the requested day."""
    local_tz = _local_timezone()
    window_start = datetime.combine(target_day, time.min, local_tz)
    window_end = window_start + timedelta(days=1)
    candidates: list[tuple[float, datetime, dict[str, Any]]] = []
    for record in records:
        start_value = record.get("start")
        end_value = record.get("end")
        if not isinstance(start_value, str) or not isinstance(end_value, str):
            continue
        start_local = _to_local(start_value)
        end_local = _to_local(end_value)
        overlap = _overlap_seconds(start_local, end_local, window_start, window_end)
        if overlap <= 0:
            continue
        candidates.append((overlap, end_local, record))

    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def normalize_sleep_record(record: dict[str, Any], target_day: date) -> dict[str, Any]:
    """Normalize a WHOOP sleep record into an ATLAS-friendly shape."""
    score = record.get("score") or {}
    stage_summary = score.get("stage_summary") or {}

    total_in_bed = stage_summary.get("total_in_bed_time_milli")
    awake_time = stage_summary.get("total_awake_time_milli")
    no_data_time = stage_summary.get("total_no_data_time_milli")
    asleep_hours = None
    if isinstance(total_in_bed, (int, float)):
        asleep_hours = float(total_in_bed)
        if isinstance(awake_time, (int, float)):
            asleep_hours -= float(awake_time)
        if isinstance(no_data_time, (int, float)):
            asleep_hours -= float(no_data_time)
        asleep_hours = round(asleep_hours / 3_600_000, 2)

    return {
        "date": target_day.isoformat(),
        "source": "whoop",
        "sleep_id": record.get("id"),
        "start": record.get("start"),
        "end": record.get("end"),
        "nap": bool(record.get("nap", False)),
        "score_state": record.get("score_state"),
        "in_bed_hours": _millis_to_hours(total_in_bed),
        "asleep_hours": asleep_hours,
        "awake_hours": _millis_to_hours(awake_time),
        "sleep_performance": _round_or_none(score.get("sleep_performance_percentage")),
        "sleep_consistency": _round_or_none(score.get("sleep_consistency_percentage")),
        "sleep_efficiency": _round_or_none(score.get("sleep_efficiency_percentage")),
        "respiratory_rate": _round_or_none(score.get("respiratory_rate")),
        "light_sleep_hours": _millis_to_hours(stage_summary.get("total_light_sleep_time_milli")),
        "slow_wave_sleep_hours": _millis_to_hours(
            stage_summary.get("total_slow_wave_sleep_time_milli"),
        ),
        "rem_sleep_hours": _millis_to_hours(stage_summary.get("total_rem_sleep_time_milli")),
        "sleep_cycles": stage_summary.get("sleep_cycle_count"),
        "disturbances": stage_summary.get("disturbance_count"),
    }


def normalize_recovery_record(record: dict[str, Any], target_day: date) -> dict[str, Any]:
    """Normalize a WHOOP recovery record into an ATLAS-friendly shape."""
    score = record.get("score") or {}
    return {
        "date": target_day.isoformat(),
        "source": "whoop",
        "recovery_id": record.get("id"),
        "cycle_id": record.get("cycle_id"),
        "sleep_id": record.get("sleep_id"),
        "created_at": record.get("created_at"),
        "start": record.get("start"),
        "end": record.get("end"),
        "score_state": record.get("score_state"),
        "recovery_score": _round_or_none(score.get("recovery_score")),
        "resting_heart_rate_bpm": _round_or_none(score.get("resting_heart_rate")),
        "hrv_rmssd_ms": _round_or_none(score.get("hrv_rmssd_milli")),
        "spo2_percentage": _round_or_none(score.get("spo2_percentage")),
        "skin_temp_celsius": _round_or_none(score.get("skin_temp_celsius")),
    }


def normalize_cycle_record(
    record: dict[str, Any],
    target_day: date,
) -> dict[str, Any]:
    """Normalize a WHOOP cycle record into an ATLAS-friendly shape."""
    score = record.get("score") or {}
    local_tz = _local_timezone()
    day_start = datetime.combine(target_day, time.min, local_tz)
    day_end = day_start + timedelta(days=1)
    start_local = _to_local(record["start"])
    end_local = _to_local(record["end"])
    overlap_hours = round(_overlap_seconds(start_local, end_local, day_start, day_end) / 3600, 2)

    return {
        "date": target_day.isoformat(),
        "source": "whoop",
        "cycle_id": record.get("id"),
        "start": record.get("start"),
        "end": record.get("end"),
        "score_state": record.get("score_state"),
        "strain": _round_or_none(score.get("strain")),
        "kilojoule": _round_or_none(score.get("kilojoule")),
        "average_heart_rate_bpm": _round_or_none(score.get("average_heart_rate")),
        "max_heart_rate_bpm": _round_or_none(score.get("max_heart_rate")),
        "overlap_hours": overlap_hours,
    }


def normalize_workout_record(record: dict[str, Any]) -> dict[str, Any]:
    """Normalize a WHOOP workout record into an ATLAS-friendly shape."""
    start_value = record.get("start")
    end_value = record.get("end")
    duration_minutes = None
    local_date = None
    if isinstance(start_value, str) and isinstance(end_value, str):
        start_local = _to_local(start_value)
        end_local = _to_local(end_value)
        duration_minutes = round((end_local - start_local).total_seconds() / 60, 2)
        local_date = start_local.date().isoformat()

    score = record.get("score") or {}
    return {
        "date": local_date,
        "source": "whoop",
        "workout_id": record.get("id"),
        "sport_name": record.get("sport_name"),
        "sport_id": record.get("sport_id"),
        "start": start_value,
        "end": end_value,
        "score_state": record.get("score_state"),
        "duration_minutes": duration_minutes,
        "strain": _round_or_none(score.get("strain")),
        "average_heart_rate_bpm": _round_or_none(score.get("average_heart_rate")),
        "max_heart_rate_bpm": _round_or_none(score.get("max_heart_rate")),
        "kilojoule": _round_or_none(score.get("kilojoule")),
        "distance_meters": _round_or_none(score.get("distance_meter")),
        "altitude_gain_meters": _round_or_none(score.get("altitude_gain_meter")),
    }


async def get_whoop_client() -> WhoopClient:
    """Return an authenticated WHOOP client."""
    return WhoopClient(access_token=get_valid_access_token())


async def get_daily_sleep_tool(
    context: Context,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Get WHOOP daily sleep data with optional date range."""
    del context
    try:
        days, window_start, window_end = _resolve_requested_dates(start_date, end_date)
        async with await get_whoop_client() as client:
            records = await client.get_sleep_collection(
                start=window_start - timedelta(days=1),
                end=window_end + timedelta(days=1),
            )
        normalized = [
            normalize_sleep_record(record, target_day)
            for target_day in days
            if (record := select_primary_sleep(records, target_day)) is not None
        ]
        return normalized or [{"error": "No WHOOP sleep data available"}]
    except Exception as exc:
        logger.error("Failed to get WHOOP daily sleep", error=str(exc))
        return [{"error": f"Failed to retrieve WHOOP sleep data: {exc}"}]


async def get_daily_recovery_tool(
    context: Context,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Get WHOOP daily recovery data with optional date range."""
    del context
    try:
        days, window_start, window_end = _resolve_requested_dates(start_date, end_date)
        async with await get_whoop_client() as client:
            records = await client.get_recovery_collection(
                start=window_start - timedelta(days=1),
                end=window_end + timedelta(days=1),
            )
        normalized = [
            normalize_recovery_record(record, target_day)
            for target_day in days
            if (record := select_recovery_for_day(records, target_day)) is not None
        ]
        return normalized or [{"error": "No WHOOP recovery data available"}]
    except Exception as exc:
        logger.error("Failed to get WHOOP daily recovery", error=str(exc))
        return [{"error": f"Failed to retrieve WHOOP recovery data: {exc}"}]


async def get_daily_cycle_tool(
    context: Context,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Get WHOOP daily cycle data with optional date range."""
    del context
    try:
        days, window_start, window_end = _resolve_requested_dates(start_date, end_date)
        async with await get_whoop_client() as client:
            records = await client.get_cycle_collection(
                start=window_start - timedelta(days=1),
                end=window_end + timedelta(days=1),
            )
        normalized = [
            normalize_cycle_record(record, target_day)
            for target_day in days
            if (record := select_cycle_for_day(records, target_day)) is not None
        ]
        return normalized or [{"error": "No WHOOP cycle data available"}]
    except Exception as exc:
        logger.error("Failed to get WHOOP daily cycle", error=str(exc))
        return [{"error": f"Failed to retrieve WHOOP cycle data: {exc}"}]


async def get_daily_workouts_tool(
    context: Context,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Get WHOOP workouts with optional date range."""
    del context
    try:
        _, window_start, window_end = _resolve_requested_dates(start_date, end_date)
        async with await get_whoop_client() as client:
            records = await client.get_workout_collection(start=window_start, end=window_end)
        workouts = [normalize_workout_record(record) for record in records]
        return sorted(
            workouts,
            key=lambda workout: (workout.get("date") or "", workout.get("start") or ""),
        )
    except Exception as exc:
        logger.error("Failed to get WHOOP workouts", error=str(exc))
        return [{"error": f"Failed to retrieve WHOOP workouts: {exc}"}]
