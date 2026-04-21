"""Google API client helpers for the ATLAS Google bot MCP server."""

from __future__ import annotations

from typing import Any

from .oauth_manager import get_google_credentials


def _load_google_api_dependencies() -> tuple[Any, Any]:
    try:
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
    except ModuleNotFoundError as exc:  # pragma: no cover - environment-specific guard
        raise RuntimeError(
            "Google API dependencies are missing. Run `pip install -e \".[dev]\"` from the repo root."
        ) from exc

    return build, HttpError


def build_gmail_service() -> Any:
    """Build an authenticated Gmail API client."""
    build, _ = _load_google_api_dependencies()
    return build("gmail", "v1", credentials=get_google_credentials(), cache_discovery=False)


def build_calendar_service() -> Any:
    """Build an authenticated Google Calendar API client."""
    build, _ = _load_google_api_dependencies()
    return build("calendar", "v3", credentials=get_google_credentials(), cache_discovery=False)


def get_http_error_type() -> Any:
    """Return the Google API HTTP error type for exception handling."""
    _, http_error = _load_google_api_dependencies()
    return http_error
