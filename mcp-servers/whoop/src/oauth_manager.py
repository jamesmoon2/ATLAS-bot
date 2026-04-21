"""WHOOP OAuth token management with secure persistence and refresh."""

from __future__ import annotations

import json
import os
import stat
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import structlog

from .config import settings

logger = structlog.get_logger(__name__)

TOKEN_URL = f"{settings.whoop_auth_base_url}/token"
VALIDATION_URL = f"{settings.whoop_api_base_url}/user/profile/basic"
DEFAULT_REDIRECT_URI = "http://localhost:3000/callback"

MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 1.0


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_credentials_file() -> Path:
    return _repo_root() / "mcp-servers" / "credentials" / "whoop-oauth.keys.json"


def _default_token_file() -> Path:
    return _repo_root() / "mcp-servers" / "credentials" / "whoop-tokens.json"


CREDENTIALS_FILE = Path(os.getenv("WHOOP_OAUTH_CREDENTIALS", _default_credentials_file()))
TOKEN_FILE = Path(os.getenv("WHOOP_TOKEN_FILE", _default_token_file()))


class TokenRefreshError(Exception):
    """Base exception for token refresh failures."""


class RecoverableTokenError(TokenRefreshError):
    """Temporary token issue that can be retried."""


class UnrecoverableTokenError(TokenRefreshError):
    """Permanent token issue that requires user action."""


def _write_json_secure(path: Path, data: dict[str, Any]) -> None:
    """Write JSON to disk atomically with restrictive permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = path.with_suffix(".tmp")
    temp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temp_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
    temp_file.replace(path)


def _load_json_from_file(path: Path) -> dict[str, Any] | None:
    """Load JSON from a file when present and readable."""
    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read JSON file", path=str(path), error=str(exc))
        return None


def _load_credentials_from_file() -> dict[str, str] | None:
    """Load WHOOP OAuth client credentials from disk."""
    data = _load_json_from_file(CREDENTIALS_FILE)
    if not data:
        return None

    client_id = data.get("client_id")
    client_secret = data.get("client_secret")
    redirect_uri = data.get("redirect_uri", DEFAULT_REDIRECT_URI)
    if not isinstance(client_id, str) or not isinstance(client_secret, str):
        return None

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }


def _load_credentials_from_env() -> dict[str, str] | None:
    """Load WHOOP OAuth client credentials from environment variables."""
    client_id = os.getenv("WHOOP_CLIENT_ID")
    client_secret = os.getenv("WHOOP_CLIENT_SECRET")
    redirect_uri = os.getenv("WHOOP_REDIRECT_URI", DEFAULT_REDIRECT_URI)
    if not client_id or not client_secret:
        return None

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }


def _load_tokens_from_file() -> dict[str, Any] | None:
    """Load WHOOP access and refresh tokens from disk."""
    return _load_json_from_file(TOKEN_FILE)


def _load_tokens_from_env() -> dict[str, Any] | None:
    """Load WHOOP tokens from environment variables when present."""
    access_token = os.getenv("WHOOP_ACCESS_TOKEN")
    refresh_token = os.getenv("WHOOP_REFRESH_TOKEN")
    if not access_token and not refresh_token:
        return None

    data: dict[str, Any] = {}
    if access_token:
        data["access_token"] = access_token
    if refresh_token:
        data["refresh_token"] = refresh_token
    expires_at = os.getenv("WHOOP_TOKEN_EXPIRES_AT")
    if expires_at:
        data["expires_at"] = expires_at
    return data


def _parse_expires_at(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp into a timezone-aware datetime."""
    if not value:
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


