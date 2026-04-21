"""Tests for bot session permission defaults."""

import bot


def test_channel_permissions_allow_google_calendar_tools():
    allowed = bot.CHANNEL_PERMISSIONS["permissions"]["allow"]

    assert "mcp__google_bot__*" in allowed


def test_channel_permissions_allow_gmail_tools():
    allowed = bot.CHANNEL_PERMISSIONS["permissions"]["allow"]

    assert "mcp__google_bot__*" in allowed
