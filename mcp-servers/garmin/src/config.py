"""Configuration helpers for the repo-managed Garmin MCP server."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


def repo_root() -> Path:
    """Return the ATLAS repository root."""
    return Path(__file__).resolve().parents[3]


def default_repo_token_dir() -> Path:
    """Return the repo-managed Garmin token directory."""
    return repo_root() / "mcp-servers" / "credentials" / "garminconnect"


def default_legacy_token_dir() -> Path:
    """Return the legacy token directory used by garmin-mcp-auth."""
    return Path.home() / ".garminconnect"


def _env_path(name: str) -> Path | None:
    value = os.getenv(name)
    if not value:
        return None
    return Path(value).expanduser()


def _env_bool(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def python_for_server() -> str:
    """Return the preferred Python executable for repo-managed server registration."""
    repo_python = repo_root() / "venv" / "bin" / "python3"
    return str(repo_python if repo_python.exists() else Path(sys.executable))


@dataclass(frozen=True)
class GarminSettings:
    """Runtime settings for the Garmin MCP server."""

    explicit_token_dir: Path | None
    repo_token_dir: Path
    legacy_token_dir: Path
    is_cn: bool
    startup_validate: bool

    @classmethod
    def from_env(cls) -> GarminSettings:
        return cls(
            explicit_token_dir=_env_path("GARMIN_TOKEN_DIR"),
            repo_token_dir=_env_path("GARMIN_REPO_TOKEN_DIR") or default_repo_token_dir(),
            legacy_token_dir=_env_path("GARMIN_LEGACY_TOKEN_DIR") or default_legacy_token_dir(),
            is_cn=_env_bool("GARMIN_IS_CN", default=False),
            startup_validate=_env_bool("GARMIN_STARTUP_VALIDATE", default=True),
        )

    def preferred_token_dir(self) -> Path:
        """Return the preferred repo-owned token directory."""
        return self.explicit_token_dir or self.repo_token_dir

    def candidate_token_dirs(self) -> list[Path]:
        """Return token directories in lookup order."""
        directories: list[Path] = []
        for candidate in (
            self.explicit_token_dir,
            self.repo_token_dir,
            self.legacy_token_dir,
        ):
            if candidate is None:
                continue
            if candidate not in directories:
                directories.append(candidate)
        return directories


settings = GarminSettings.from_env()
