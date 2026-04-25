#!/usr/bin/env python3
"""ATLAS Garmin workout fallback for sessions without direct Garmin MCP tools."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import warnings
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

REPO_GARMIN_AUTH_HOME = (
    Path(__file__).resolve().parent / "mcp-servers" / "credentials" / "garminconnect"
)
LEGACY_GARMIN_AUTH_HOME = Path.home() / ".garminconnect"


def _resolve_default_auth_home() -> Path:
    explicit = os.getenv("GARMIN_TOKEN_DIR")
    if explicit:
        return Path(explicit).expanduser()
    if (REPO_GARMIN_AUTH_HOME / "oauth1_token.json").exists() and (
        REPO_GARMIN_AUTH_HOME / "oauth2_token.json"
    ).exists():
        return REPO_GARMIN_AUTH_HOME
    return LEGACY_GARMIN_AUTH_HOME


DEFAULT_GARMIN_AUTH_HOME = _resolve_default_auth_home()
GARMIN_ACTIVITY_TOOL_NAMES = (
    "mcp__garmin__get_activities_fordate",
    "mcp__garmin__get_activity",
)
GARMIN_TOOL_PREFIX = "mcp__garmin__"
READINESS_MORNING_CONTEXT = "AFTER_WAKEUP_RESET"


class GarminFallbackError(RuntimeError):
    """Base error for repo-native Garmin workout lookups."""

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint


class GarminDependencyError(GarminFallbackError):
    """Raised when the local Garmin dependency is unavailable."""


class GarminTokensMissingError(GarminFallbackError):
    """Raised when the local Garmin token store is missing."""


class GarminTokensExpiredError(GarminFallbackError):
    """Raised when the local Garmin tokens can no longer be refreshed."""


class GarminActivityNotFoundError(GarminFallbackError):
    """Raised when no activity matches the requested lookup."""


class GarminClientProtocol(Protocol):
    """Minimal Garmin client contract used by the fallback helper."""

    @property
    def profile(self) -> dict[str, Any]: ...

    def connectapi(
        self,
        path: str,
        method: str = "GET",
        **kwargs: Any,
    ) -> dict[str, Any] | list[dict[str, Any]] | None: ...


@dataclass(frozen=True)
class GarminWorkoutSourcePlan:
    """Describe how a session should obtain Garmin workout data."""

    mode: str
    mcp_tools: tuple[str, ...] = ()
    fallback_command: tuple[str, ...] = ()


@dataclass
class GarminHeartRateZone:
    zone: int | None
    seconds: float | None
    low_boundary_bpm: int | None


@dataclass
class GarminReadinessSummary:
    score: int | None
    level: str | None
    timestamp_local: str | None
    recovery_time_minutes: int | None
    acute_load: int | None
    sleep_score: int | None
    hrv_weekly_average: int | None


@dataclass
class GarminHrvSummary:
    status: str | None
    weekly_avg: int | None
    last_night_avg: int | None
    last_night_high_5_min: int | None


@dataclass
class GarminSleepSummary:
    score: int | None
    duration_seconds: int | None
    start_time_local: str | None
    end_time_local: str | None
    average_heart_rate: float | None


@dataclass
class GarminWorkoutSnapshot:
    source: str
    date: str
    activity_id: int
    activity_name: str | None
    activity_type: str | None
    start_time: str | None
    start_time_gmt: str | None
    duration_seconds: float | None
    duration_human: str | None
    average_heart_rate: float | None
    max_heart_rate: float | None
    calories: float | None
    training_effect_label: str | None
    overall_training_effect: float | None
    aerobic_training_effect: float | None
    anaerobic_training_effect: float | None
    training_load: float | None
    body_battery_impact: int | None
    readiness: GarminReadinessSummary | None
    hrv: GarminHrvSummary | None
    sleep: GarminSleepSummary | None
    hr_zones: list[GarminHeartRateZone] = field(default_factory=list)
    selected_from_count: int = 1
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized workout snapshot to JSON."""
        return asdict(self)


def choose_garmin_workout_source(
    available_tools: Sequence[str],
    *,
    bot_dir: str,
) -> GarminWorkoutSourcePlan:
    """Choose the workout data source for a session."""
    if any(tool.startswith(GARMIN_TOOL_PREFIX) for tool in available_tools):
        return GarminWorkoutSourcePlan(
            mode="mcp",
            mcp_tools=GARMIN_ACTIVITY_TOOL_NAMES,
        )

    return GarminWorkoutSourcePlan(
        mode="fallback",
        fallback_command=("python3", str(Path(bot_dir) / "garmin_workout_fallback.py")),
    )


