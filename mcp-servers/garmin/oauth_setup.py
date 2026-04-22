#!/usr/bin/env python3
"""One-time Garmin token setup for the repo-managed ATLAS Garmin server."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import stat
from pathlib import Path
from typing import Any

from src.auth_manager import copy_token_dir_secure, describe_token_dir
from src.config import (
    GarminSettings,
    default_legacy_token_dir,
    default_repo_token_dir,
    python_for_server,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TOKEN_DIR = default_repo_token_dir()
DEFAULT_LEGACY_TOKEN_DIR = default_legacy_token_dir()


class SetupError(RuntimeError):
    """Raised when Garmin setup cannot complete."""


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
        raise SetupError(
            'Garmin dependencies are missing. Run `pip install -e ".[dev]"` from the repo root.',
        ) from _GARMIN_IMPORT_ERROR
    return _GarminClient


def _write_json_secure(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = path.with_suffix(".tmp")
    temp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temp_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
    temp_file.replace(path)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _update_home_mcp_json(token_dir: Path) -> Path:
    mcp_json_path = Path.home() / ".mcp.json"
    data = _load_json(mcp_json_path)
    servers = data.setdefault("mcpServers", {})
    servers["garmin"] = {
        "command": python_for_server(),
        "args": [str(REPO_ROOT / "mcp-servers" / "garmin" / "mcp_server.py")],
        "env": {
            "GARMIN_TOKEN_DIR": str(token_dir),
        },
    }
    _write_json_secure(mcp_json_path, data)
    return mcp_json_path


def _verify_tokens(token_dir: Path, *, is_cn: bool) -> tuple[bool, str]:
    garmin_client_cls = _require_garmin_client()

    if not token_dir.exists():
        return False, f"Token directory does not exist: {token_dir}"

    client = garmin_client_cls(is_cn=is_cn)
    try:
        client.login(str(token_dir))
        return True, client.get_full_name() or ""
    except GarminRateLimitError as exc:
        raise SetupError(
            "Garmin rate limited token verification. Existing token files were left in place; "
            "wait a few minutes before retrying verification.",
        ) from exc
    except GarminAuthError:
        return False, "Stored Garmin tokens are invalid or expired."
    except GarminConnectionProblem as exc:
        raise SetupError(f"Garmin connection failed during token verification: {exc}") from exc
    except FileNotFoundError:
        return False, "Token files were not found."


def _get_mfa() -> str:
    print("\nGarmin Connect MFA required. Please check your email or phone for the code.")
    return input("Enter MFA code: ").strip()


def _read_env_or_file(name: str, file_name: str) -> str | None:
    value = os.getenv(name)
    if value:
        return value
    file_path = os.getenv(file_name)
    if not file_path:
        return None
    return Path(file_path).expanduser().read_text(encoding="utf-8").strip()


def _prompt_for_credentials() -> tuple[str, str]:
    email = _read_env_or_file("GARMIN_EMAIL", "GARMIN_EMAIL_FILE")
    password = _read_env_or_file("GARMIN_PASSWORD", "GARMIN_PASSWORD_FILE")

    if not email:
        print("\nGarmin Connect Credentials")
        print("-" * 40)
        email = input("Email: ").strip()
    if not password:
        password = getpass.getpass("Password: ")

    if not email or not password:
        raise SetupError("Garmin email and password are required.")
    return email, password


def _authenticate_to_directory(
    token_dir: Path,
    *,
    force_reauth: bool,
    is_cn: bool,
) -> tuple[Path, str | None]:
    if not force_reauth:
        settings = GarminSettings(
            explicit_token_dir=None,
            repo_token_dir=token_dir,
            legacy_token_dir=DEFAULT_LEGACY_TOKEN_DIR,
            is_cn=is_cn,
            startup_validate=True,
        )
        current = describe_token_dir(settings)
        if current["repo_exists"]:
            valid, full_name = _verify_tokens(token_dir, is_cn=is_cn)
            if valid:
                return token_dir, full_name or None

        if current["legacy_exists"]:
            copy_token_dir_secure(DEFAULT_LEGACY_TOKEN_DIR, token_dir)
            try:
                valid, full_name = _verify_tokens(token_dir, is_cn=is_cn)
            except SetupError as exc:
                print(f"WARNING: {exc}")
                return token_dir, None
            if valid:
                return token_dir, full_name or None

    garmin_client_cls = _require_garmin_client()
    email, password = _prompt_for_credentials()
    client = garmin_client_cls(email=email, password=password, is_cn=is_cn, prompt_mfa=_get_mfa)

    try:
        # Pass the target token directory into login so current garminconnect
        # versions persist oauth tokens using their supported tokenstore flow.
        client.login(str(token_dir))
    except GarminRateLimitError as exc:
        raise SetupError(
            "Garmin rate limited login attempts. Wait a few minutes before retrying instead of "
            "forcing more authentication requests.",
        ) from exc
    except GarminAuthError as exc:
        raise SetupError(f"Garmin authentication failed: {exc}") from exc
    except GarminConnectionProblem as exc:
        raise SetupError(f"Garmin connection failed: {exc}") from exc

    return token_dir, client.get_full_name()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--token-dir",
        default=str(DEFAULT_TOKEN_DIR),
        help=f"Repo-managed Garmin token directory. Defaults to {DEFAULT_TOKEN_DIR}.",
    )
    parser.add_argument(
        "--force-reauth",
        action="store_true",
        help="Force a fresh Garmin login instead of reusing or importing existing tokens.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify the resolved Garmin token directory and exit.",
    )
    parser.add_argument(
        "--is-cn",
        action="store_true",
        help="Use Garmin Connect China (garmin.cn) instead of the international service.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    token_dir = Path(args.token_dir).expanduser()

    try:
        if args.verify_only:
            valid, full_name = _verify_tokens(token_dir, is_cn=args.is_cn)
            if not valid:
                print(f"ERROR: {full_name}")
                return 1
            print("Garmin token verification successful.")
            print(f"- Token directory: {token_dir}")
            if full_name:
                print(f"- Garmin profile: {full_name}")
            return 0

        resolved_dir, full_name = _authenticate_to_directory(
            token_dir,
            force_reauth=args.force_reauth,
            is_cn=args.is_cn,
        )
        mcp_json_path = _update_home_mcp_json(resolved_dir)
    except SetupError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("\nGarmin setup complete.")
    print(f"- Tokens available at:        {resolved_dir}")
    if full_name:
        print(f"- Connected Garmin profile:   {full_name}")
    print(f"- ~/.mcp.json updated at:     {mcp_json_path}")
    print("\nNext steps:")
    print("1. Restart Claude Code and ATLAS services.")
    print("2. Ask ATLAS to run a Garmin workout lookup for a recent date.")
    print("3. If Garmin later rate limits login, avoid forcing reauth and use --verify first.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
