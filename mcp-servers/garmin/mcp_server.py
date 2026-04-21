#!/usr/bin/env python3
"""Repo-managed Garmin MCP server for ATLAS."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import structlog

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
    force=True,
)

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

os.environ.setdefault("LOG_LEVEL", "INFO")

CURRENT_DIR = Path(__file__).parent.resolve()
REPO_ROOT = CURRENT_DIR.parents[1]
sys.path.insert(0, str(CURRENT_DIR))
sys.path.insert(0, str(REPO_ROOT))

from mcp.server import FastMCP
from mcp.server.fastmcp import Context

from src.auth_manager import GarminAuthManager, RecoverableTokenError, UnrecoverableTokenError
from src.garmin_api.client import GarminAPIClient
from src.garmin_mcp import tools

logger = structlog.get_logger(__name__)

try:
    api_client = GarminAPIClient()
    tools.set_api_client(api_client)
    logger.info("Garmin token manager initialized")
except UnrecoverableTokenError as exc:
    raise SystemExit(
        f"Garmin authentication failed: {exc}\n"
        "Run 'python mcp-servers/garmin/oauth_setup.py' to complete or refresh setup.",
    ) from exc
except RecoverableTokenError as exc:  # pragma: no cover - transient startup warning
    logger.warning("Garmin initialization warning", error=str(exc))
    api_client = GarminAPIClient(GarminAuthManager(validate_on_init=False))
    tools.set_api_client(api_client)
except Exception as exc:  # pragma: no cover - startup warning path
    logger.warning("Unexpected Garmin initialization warning", error=str(exc))
    api_client = GarminAPIClient(GarminAuthManager(validate_on_init=False))
    tools.set_api_client(api_client)

mcp = FastMCP(
    name="garmin",
    instructions=(
        "Repo-managed Garmin Connect MCP server for ATLAS. Prefer get_activities_fordate and "
        "get_activity for workout logging compatibility, and use the normalized daily tools for "
        "training readiness, HRV, sleep, and body battery summaries."
    ),
)


@mcp.tool(name="get_profile")
async def get_profile(context: Context) -> dict[str, str | None]:
    """Verify Garmin auth and return a minimal profile payload."""
    return await tools.get_profile_tool(context)


@mcp.tool(name="get_activities_by_date")
async def get_activities_by_date(
    context: Context,
    start_date: str,
    end_date: str,
    activity_type: str = "",
) -> dict[str, object]:
    """Get activities between dates, optionally filtered by Garmin activity type."""
    return await tools.get_activities_by_date_tool(context, start_date, end_date, activity_type)


@mcp.tool(name="get_activities_fordate")
async def get_activities_fordate(context: Context, date: str) -> dict[str, object]:
    """Get activities for a single Garmin activity day."""
    return await tools.get_activities_fordate_tool(context, date)


@mcp.tool(name="get_activity")
async def get_activity(context: Context, activity_id: int) -> dict[str, object]:
    """Get Garmin activity detail for a specific id."""
    return await tools.get_activity_tool(context, activity_id)


@mcp.tool(name="get_activity_splits")
async def get_activity_splits(context: Context, activity_id: int) -> dict[str, object]:
    """Get Garmin activity split data."""
    return await tools.get_activity_splits_tool(context, activity_id)


@mcp.tool(name="get_activity_hr_in_timezones")
async def get_activity_hr_in_timezones(context: Context, activity_id: int) -> dict[str, object]:
    """Get time spent in each heart-rate zone for an activity."""
    return await tools.get_activity_hr_in_timezones_tool(context, activity_id)


@mcp.tool(name="get_stats")
async def get_stats(context: Context, date: str) -> dict[str, object]:
    """Get Garmin daily stats for a single date."""
    return await tools.get_stats_tool(context, date)


@mcp.tool(name="get_sleep_data")
async def get_sleep_data(context: Context, date: str) -> dict[str, object]:
    """Get Garmin sleep data for a single date."""
    return await tools.get_sleep_data_tool(context, date)


@mcp.tool(name="get_hrv_data")
async def get_hrv_data(context: Context, date: str) -> dict[str, object]:
    """Get Garmin HRV data for a single date."""
    return await tools.get_hrv_data_tool(context, date)


@mcp.tool(name="get_training_readiness")
async def get_training_readiness(context: Context, date: str) -> dict[str, object]:
    """Get Garmin training readiness for a single date."""
    return await tools.get_training_readiness_tool(context, date)


@mcp.tool(name="get_body_battery")
async def get_body_battery(
    context: Context,
    start_date: str,
    end_date: str | None = None,
) -> dict[str, object]:
    """Get Garmin body battery summaries for a date or date range."""
    return await tools.get_body_battery_tool(context, start_date, end_date)


@mcp.tool(name="get_body_battery_events")
async def get_body_battery_events(context: Context, date: str) -> dict[str, object]:
    """Get Garmin body battery events for a single date."""
    return await tools.get_body_battery_events_tool(context, date)


if __name__ == "__main__":
    logger.info("Starting Garmin MCP server")
    mcp.run()
