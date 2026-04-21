"""Async WHOOP API v2 client."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from ..config import settings

logger = structlog.get_logger(__name__)


class WhoopAPIError(Exception):
    """WHOOP API-specific error."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_data: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


class RateLimitError(WhoopAPIError):
    """WHOOP API rate limit error."""

    def __init__(self, retry_after: int | None = None) -> None:
        super().__init__("WHOOP rate limit exceeded")
        self.retry_after = retry_after


def _to_utc_iso(value: datetime) -> str:
    """Convert a datetime to a WHOOP-friendly UTC ISO-8601 string."""
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class WhoopClient:
    """Async WHOOP client for ATLAS health integrations."""

    REQUEST_TIMEOUT = 30.0
    MAX_RETRIES = 3
    PAGE_LIMIT = 25

    def __init__(self, access_token: str) -> None:
        self.base_url = settings.whoop_api_base_url
        self.access_token = access_token
        self.session: httpx.AsyncClient | None = None

    async def __aenter__(self) -> WhoopClient:
        """Open the shared async HTTP client."""
        self.session = httpx.AsyncClient(timeout=httpx.Timeout(self.REQUEST_TIMEOUT))
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, exc_tb: Any) -> None:
        """Close the shared async HTTP client."""
        if self.session is not None:
            await self.session.aclose()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "User-Agent": "atlas-whoop-mcp/1.0.0",
        }

    async def _request(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        retries: int = MAX_RETRIES,
    ) -> dict[str, Any]:
        """Make a GET request against the WHOOP API."""
        if self.session is None:
            raise RuntimeError("WHOOP client not initialized; use async context manager")

        url = f"{self.base_url}{endpoint}"
        for attempt in range(retries + 1):
            try:
                response = await self.session.get(url, headers=self._headers(), params=params)
            except httpx.RequestError as exc:
                if attempt < retries:
                    await asyncio.sleep(2**attempt)
                    continue
                raise WhoopAPIError(f"WHOOP request failed: {exc}") from exc

            if response.status_code == 200:
                return response.json()

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "60"))
                if attempt < retries:
                    await asyncio.sleep(retry_after)
                    continue
                raise RateLimitError(retry_after)

            if response.status_code in {401, 403}:
                raise WhoopAPIError(
                    "WHOOP authentication failed",
                    status_code=response.status_code,
                    response_data=response.json() if response.content else {},
                )

            if response.status_code >= 500 and attempt < retries:
                await asyncio.sleep(2**attempt)
                continue

            raise WhoopAPIError(
                f"WHOOP request failed with HTTP {response.status_code}",
                status_code=response.status_code,
                response_data=response.json() if response.content else {},
            )

        raise WhoopAPIError("WHOOP request failed after retries")

    async def _collect_records(
        self,
        endpoint: str,
        *,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        """Collect all paginated records for a WHOOP collection endpoint."""
        records: list[dict[str, Any]] = []
        next_token: str | None = None

        while True:
            params: dict[str, Any] = {
                "limit": self.PAGE_LIMIT,
                "start": _to_utc_iso(start),
                "end": _to_utc_iso(end),
            }
            if next_token:
                params["nextToken"] = next_token

            payload = await self._request(endpoint, params=params)
            page_records = payload.get("records", [])
            if isinstance(page_records, list):
                records.extend([record for record in page_records if isinstance(record, dict)])

            next_token = payload.get("next_token") or payload.get("nextToken")
            if not isinstance(next_token, str) or not next_token:
                break

        return records

    async def get_profile(self) -> dict[str, Any]:
        """Get the WHOOP user profile."""
        return await self._request("/user/profile/basic")

    async def get_sleep_collection(self, *, start: datetime, end: datetime) -> list[dict[str, Any]]:
        """Get all sleep records in the requested window."""
        return await self._collect_records("/activity/sleep", start=start, end=end)

    async def get_recovery_collection(
        self,
        *,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        """Get all recovery records in the requested window."""
        return await self._collect_records("/recovery", start=start, end=end)

    async def get_cycle_collection(self, *, start: datetime, end: datetime) -> list[dict[str, Any]]:
        """Get all cycle records in the requested window."""
        return await self._collect_records("/cycle", start=start, end=end)

    async def get_workout_collection(
        self,
        *,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        """Get all workout records in the requested window."""
        return await self._collect_records("/activity/workout", start=start, end=end)