def _today_local_date() -> str:
    return datetime.now().astimezone().date().isoformat()


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _format_duration(duration_seconds: float | None) -> str | None:
    if duration_seconds is None:
        return None
    total_seconds = max(int(round(duration_seconds)), 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:d}:{seconds:02d}"


def _load_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_auth_files(auth_home: Path) -> None:
    required_files = [auth_home / "oauth1_token.json", auth_home / "oauth2_token.json"]
    missing_files = [path.name for path in required_files if not path.exists()]
    if missing_files:
        raise GarminTokensMissingError(
            (f"Garmin tokens were not found in {auth_home}. Missing: {', '.join(missing_files)}."),
            hint="Reauthenticate the local Garmin integration so the configured token directory is repopulated.",
        )


def _build_client(auth_home: Path) -> GarminClientProtocol:
    _ensure_auth_files(auth_home)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            garth_http = importlib.import_module("garth.http")
    except ModuleNotFoundError as exc:
        raise GarminDependencyError(
            "The `garth` package is not installed in the ATLAS environment.",
            hint="Install the project dependencies so the Garmin fallback can use ~/.garminconnect.",
        ) from exc

    client = garth_http.Client()
    try:
        # Garmin can exchange a fresh OAuth2 access token from the stored OAuth1 token,
        # so we trust the real client load/request path instead of cached refresh metadata.
        client.load(str(auth_home))
    except Exception as exc:  # pragma: no cover - exercised via higher-level tests
        raise GarminTokensExpiredError(
            f"Garmin auth in {auth_home} could not be loaded cleanly: {exc}",
            hint="Refresh the local Garmin login so the configured token directory contains a valid session.",
        ) from exc

    return client


def _is_auth_error(message: str) -> bool:
    lowered = message.lower()
    markers = (
        "401",
        "403",
        "authentication",
        "unauthorized",
        "forbidden",
        "invalid token",
        "expired",
    )
    return any(marker in lowered for marker in markers)


def _connectapi(
    client: GarminClientProtocol,
    path: str,
    *,
    auth_home: Path,
    optional: bool = False,
    **kwargs: Any,
) -> dict[str, Any] | list[dict[str, Any]] | None:
    try:
        return client.connectapi(path, **kwargs)
    except Exception as exc:
        message = str(exc)
        if _is_auth_error(message):
            raise GarminTokensExpiredError(
                f"Garmin auth in {auth_home} is no longer valid: {message}",
                hint="Refresh the local Garmin login so the configured token directory contains a valid session.",
            ) from exc
        if optional and ("404" in message or "not found" in message.lower()):
            return None
        raise GarminFallbackError(f"Garmin request failed for {path}: {message}") from exc


def _extract_activity_entries(
    day_payload: dict[str, Any] | list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if isinstance(day_payload, list):
        return [entry for entry in day_payload if isinstance(entry, dict)]
    if not isinstance(day_payload, dict):
        return []

    activities_for_day = day_payload.get("ActivitiesForDay")
    if isinstance(activities_for_day, dict):
        payload = activities_for_day.get("payload")
        if isinstance(payload, list):
            return [entry for entry in payload if isinstance(entry, dict)]

    payload = day_payload.get("payload")
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, dict)]
    return []


def _activity_sort_key(activity: dict[str, Any]) -> str:
    return str(_coalesce(activity.get("startTimeGMT"), activity.get("startTimeLocal"), ""))


def _select_activity_summary(
    activities: list[dict[str, Any]],
    *,
    activity_id: int | None,
    activity_date: str,
) -> dict[str, Any]:
    if activity_id is not None:
        for activity in activities:
            if _safe_int(activity.get("activityId")) == activity_id:
                return activity
        raise GarminActivityNotFoundError(
            f"Garmin activity {activity_id} was not found on {activity_date}.",
        )

    if not activities:
        raise GarminActivityNotFoundError(
            f"No Garmin activities were found on {activity_date}.",
        )

    return max(activities, key=_activity_sort_key)


