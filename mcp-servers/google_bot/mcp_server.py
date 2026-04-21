#!/usr/bin/env python3
"""Google bot MCP server for ATLAS."""

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

from src.google_bot_mcp import tools
from src.oauth_manager import GoogleBotAuthMissingError, get_google_credentials

logger = structlog.get_logger(__name__)


try:
    get_google_credentials()
    logger.info("Google bot OAuth credentials loaded")
except GoogleBotAuthMissingError as exc:
    raise SystemExit(
        f"Google bot authentication failed: {exc}\n"
        "Run 'python3 mcp-servers/google_bot/oauth_setup.py --client-secret-file <path>'"
        " to complete or refresh setup.",
    ) from exc
except Exception as exc:  # pragma: no cover - startup warning path
    logger.warning("Google bot OAuth initialization warning", error=str(exc))


mcp = FastMCP(
    name="google_bot",
    instructions=(
        "Google bot MCP server for ATLAS. Provides Gmail and Google Calendar tools backed by "
        "a repo-managed OAuth flow so ATLAS can use a bot-owned Google account independent of "
        "the ChatGPT/Codex account login."
    ),
)


@mcp.tool()
async def get_profile(context: Context) -> dict[str, Any]:
    """Return the connected Google bot profile plus calendar access summary."""
    return await tools.get_profile_tool(context)


@mcp.tool()
async def list_labels(context: Context) -> list[dict[str, Any]]:
    """List Gmail labels for the connected bot mailbox."""
    return await tools.list_labels_tool(context)


@mcp.tool()
async def search_emails(
    context: Context,
    query: str | None = None,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """Search Gmail messages for the connected bot mailbox."""
    return await tools.search_emails_tool(context, query=query, max_results=max_results)


@mcp.tool()
async def read_email(context: Context, message_id: str) -> dict[str, Any]:
    """Read a Gmail message including decoded text/html bodies when available."""
    return await tools.read_email_tool(context, message_id)


@mcp.tool()
async def send_email(
    context: Context,
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
) -> dict[str, Any]:
    """Send an email from the connected Gmail account."""
    return await tools.send_email_tool(context, to=to, subject=subject, body=body, cc=cc, bcc=bcc)


@mcp.tool()
async def modify_email_labels(
    context: Context,
    message_ids: list[str],
    add_label_names: list[str] | None = None,
    remove_label_names: list[str] | None = None,
    create_missing_labels: bool = False,
    archive: bool = False,
) -> list[dict[str, Any]]:
    """Add/remove Gmail labels and optionally archive messages."""
    return await tools.modify_email_labels_tool(
        context,
        message_ids=message_ids,
        add_label_names=add_label_names,
        remove_label_names=remove_label_names,
        create_missing_labels=create_missing_labels,
        archive=archive,
    )


@mcp.tool()
async def archive_emails(context: Context, message_ids: list[str]) -> list[dict[str, Any]]:
    """Archive existing Gmail messages by removing the INBOX label."""
    return await tools.archive_emails_tool(context, message_ids=message_ids)


@mcp.tool()
async def list_calendars(context: Context, max_results: int = 50) -> list[dict[str, Any]]:
    """List calendars the bot account can access."""
    return await tools.list_calendars_tool(context, max_results=max_results)


@mcp.tool()
async def search_events(
    context: Context,
    calendar_id: str = "primary",
    query: str | None = None,
    time_min: str | None = None,
    time_max: str | None = None,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Search Google Calendar events for a calendar and optional time window."""
    return await tools.search_events_tool(
        context,
        calendar_id=calendar_id,
        query=query,
        time_min=time_min,
        time_max=time_max,
        max_results=max_results,
    )


@mcp.tool()
async def create_event(
    context: Context,
    title: str,
    start_time: str,
    end_time: str,
    timezone_str: str,
    calendar_id: str = "primary",
    attendees: list[str] | None = None,
    description: str | None = None,
    location: str | None = None,
    add_google_meet: bool = False,
    visibility: str | None = None,
    transparency: str | None = None,
) -> dict[str, Any]:
    """Create a Google Calendar event in the bot-owned calendar."""
    return await tools.create_event_tool(
        context,
        title=title,
        start_time=start_time,
        end_time=end_time,
        timezone_str=timezone_str,
        calendar_id=calendar_id,
        attendees=attendees,
        description=description,
        location=location,
        add_google_meet=add_google_meet,
        visibility=visibility,
        transparency=transparency,
    )


@mcp.tool()
async def update_event(
    context: Context,
    event_id: str,
    calendar_id: str = "primary",
    title: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    timezone_str: str | None = None,
    description: str | None = None,
    location: str | None = None,
    attendees_to_add: list[str] | None = None,
    attendees_to_remove: list[str] | None = None,
    add_google_meet: bool = False,
    visibility: str | None = None,
    transparency: str | None = None,
) -> dict[str, Any]:
    """Update an existing Google Calendar event."""
    return await tools.update_event_tool(
        context,
        event_id=event_id,
        calendar_id=calendar_id,
        title=title,
        start_time=start_time,
        end_time=end_time,
        timezone_str=timezone_str,
        description=description,
        location=location,
        attendees_to_add=attendees_to_add,
        attendees_to_remove=attendees_to_remove,
        add_google_meet=add_google_meet,
        visibility=visibility,
        transparency=transparency,
    )


@mcp.tool()
async def delete_event(context: Context, event_id: str, calendar_id: str = "primary") -> dict[str, Any]:
    """Delete an existing Google Calendar event."""
    return await tools.delete_event_tool(context, event_id=event_id, calendar_id=calendar_id)


if __name__ == "__main__":
    logger.info("Starting Google bot MCP server")
    mcp.run()
