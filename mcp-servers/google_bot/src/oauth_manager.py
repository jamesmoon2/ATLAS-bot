"""Google OAuth credential loading and refresh for the ATLAS Google bot server."""

from __future__ import annotations

import json
import os
import stat
import threading
from pathlib import Path
from typing import Any

SCOPES = (
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events.owned",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_client_secret_file() -> Path:
    return _repo_root() / "mcp-servers" / "credentials" / "google-bot-oauth-client.json"


def _default_token_file() -> Path:
    return _repo_root() / "mcp-servers" / "credentials" / "google-bot-tokens.json"


CLIENT_SECRET_FILE = Path(
    os.getenv("GOOGLE_BOT_CLIENT_SECRET_FILE", _default_client_secret_file())
).expanduser()
TOKEN_FILE = Path(os.getenv("GOOGLE_BOT_TOKEN_FILE", _default_token_file())).expanduser()


class GoogleBotAuthError(RuntimeError):
    """Base exception for Google bot OAuth problems."""


class GoogleBotAuthMissingError(GoogleBotAuthError):
    """Raised when the repo-managed Google bot credentials are not configured."""


_CREDENTIAL_LOCK = threading.Lock()


def _write_json_secure(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = path.with_suffix(".tmp")
    temp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temp_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
    temp_file.replace(path)


def _load_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise GoogleBotAuthMissingError(f"Failed to read Google auth file {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise GoogleBotAuthMissingError(f"Google auth file {path} does not contain a JSON object.")
    return data


def _load_google_auth_dependencies() -> tuple[Any, Any]:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ModuleNotFoundError as exc:  # pragma: no cover - environment-specific guard
        raise GoogleBotAuthMissingError(
            "Google bot dependencies are missing. Run `pip install -e \".[dev]\"` from the repo root."
        ) from exc

    return Credentials, Request


def _scopes_match(granted_scopes: list[str] | tuple[str, ...] | None) -> bool:
    if not granted_scopes:
        return False
    return set(SCOPES).issubset(set(granted_scopes))


def _refresh_credentials(credentials: Any, request_cls: Any) -> Any:
    if not credentials.refresh_token:
        raise GoogleBotAuthMissingError(
            "Google bot refresh token is missing. Run "
            "'python3 mcp-servers/google_bot/oauth_setup.py --client-secret-file <path>'."
        )

    credentials.refresh(request_cls())
    token_payload = json.loads(credentials.to_json())
    token_payload["granted_scopes"] = sorted(credentials.scopes or [])
    _write_json_secure(TOKEN_FILE, token_payload)
    return credentials


def get_google_credentials() -> Any:
    """Return valid Google OAuth credentials for the repo-managed bot account."""
    with _CREDENTIAL_LOCK:
        if not TOKEN_FILE.exists():
            raise GoogleBotAuthMissingError(
                f"Google bot token file is missing: {TOKEN_FILE}. "
                "Run 'python3 mcp-servers/google_bot/oauth_setup.py --client-secret-file <path>'."
            )

        Credentials, Request = _load_google_auth_dependencies()
        token_payload = _load_json_file(TOKEN_FILE)
        credentials = Credentials.from_authorized_user_info(token_payload or {}, SCOPES)

        granted_scopes = token_payload.get("granted_scopes") if token_payload else None
        if not _scopes_match(granted_scopes or credentials.scopes):
            raise GoogleBotAuthMissingError(
                "Google bot token is missing required scopes. "
                "Re-run 'python3 mcp-servers/google_bot/oauth_setup.py --client-secret-file <path>'."
            )

        if credentials.expired or not credentials.valid:
            credentials = _refresh_credentials(credentials, Request)

        return credentials
