#!/usr/bin/env python3
"""WHOOP MCP server for ATLAS."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

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
sys.path.insert(0, str(CURRENT_DIR))

from mcp.server import FastMCP
from mcp.server.fastmcp import Context

from src.oauth_manager import UnrecoverableTokenError, load_and_init_oauth
from src.whoop_mcp import tools

logger = structlog.get_logger(__name__)


try:
    load_and_init_oauth()
    logger.info("WHOOP OAuth token manager initialized")
except UnrecoverableTokenError as exc:
    raise SystemExit(
        f"WHOOP authentication failed: {exc}\n"
        "Run 'python mcp-servers/whoop/oauth_setup.py' to complete or refresh setup.",
    ) from exc
except ValueError as exc:
    raise SystemExit(str(exc)) from exc
except Exception as exc:  # pragma: no cover - startup warning path
    logger.warning("WHOOP OAuth initialization warning", error=str(exc))


mcp = FastMCP(
    name="whoop",
    instructions=(
        "WHOOP MCP server for ATLAS. Provides high-level, provider-agnostic daily tools for "
        "sleep, recovery, cycle, and workout data. Prefer these normalized tools over raw WHOOP "
        "collection endpoints when building health summaries."
    ),
)


@mcp.tool()
async def get_daily_sleep(
    context: Context,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Get WHOOP daily sleep data with optional date range (YYYY-MM-DD format)."""
    return await tools.get_daily_sleep_tool(context, start_date, end_date)


@mcp.tool()
async def get_daily_recovery(
    context: Context,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Get WHOOP daily recovery data with optional date range (YYYY-MM-DD format)."""
    return await tools.get_daily_recovery_tool(context, start_date, end_date)


@mcp.tool()
async def get_daily_cycle(
    context: Context,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Get WHOOP daily cycle data with optional date range (YYYY-MM-DD format)."""
    return await tools.get_daily_cycle_tool(context, start_date, end_date)


@mcp.tool()
async def get_daily_workouts(
    context: Context,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Get WHOOP workouts with optional date range (YYYY-MM-DD format)."""
    return await tools.get_daily_workouts_tool(context, start_date, end_date)


if __name__ == "__main__":
    logger.info("Starting WHOOP MCP server")
    mcp.run()
