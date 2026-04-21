"""Shared MCP tool compatibility helpers for ATLAS."""

from __future__ import annotations

ATLAS_GOOGLE_CALENDAR_PREFIX = "atlas__google_calendar__"
ATLAS_GMAIL_PREFIX = "atlas__gmail__"
GOOGLE_BOT_TOOL_PREFIX = "mcp__google_bot__"
GOOGLE_BOT_CALENDAR_TOOL_NAMES = {
    "mcp__google_bot__get_profile",
    "mcp__google_bot__list_calendars",
    "mcp__google_bot__search_events",
    "mcp__google_bot__create_event",
    "mcp__google_bot__update_event",
    "mcp__google_bot__delete_event",
}

ATLAS_TO_PROVIDER_TOOL_NAMES = {
    "atlas__google_calendar__search_events": {
        "claude": "mcp__google_bot__search_events",
        "codex": "mcp__google_bot__search_events",
    },
    # Probe auth/connectivity via a lightweight read-only call.
    "atlas__google_calendar__probe_auth": {
        "claude": "mcp__google_bot__get_profile",
        "codex": "mcp__google_bot__get_profile",
    },
    # Backward-compatible legacy alias. Prefer `atlas__google_calendar__probe_auth`.
    "atlas__google_calendar__get_profile": {
        "claude": "mcp__google_bot__get_profile",
        "codex": "mcp__google_bot__get_profile",
    },
    "atlas__google_calendar__create_event": {
        "claude": "mcp__google_bot__create_event",
        "codex": "mcp__google_bot__create_event",
    },
    "atlas__google_calendar__update_event": {
        "claude": "mcp__google_bot__update_event",
        "codex": "mcp__google_bot__update_event",
    },
    "atlas__google_calendar__delete_event": {
        "claude": "mcp__google_bot__delete_event",
        "codex": "mcp__google_bot__delete_event",
    },
    "atlas__gmail__list_labels": {
        "claude": "mcp__google_bot__list_labels",
        "codex": "mcp__google_bot__list_labels",
    },
}

PROVIDER_TOOL_TO_ATLAS_ALIAS = {
    atlas_tool: atlas_tool for atlas_tool in ATLAS_TO_PROVIDER_TOOL_NAMES
}
for atlas_tool, provider_tools in ATLAS_TO_PROVIDER_TOOL_NAMES.items():
    for provider_tool in provider_tools.values():
        PROVIDER_TOOL_TO_ATLAS_ALIAS[provider_tool] = atlas_tool

# Older Claude-era aliases that still appear in existing configs/tests.
PROVIDER_TOOL_TO_ATLAS_ALIAS.update(
    {
        "mcp__google-calendar__list-events": "atlas__google_calendar__search_events",
        "mcp__google-calendar__search-events": "atlas__google_calendar__search_events",
        "mcp__google-calendar__list-calendars": "atlas__google_calendar__probe_auth",
        "mcp__google-calendar__create-event": "atlas__google_calendar__create_event",
        "mcp__google-calendar__update-event": "atlas__google_calendar__update_event",
        "mcp__google-calendar__delete-event": "atlas__google_calendar__delete_event",
        "mcp__codex_apps__google_calendar_search_events": "atlas__google_calendar__search_events",
        "mcp__codex_apps__google_calendar_get_profile": "atlas__google_calendar__probe_auth",
        "mcp__codex_apps__google_calendar_create_event": "atlas__google_calendar__create_event",
        "mcp__codex_apps__google_calendar_update_event": "atlas__google_calendar__update_event",
        "mcp__codex_apps__google_calendar_delete_event": "atlas__google_calendar__delete_event",
        "mcp__gmail__list_email_labels": "atlas__gmail__list_labels",
        "mcp__codex_apps__gmail_list_labels": "atlas__gmail__list_labels",
    }
)

GOOGLE_CALENDAR_TOOL_LEGACY_PREFIXES = (
    "mcp__codex_apps__google_calendar_",
    "mcp__google-calendar__",
)

GOOGLE_CALENDAR_PRE_TOOL_MATCHERS = (
    "mcp__google_bot__create_event",
    "mcp__google_bot__update_event",
    "mcp__codex_apps__google_calendar_create_event",
    "mcp__codex_apps__google_calendar_update_event",
    "mcp__google-calendar__create-event",
    "mcp__google-calendar__update-event",
)

GOOGLE_CALENDAR_PERMISSION_PATTERNS = ("mcp__google_bot__*",)

GMAIL_PERMISSION_PATTERNS = ("mcp__google_bot__*",)


def is_google_calendar_tool_name(tool_name: str) -> bool:
    """Return whether a tool name targets the Google Calendar connector."""
    if tool_name.startswith(ATLAS_GOOGLE_CALENDAR_PREFIX):
        return True
    if tool_name.startswith(GOOGLE_CALENDAR_TOOL_LEGACY_PREFIXES):
        return True
    return tool_name in GOOGLE_BOT_CALENDAR_TOOL_NAMES


def normalize_allowed_tools_for_provider(allowed_tools: list[str], provider: str) -> list[str]:
    """Translate ATLAS or provider-specific tool names for the selected provider."""
    translated_tools: list[str] = []
    seen_tools: set[str] = set()

    for tool_name in allowed_tools:
        atlas_tool = PROVIDER_TOOL_TO_ATLAS_ALIAS.get(tool_name, tool_name)
        provider_tools = ATLAS_TO_PROVIDER_TOOL_NAMES.get(atlas_tool)
        normalized_tool = provider_tools.get(provider) if provider_tools else atlas_tool

        if normalized_tool is None:
            continue
        if provider == "claude" and atlas_tool.startswith("mcp__codex_apps__"):
            continue

        if normalized_tool not in seen_tools:
            translated_tools.append(normalized_tool)
            seen_tools.add(normalized_tool)

    return translated_tools
