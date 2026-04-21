"""Thin Garmin API wrapper used by the repo-managed MCP server."""

from __future__ import annotations

from typing import Any

from src.auth_manager import GarminAuthManager


class GarminAPIClient:
    """High-level wrapper around the authenticated Garmin client."""

    def __init__(self, auth_manager: GarminAuthManager | None = None) -> None:
        self._auth_manager = auth_manager or GarminAuthManager()

    def get_activities_fordate(self, fordate: str) -> dict[str, Any]:
        return self._auth_manager.run_with_client(
            f"activity lookup for {fordate}",
            lambda client: client.get_activities_fordate(fordate),
        )

    def get_activities_by_date(
        self,
        start_date: str,
        end_date: str,
        activity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._auth_manager.run_with_client(
            f"activity lookup from {start_date} to {end_date}",
            lambda client: client.get_activities_by_date(start_date, end_date, activity_type),
        )

    def get_activity(self, activity_id: int) -> dict[str, Any]:
        return self._auth_manager.run_with_client(
            f"activity {activity_id}",
            lambda client: client.get_activity(str(activity_id)),
        )

    def get_activity_splits(self, activity_id: int) -> dict[str, Any]:
        return self._auth_manager.run_with_client(
            f"activity splits for {activity_id}",
            lambda client: client.get_activity_splits(str(activity_id)),
        )

    def get_activity_hr_in_timezones(self, activity_id: int) -> list[dict[str, Any]]:
        return self._auth_manager.run_with_client(
            f"activity hr zones for {activity_id}",
            lambda client: client.get_activity_hr_in_timezones(str(activity_id)),
        )

    def get_stats(self, cdate: str) -> dict[str, Any]:
        return self._auth_manager.run_with_client(
            f"daily stats for {cdate}",
            lambda client: client.get_stats(cdate),
        )

    def get_sleep_data(self, cdate: str) -> dict[str, Any]:
        return self._auth_manager.run_with_client(
            f"sleep data for {cdate}",
            lambda client: client.get_sleep_data(cdate),
        )

    def get_hrv_data(self, cdate: str) -> dict[str, Any] | None:
        return self._auth_manager.run_with_client(
            f"hrv data for {cdate}",
            lambda client: client.get_hrv_data(cdate),
        )

    def get_training_readiness(self, cdate: str) -> dict[str, Any] | list[dict[str, Any]]:
        return self._auth_manager.run_with_client(
            f"training readiness for {cdate}",
            lambda client: client.get_training_readiness(cdate),
        )

    def get_body_battery(
        self,
        start_date: str,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._auth_manager.run_with_client(
            f"body battery from {start_date} to {end_date or start_date}",
            lambda client: client.get_body_battery(start_date, end_date),
        )

    def get_body_battery_events(self, cdate: str) -> list[dict[str, Any]]:
        return self._auth_manager.run_with_client(
            f"body battery events for {cdate}",
            lambda client: client.get_body_battery_events(cdate),
        )

    def get_full_name(self) -> str | None:
        return self._auth_manager.run_with_client(
            "profile lookup",
            lambda client: client.get_full_name(),
        )