def _resolve_activity_date(
    activity_summary: dict[str, Any],
    activity_detail: dict[str, Any],
    requested_date: str | None,
) -> str:
    if requested_date:
        return requested_date

    summary_dto = activity_detail.get("summaryDTO")
    start_time = None
    if isinstance(summary_dto, dict):
        start_time = _coalesce(summary_dto.get("startTimeLocal"), summary_dto.get("startTimeGMT"))
    start_time = _coalesce(
        start_time,
        activity_summary.get("startTimeLocal"),
        activity_summary.get("startTimeGMT"),
    )

    if isinstance(start_time, str) and "T" in start_time:
        return start_time.split("T", 1)[0]

    return _today_local_date()


def _select_readiness_entry(
    payload: dict[str, Any] | list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    if isinstance(payload, dict):
        return payload
    if not isinstance(payload, list) or not payload:
        return None

    morning_entry = next(
        (
            entry
            for entry in payload
            if isinstance(entry, dict) and entry.get("inputContext") == READINESS_MORNING_CONTEXT
        ),
        None,
    )
    if morning_entry is not None:
        return morning_entry

    valid_entries = [entry for entry in payload if isinstance(entry, dict)]
    if not valid_entries:
        return None
    return min(
        valid_entries,
        key=lambda entry: str(entry.get("timestampLocal") or entry.get("timestamp") or ""),
    )


def _normalize_readiness(
    payload: dict[str, Any] | list[dict[str, Any]] | None,
) -> GarminReadinessSummary | None:
    entry = _select_readiness_entry(payload)
    if entry is None:
        return None

    recovery_time_minutes = None
    recovery_time = _safe_float(entry.get("recoveryTime"))
    if recovery_time is not None:
        recovery_time_minutes = int(round(recovery_time))

    return GarminReadinessSummary(
        score=_safe_int(entry.get("score")),
        level=entry.get("level"),
        timestamp_local=_coalesce(entry.get("timestampLocal"), entry.get("timestamp")),
        recovery_time_minutes=recovery_time_minutes,
        acute_load=_safe_int(entry.get("acuteLoad")),
        sleep_score=_safe_int(entry.get("sleepScore")),
        hrv_weekly_average=_safe_int(entry.get("hrvWeeklyAverage")),
    )


def _normalize_hrv(
    payload: dict[str, Any] | list[dict[str, Any]] | None,
) -> GarminHrvSummary | None:
    if not isinstance(payload, dict):
        return None
    summary = payload.get("hrvSummary")
    if not isinstance(summary, dict):
        return None

    return GarminHrvSummary(
        status=summary.get("status"),
        weekly_avg=_safe_int(summary.get("weeklyAvg")),
        last_night_avg=_safe_int(summary.get("lastNightAvg")),
        last_night_high_5_min=_safe_int(summary.get("lastNight5MinHigh")),
    )


def _normalize_sleep(
    payload: dict[str, Any] | list[dict[str, Any]] | None,
) -> GarminSleepSummary | None:
    if not isinstance(payload, dict):
        return None
    sleep_dto = payload.get("dailySleepDTO")
    if not isinstance(sleep_dto, dict):
        return None

    sleep_scores = sleep_dto.get("sleepScores")
    overall_score = None
    if isinstance(sleep_scores, dict):
        overall = sleep_scores.get("overall")
        if isinstance(overall, dict):
            overall_score = _safe_int(overall.get("value"))

    return GarminSleepSummary(
        score=overall_score,
        duration_seconds=_safe_int(sleep_dto.get("sleepTimeSeconds")),
        start_time_local=sleep_dto.get("sleepStartTimestampLocal"),
        end_time_local=sleep_dto.get("sleepEndTimestampLocal"),
        average_heart_rate=_safe_float(sleep_dto.get("avgHeartRate")),
    )


def _normalize_hr_zones(
    payload: dict[str, Any] | list[dict[str, Any]] | None,
) -> list[GarminHeartRateZone]:
    if not isinstance(payload, list):
        return []

    normalized_zones: list[GarminHeartRateZone] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        normalized_zones.append(
            GarminHeartRateZone(
                zone=_safe_int(entry.get("zoneNumber")),
                seconds=_safe_float(entry.get("secsInZone")),
                low_boundary_bpm=_safe_int(entry.get("zoneLowBoundary")),
            )
        )

    return normalized_zones


def _best_effort(fetcher: Any, warnings_list: list[str], warning_prefix: str) -> Any:
    try:
        return fetcher()
    except GarminTokensExpiredError:
        raise
    except GarminFallbackError as exc:
        warnings_list.append(f"{warning_prefix}: {exc}")
        return None


def _resolve_body_battery_impact(
    client: GarminClientProtocol,
    *,
    activity_id: int,
    activity_date: str,
    auth_home: Path,
    fallback_value: int | None,
) -> int | None:
    body_events = _connectapi(
        client,
        f"/wellness-service/wellness/bodyBattery/events/{activity_date}",
        auth_home=auth_home,
        optional=True,
    )
    if isinstance(body_events, list):
        for event in body_events:
            if not isinstance(event, dict):
                continue
            if _safe_int(event.get("activityId")) != activity_id:
                continue
            event_payload = event.get("event")
            if isinstance(event_payload, dict):
                impact = _safe_int(event_payload.get("bodyBatteryImpact"))
                if impact is not None:
                    return impact
    return fallback_value


def fetch_workout_snapshot(
    *,
    activity_date: str | None = None,
    activity_id: int | None = None,
    auth_home: str | Path = DEFAULT_GARMIN_AUTH_HOME,
    client: GarminClientProtocol | None = None,
) -> GarminWorkoutSnapshot:
    """Fetch normalized Garmin workout data using the repo-native fallback."""
    resolved_auth_home = Path(auth_home).expanduser()
    resolved_date = activity_date or _today_local_date()
    resolved_client = client or _build_client(resolved_auth_home)

    daily_payload = _connectapi(
        resolved_client,
        f"/mobile-gateway/heartRate/forDate/{resolved_date}",
        auth_home=resolved_auth_home,
    )
    activities = _extract_activity_entries(daily_payload)
    selected_activity = _select_activity_summary(
        activities,
        activity_id=activity_id,
        activity_date=resolved_date,
    )

    resolved_activity_id = _safe_int(selected_activity.get("activityId"))
    if resolved_activity_id is None:
        raise GarminFallbackError(
            f"Garmin activity data for {resolved_date} did not include a valid activity id."
        )

    activity_detail = _connectapi(
        resolved_client,
        f"/activity-service/activity/{resolved_activity_id}",
        auth_home=resolved_auth_home,
    )
    if not isinstance(activity_detail, dict):
        raise GarminFallbackError(
            f"Garmin returned an unexpected payload for {resolved_activity_id}."
        )

    resolved_date = _resolve_activity_date(selected_activity, activity_detail, activity_date)

    summary_dto = activity_detail.get("summaryDTO")
    if not isinstance(summary_dto, dict):
        summary_dto = {}

    warnings_list: list[str] = []
    readiness = _best_effort(
        lambda: _normalize_readiness(
            _connectapi(
                resolved_client,
                f"/metrics-service/metrics/trainingreadiness/{resolved_date}",
                auth_home=resolved_auth_home,
                optional=True,
            )
        ),
        warnings_list,
        "Training readiness unavailable",
    )
    hrv = _best_effort(
        lambda: _normalize_hrv(
            _connectapi(
                resolved_client,
                f"/hrv-service/hrv/{resolved_date}",
                auth_home=resolved_auth_home,
                optional=True,
            )
        ),
        warnings_list,
        "HRV unavailable",
    )

    profile = {}
    try:
        profile = resolved_client.profile
    except Exception as exc:
        if _is_auth_error(str(exc)):
            raise GarminTokensExpiredError(
                f"Garmin auth in {resolved_auth_home} is no longer valid: {exc}",
                hint="Refresh the local Garmin login so the configured token directory contains a valid session.",
            ) from exc
        warnings_list.append(f"Garmin profile unavailable: {exc}")

    sleep = None
    display_name = profile.get("displayName") if isinstance(profile, dict) else None
    if isinstance(display_name, str) and display_name:
        sleep = _best_effort(
            lambda: _normalize_sleep(
                _connectapi(
                    resolved_client,
                    f"/wellness-service/wellness/dailySleepData/{display_name}",
                    auth_home=resolved_auth_home,
                    optional=True,
                    params={"date": resolved_date, "nonSleepBufferMinutes": 60},
                )
            ),
            warnings_list,
            "Sleep unavailable",
        )
    else:
        warnings_list.append("Sleep unavailable: Garmin profile did not include a display name.")

    hr_zones = _best_effort(
        lambda: (
            _normalize_hr_zones(
                _connectapi(
                    resolved_client,
                    f"/activity-service/activity/{resolved_activity_id}/hrTimeInZones",
                    auth_home=resolved_auth_home,
                    optional=True,
                )
            )
            or []
        ),
        warnings_list,
        "Heart-rate zones unavailable",
    )
    if hr_zones is None:
        hr_zones = []

    body_battery_impact = _best_effort(
        lambda: _resolve_body_battery_impact(
            resolved_client,
            activity_id=resolved_activity_id,
            activity_date=resolved_date,
            auth_home=resolved_auth_home,
            fallback_value=_safe_int(summary_dto.get("differenceBodyBattery")),
        ),
        warnings_list,
        "Body battery impact unavailable",
    )

    duration_seconds = _safe_float(
        _coalesce(summary_dto.get("duration"), selected_activity.get("duration"))
    )

    return GarminWorkoutSnapshot(
        source="atlas_garmin_fallback",
        date=resolved_date,
        activity_id=resolved_activity_id,
        activity_name=_coalesce(
            activity_detail.get("activityName"), selected_activity.get("activityName")
        ),
        activity_type=_coalesce(
            activity_detail.get("activityTypeDTO", {}).get("typeKey")
            if isinstance(activity_detail.get("activityTypeDTO"), dict)
            else None,
            selected_activity.get("activityType", {}).get("typeKey")
            if isinstance(selected_activity.get("activityType"), dict)
            else None,
        ),
        start_time=_coalesce(
            summary_dto.get("startTimeLocal"),
            selected_activity.get("startTimeLocal"),
        ),
        start_time_gmt=_coalesce(
            summary_dto.get("startTimeGMT"),
            selected_activity.get("startTimeGMT"),
        ),
        duration_seconds=duration_seconds,
        duration_human=_format_duration(duration_seconds),
        average_heart_rate=_safe_float(
            _coalesce(summary_dto.get("averageHR"), selected_activity.get("averageHR"))
        ),
        max_heart_rate=_safe_float(summary_dto.get("maxHR")),
        calories=_safe_float(
            _coalesce(summary_dto.get("calories"), selected_activity.get("calories"))
        ),
        training_effect_label=summary_dto.get("trainingEffectLabel"),
        overall_training_effect=_safe_float(
            _coalesce(summary_dto.get("trainingEffect"), summary_dto.get("aerobicTrainingEffect"))
        ),
        aerobic_training_effect=_safe_float(summary_dto.get("aerobicTrainingEffect")),
        anaerobic_training_effect=_safe_float(summary_dto.get("anaerobicTrainingEffect")),
        training_load=_safe_float(summary_dto.get("activityTrainingLoad")),
        body_battery_impact=_safe_int(body_battery_impact),
        readiness=readiness,
        hrv=hrv,
        sleep=sleep,
        hr_zones=hr_zones,
        selected_from_count=len(activities) if activities else 1,
        warnings=warnings_list,
    )


def _build_error_payload(exc: GarminFallbackError) -> dict[str, Any]:
    payload = {
        "error": str(exc),
        "error_type": exc.__class__.__name__,
    }
    if exc.hint:
        payload["hint"] = exc.hint
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for repo-native Garmin workout lookups."""
    parser = argparse.ArgumentParser(description="Fetch normalized Garmin workout data for ATLAS.")
    parser.add_argument(
        "--date",
        default=None,
        help="Workout date in YYYY-MM-DD. Defaults to today in the local timezone.",
    )
    parser.add_argument(
        "--activity-id",
        default=None,
        type=int,
        help="Specific Garmin activity id to fetch.",
    )
    parser.add_argument(
        "--auth-home",
        default=str(DEFAULT_GARMIN_AUTH_HOME),
        help="Path to the local Garmin token directory.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Emit compact JSON instead of pretty-printed JSON.",
    )
    args = parser.parse_args(argv)

    try:
        snapshot = fetch_workout_snapshot(
            activity_date=args.date,
            activity_id=args.activity_id,
            auth_home=args.auth_home,
        )
    except GarminFallbackError as exc:
        print(
            json.dumps(
                _build_error_payload(exc),
                indent=None if args.compact else 2,
                sort_keys=True,
            )
        )
        return 1

    print(json.dumps(snapshot.to_dict(), indent=None if args.compact else 2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
