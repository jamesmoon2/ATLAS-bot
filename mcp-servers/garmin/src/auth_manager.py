"""Authentication and token resolution for the repo-managed Garmin MCP server."""

from __future__ import annotations

import json
import shutil
import stat
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import structlog

from .config import GarminSettings, settings

logger = structlog.get_logger(__name__)

TOKEN_FILENAMES = ("oauth1_token.json", "oauth2_token.json")
T = TypeVar("T")


class TokenError(RuntimeError):
    """Base exception for Garmin token issues."""


class RecoverableTokenError(TokenError):
    """Temporary issue that can be retried later."""


class UnrecoverableTokenError(TokenError):
    """Permanent issue that requires user action."""


class _MissingGarminDependencyError(Exception):
    """Sentinel exception used when garminconnect is not installed."""


GarminAuthError: type[Exception]
GarminConnectionProblem: type[Exception]
GarminRateLimitError: type[Exception]
_GARMIN_IMPORT_ERROR: ModuleNotFoundError | None = None

try:
    from garminconnect import Garmin as _GarminClient
    from garminconnect import (
        GarminConnectAuthenticationError as GarminAuthError,
    )
    from garminconnect import GarminConnectConnectionError as GarminConnectionProblem
    from garminconnect import GarminConnectTooManyRequestsError as GarminRateLimitError
except ModuleNotFoundError as exc:  # pragma: no cover - environment-specific guard
    _GARMIN_IMPORT_ERROR = exc
    _GarminClient = None
    GarminAuthError = _MissingGarminDependencyError
    GarminConnectionProblem = _MissingGarminDependencyError
    GarminRateLimitError = _MissingGarminDependencyError


GarminClientType = type[Any]


def _require_garmin_client() -> GarminClientType:
    if _GarminClient is None:
        raise UnrecoverableTokenError(
            'Garmin dependencies are missing. Run `pip install -e ".[dev]"` from the repo root.',
        ) from _GARMIN_IMPORT_ERROR
    return _GarminClient


def _token_files_present(directory: Path) -> bool:
    return all((directory / filename).exists() for filename in TOKEN_FILENAMES)


def resolve_token_dir(
    current_settings: GarminSettings = settings,
) -> tuple[Path, bool]:
    """Resolve the token directory and whether it is repo-managed."""
    if current_settings.explicit_token_dir is not None:
        return current_settings.explicit_token_dir, (
            current_settings.explicit_token_dir == current_settings.repo_token_dir
        )

    if _token_files_present(current_settings.repo_token_dir):
        return current_settings.repo_token_dir, True

    return current_settings.legacy_token_dir, False


def _load_json_from_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_json_secure(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = path.with_suffix(".tmp")
    temp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temp_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
    temp_file.replace(path)


def copy_token_dir_secure(source_dir: Path, destination_dir: Path) -> Path:
    """Copy OAuth token files into the repo-managed token directory."""
    destination_dir.mkdir(parents=True, exist_ok=True)
    for filename in TOKEN_FILENAMES:
        source = source_dir / filename
        if not source.exists():
            raise FileNotFoundError(source)
        destination = destination_dir / filename
        shutil.copyfile(source, destination)
        destination.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return destination_dir


def describe_token_dir(current_settings: GarminSettings = settings) -> dict[str, Any]:
    """Return token lookup metadata for diagnostics and setup flows."""
    resolved_dir, using_repo_tokens = resolve_token_dir(current_settings)
    return {
        "resolved_dir": resolved_dir,
        "using_repo_tokens": using_repo_tokens,
        "preferred_repo_dir": current_settings.repo_token_dir,
        "legacy_dir": current_settings.legacy_token_dir,
        "resolved_exists": _token_files_present(resolved_dir),
        "repo_exists": _token_files_present(current_settings.repo_token_dir),
        "legacy_exists": _token_files_present(current_settings.legacy_token_dir),
    }


class GarminAuthManager:
    """Thread-safe Garmin token loader for the repo-managed MCP server."""

    def __init__(
        self,
        *,
        current_settings: GarminSettings = settings,
        validate_on_init: bool | None = None,
    ) -> None:
        self._settings = current_settings
        self._validate_on_init = (
            current_settings.startup_validate if validate_on_init is None else validate_on_init
        )
        self._lock = threading.Lock()
        self._client: Any | None = None
        self._token_dir, self._using_repo_tokens = resolve_token_dir(current_settings)

        if self._validate_on_init:
            self.get_client()

    @property
    def token_dir(self) -> Path:
        return self._token_dir

    @property
    def using_repo_tokens(self) -> bool:
        return self._using_repo_tokens

    def refresh_client(self) -> Any:
        """Drop the cached Garmin client and reinitialize it from disk."""
        with self._lock:
            self._client = None
        return self.get_client()

    def get_client(self) -> Any:
        """Return a Garmin client initialized from the resolved token directory."""
        with self._lock:
            if self._client is not None:
                return self._client
            self._client = self._load_client()
            return self._client

    def run_with_client(self, operation_name: str, callback: Callable[[Any], T]) -> T:
        """Execute a Garmin API callback and normalize auth-related errors."""
        client = self.get_client()
        try:
            return callback(client)
        except GarminRateLimitError as exc:
            raise RecoverableTokenError(
                f"Garmin rate limited {operation_name}. Wait a few minutes and retry.",
            ) from exc
        except GarminAuthError as exc:
            logger.warning(
                "Garmin auth failed during request; retrying after client reload",
                operation=operation_name,
                token_dir=str(self._token_dir),
                error=str(exc),
            )
            client = self.refresh_client()
            try:
                return callback(client)
            except GarminRateLimitError as retry_exc:
                raise RecoverableTokenError(
                    f"Garmin rate limited {operation_name}. Wait a few minutes and retry.",
                ) from retry_exc
            except GarminAuthError as retry_exc:
                raise UnrecoverableTokenError(
                    "Garmin authentication is no longer valid. "
                    "Run `python mcp-servers/garmin/oauth_setup.py` to refresh the token store.",
                ) from retry_exc
        except GarminConnectionProblem as exc:
            raise RecoverableTokenError(
                f"Garmin connection failed during {operation_name}: {exc}",
            ) from exc

    def _load_client(self) -> Any:
        garmin_client_cls = _require_garmin_client()

        if not _token_files_present(self._token_dir):
            raise UnrecoverableTokenError(
                "Garmin tokens were not found. "
                f"Looked in `{self._token_dir}`. Run `python mcp-servers/garmin/oauth_setup.py`.",
            )

        client = garmin_client_cls(is_cn=self._settings.is_cn)
        try:
            client.login(str(self._token_dir))
        except FileNotFoundError as exc:
            raise UnrecoverableTokenError(
                "Garmin tokens were not found. "
                f"Looked in `{self._token_dir}`. Run `python mcp-servers/garmin/oauth_setup.py`.",
            ) from exc
        except GarminRateLimitError as exc:
            raise RecoverableTokenError(
                "Garmin rate limited token validation. Existing token files are still on disk, "
                "so wait a few minutes and retry instead of forcing reauthentication.",
            ) from exc
        except GarminAuthError as exc:
            raise UnrecoverableTokenError(
                "Garmin tokens are invalid or expired. "
                "Run `python mcp-servers/garmin/oauth_setup.py` to refresh the "
                "repo-managed token store.",
            ) from exc
        except GarminConnectionProblem as exc:
            raise RecoverableTokenError(f"Garmin token validation failed: {exc}") from exc

        logger.info(
            "Garmin token manager initialized",
            token_dir=str(self._token_dir),
            using_repo_tokens=self._using_repo_tokens,
        )
        return client
