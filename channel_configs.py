"""Configured Discord channel roles and lookup helpers for ATLAS."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ChannelConfig:
    """Configuration for one ATLAS-managed Discord channel."""

    key: str
    role_description: str
    webhook_env: str
    channel_id_env: str | None = None
    default_model: str = "opus"
    auto_activate: bool = True
    read_mostly: bool = False
    preferred_skills: tuple[str, ...] = ()


CHANNEL_CONFIGS: dict[str, ChannelConfig] = {
    "atlas": ChannelConfig(
        key="atlas",
        role_description="General ATLAS conversation. Broad context; no specialization.",
        webhook_env="DISCORD_WEBHOOK_ATLAS",
        channel_id_env="ATLAS_CHANNEL_ID_ATLAS",
        preferred_skills=(
            "morning-briefing",
            "second-brain-librarian",
            "backend-concepts-lesson",
        ),
    ),
    "health": ChannelConfig(
        key="health",
        role_description=(
            "Prioritize health, training, medications, recovery, symptoms, supplements, "
            "Oura, WHOOP, Garmin, and workout logs. Prefer concrete logging and trend detection."
        ),
        webhook_env="DISCORD_WEBHOOK_HEALTH",
        channel_id_env="ATLAS_CHANNEL_ID_HEALTH",
        preferred_skills=(
            "morning-briefing",
            "health-pattern-monitor",
            "weekly-training-planner",
            "log-workout",
            "log-cardio",
            "log-medication",
        ),
    ),
    "projects": ChannelConfig(
        key="projects",
        role_description=(
            "Prioritize project state, tasks, decisions, stale threads, and follow-up. "
            "Keep recommendations action-oriented and grounded in the vault."
        ),
        webhook_env="DISCORD_WEBHOOK_PROJECTS",
        channel_id_env="ATLAS_CHANNEL_ID_PROJECTS",
        preferred_skills=("second-brain-librarian",),
    ),
    "briefings": ChannelConfig(
        key="briefings",
        role_description=(
            "Treat as read-mostly. Prefer concise reports, summaries, and ambient updates. "
            "Avoid turning it into a long conversational workspace unless James explicitly asks."
        ),
        webhook_env="DISCORD_WEBHOOK_BRIEFINGS",
        channel_id_env="ATLAS_CHANNEL_ID_BRIEFINGS",
        read_mostly=True,
        preferred_skills=("daily-summary", "weekly-review"),
    ),
    "atlas-dev": ChannelConfig(
        key="atlas-dev",
        role_description=(
            "Prioritize ATLAS harness development, repo changes, operational alerts, CI, "
            "test failures, MCP setup, and automation work."
        ),
        webhook_env="DISCORD_WEBHOOK_ATLAS_DEV",
        channel_id_env="ATLAS_CHANNEL_ID_ATLAS_DEV",
        preferred_skills=("backend-concepts-lesson",),
    ),
}


def normalize_channel_key(value: str) -> str:
    """Normalize a Discord channel name or config key for lookup."""
    return value.strip().lower().removeprefix("#")


def _configured_channel_keys() -> set[str] | None:
    raw_value = os.getenv("ATLAS_CONFIGURED_CHANNELS", "").strip()
    if not raw_value:
        return None
    return {
        normalize_channel_key(part) for part in raw_value.split(",") if normalize_channel_key(part)
    }


def _is_allowed(config: ChannelConfig) -> bool:
    allowed_keys = _configured_channel_keys()
    return allowed_keys is None or config.key in allowed_keys


def _parse_channel_id(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value.strip())
    except ValueError:
        return None


def get_channel_config_by_key(key: str, *, honor_allowlist: bool = True) -> ChannelConfig | None:
    """Return a configured channel by canonical key."""
    config = CHANNEL_CONFIGS.get(normalize_channel_key(key))
    if config is None:
        return None
    if honor_allowlist and not _is_allowed(config):
        return None
    return config


def get_channel_config(*, channel_id: int, channel_name: str = "") -> ChannelConfig | None:
    """Resolve by channel ID env pin first, then by channel name."""
    for config in CHANNEL_CONFIGS.values():
        configured_id = _parse_channel_id(os.getenv(config.channel_id_env or ""))
        if configured_id == channel_id:
            return config if _is_allowed(config) else None

    if channel_name:
        return get_channel_config_by_key(channel_name)

    return None


def render_channel_role_context(config: ChannelConfig | None, *, channel_name: str = "") -> str:
    """Render the session role context markdown for a Discord channel."""
    if config is None:
        label = f"#{normalize_channel_key(channel_name)}" if channel_name else "this channel"
        return (
            "# ATLAS Channel Role\n\n"
            f"{label} is not configured for automatic ATLAS activation. "
            "Treat this as a mention-initiated ad hoc conversation and follow the global "
            "ATLAS system prompt.\n"
        )

    lines = [
        "# ATLAS Channel Role",
        "",
        f"Channel: #{config.key}",
        f"Read-mostly: {'yes' if config.read_mostly else 'no'}",
        "",
        config.role_description,
    ]
    if config.preferred_skills:
        lines.extend(
            [
                "",
                "## Preferred Skills",
                "",
                "Prefer these skills when they fit the user's request:",
                *[f"- {skill}" for skill in config.preferred_skills],
            ]
        )
    return "\n".join(lines) + "\n"