class OAuthTokenManager:
    """Thread-safe WHOOP OAuth token manager with automatic refresh."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        access_token: str | None,
        refresh_token: str | None,
        token_expires_at: datetime | None,
        token_file: Path,
        validate_on_init: bool = True,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._token_expires_at = token_expires_at
        self._token_file = token_file
        self._lock = threading.Lock()

        if validate_on_init:
            self._validate_current_token()

    def _validate_current_token(self) -> None:
        """Validate the current token or refresh it if needed."""
        if not self._access_token:
            if not self._refresh_token:
                raise UnrecoverableTokenError(
                    "WHOOP authentication is not configured. "
                    "Run 'python mcp-servers/whoop/oauth_setup.py'.",
                )
            self._refresh_tokens_with_retry()
            return

        try:
            response = httpx.get(
                VALIDATION_URL,
                headers={"Authorization": f"Bearer {self._access_token}"},
                timeout=10.0,
            )
        except httpx.RequestError as exc:
            logger.warning("WHOOP token validation skipped after network error", error=str(exc))
            return

        if response.status_code == 200:
            if self._token_expires_at is None:
                self._token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=55)
            logger.info("WHOOP access token validated successfully")
            return

        if response.status_code == 401 and self._refresh_token:
            logger.info("WHOOP access token expired during startup, refreshing")
            self._refresh_tokens_with_retry()
            return

        logger.warning(
            "Unexpected WHOOP validation response",
            status_code=response.status_code,
        )

    def get_access_token(self) -> str:
        """Return a valid access token, refreshing when required."""
        with self._lock:
            expires_soon = False
            if self._token_expires_at is None:
                expires_soon = True
            else:
                expires_soon = datetime.now(timezone.utc) >= self._token_expires_at - timedelta(
                    minutes=5,
                )

            if expires_soon:
                self._refresh_tokens_with_retry()

            if not self._access_token:
                raise UnrecoverableTokenError(
                    "WHOOP authentication is not configured. "
                    "Run 'python mcp-servers/whoop/oauth_setup.py'.",
                )
            return self._access_token

    def _refresh_tokens_with_retry(self) -> None:
        """Refresh the WHOOP access token with exponential backoff."""
        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                self._refresh_tokens()
                return
            except RecoverableTokenError as exc:
                last_error = exc
                if attempt < MAX_RETRIES - 1:
                    backoff = BASE_BACKOFF_SECONDS * (2**attempt)
                    logger.warning(
                        "WHOOP token refresh failed; retrying",
                        attempt=attempt + 1,
                        max_retries=MAX_RETRIES,
                        backoff_seconds=backoff,
                        error=str(exc),
                    )
                    time.sleep(backoff)
            except UnrecoverableTokenError:
                raise

        raise RecoverableTokenError(
            f"WHOOP token refresh failed after {MAX_RETRIES} attempts: {last_error}",
        )

    def _refresh_tokens(self) -> None:
        """Refresh the WHOOP access token using the current refresh token."""
        if not self._refresh_token:
            raise UnrecoverableTokenError(
                "Missing WHOOP refresh token. Run 'python mcp-servers/whoop/oauth_setup.py'.",
            )

        try:
            response = httpx.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "scope": "offline",
                },
                timeout=30.0,
            )
        except httpx.RequestError as exc:
            raise RecoverableTokenError(f"Network error while refreshing token: {exc}") from exc

        if response.status_code == 200:
            payload = response.json()
            self._access_token = payload["access_token"]
            self._refresh_token = payload["refresh_token"]
            expires_in = int(payload.get("expires_in", 3600))
            self._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            _write_json_secure(
                self._token_file,
                {
                    "access_token": self._access_token,
                    "refresh_token": self._refresh_token,
                    "expires_at": self._token_expires_at.isoformat(),
                },
            )
            logger.info("WHOOP tokens refreshed successfully")
            return

        if response.status_code in {400, 401}:
            raise UnrecoverableTokenError(
                "WHOOP refresh token is invalid or expired. "
                "Run 'python mcp-servers/whoop/oauth_setup.py'.",
            )

        if response.status_code >= 500:
            raise RecoverableTokenError(f"WHOOP server error (HTTP {response.status_code})")

        raise RecoverableTokenError(
            f"Unexpected WHOOP refresh response (HTTP {response.status_code})",
        )


_token_manager: OAuthTokenManager | None = None
_init_lock = threading.Lock()


def init_oauth_manager(
    *,
    client_id: str,
    client_secret: str,
    access_token: str | None,
    refresh_token: str | None,
    token_expires_at: datetime | None,
    token_file: Path = TOKEN_FILE,
    validate_on_init: bool = True,
) -> None:
    """Initialize the module-level WHOOP OAuth manager."""
    global _token_manager
    with _init_lock:
        _token_manager = OAuthTokenManager(
            client_id=client_id,
            client_secret=client_secret,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            token_file=token_file,
            validate_on_init=validate_on_init,
        )


def load_and_init_oauth() -> None:
    """Load credentials and tokens, then initialize the global token manager."""
    credentials = _load_credentials_from_file() or _load_credentials_from_env()
    if not credentials:
        raise ValueError(
            "WHOOP OAuth credentials are missing. "
            f"Populate {CREDENTIALS_FILE} or set WHOOP_CLIENT_ID/WHOOP_CLIENT_SECRET.",
        )

    tokens = _load_tokens_from_file() or _load_tokens_from_env() or {}
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    if not access_token and not refresh_token:
        raise UnrecoverableTokenError(
            "WHOOP access is not authorized yet. "
            "Run 'python mcp-servers/whoop/oauth_setup.py' to complete OAuth.",
        )

    init_oauth_manager(
        client_id=credentials["client_id"],
        client_secret=credentials["client_secret"],
        access_token=access_token if isinstance(access_token, str) else None,
        refresh_token=refresh_token if isinstance(refresh_token, str) else None,
        token_expires_at=_parse_expires_at(tokens.get("expires_at")),
        validate_on_init=True,
    )


def get_valid_access_token() -> str:
    """Return a valid WHOOP access token from the global token manager."""
    if _token_manager is None:
        raise RuntimeError("WHOOP OAuth token manager has not been initialized")
    return _token_manager.get_access_token()
