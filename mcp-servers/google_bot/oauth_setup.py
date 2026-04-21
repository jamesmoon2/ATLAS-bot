#!/usr/bin/env python3
"""One-time Google OAuth setup for the repo-managed ATLAS Google bot server."""

from __future__ import annotations

import argparse
import json
import shutil
import stat
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CLIENT_SECRET_FILE = (
    REPO_ROOT / "mcp-servers" / "credentials" / "google-bot-oauth-client.json"
)
DEFAULT_TOKEN_FILE = REPO_ROOT / "mcp-servers" / "credentials" / "google-bot-tokens.json"
SCOPES = (
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events.owned",
)


class SetupError(RuntimeError):
    """Raised when the Google OAuth setup cannot complete."""


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


def _copy_client_secret_file(source_path: Path, destination_path: Path) -> Path:
    if not source_path.exists():
        raise SetupError(f"Client secret JSON does not exist: {source_path}")

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, destination_path)
    destination_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return destination_path


def _load_google_dependencies() -> tuple[Any, Any, Any]:
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ModuleNotFoundError as exc:  # pragma: no cover - environment-specific guard
        raise SetupError(
            "Google bot dependencies are missing. Run `pip install -e \".[dev]\"` from the repo root."
        ) from exc

    return InstalledAppFlow, Credentials, build


def _run_oauth_flow(
    client_secret_file: Path,
    token_file: Path,
    *,
    host: str,
    port: int,
    open_browser: bool,
) -> dict[str, Any]:
    InstalledAppFlow, _, build = _load_google_dependencies()

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_file), SCOPES)
    credentials = flow.run_local_server(
        host=host,
        port=port,
        open_browser=open_browser,
        authorization_prompt_message=(
            "A browser window should open for Google authorization.\n"
            "If it does not, open this URL:\n{url}\n"
        ),
        success_message=(
            "ATLAS Google bot authorization is complete. You may close this window."
        ),
    )

    gmail_service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    calendar_service = build("calendar", "v3", credentials=credentials, cache_discovery=False)

    gmail_profile = gmail_service.users().getProfile(userId="me").execute()
    calendar_list = calendar_service.calendarList().list(maxResults=10).execute()

    token_payload = json.loads(credentials.to_json())
    token_payload["granted_scopes"] = sorted(credentials.scopes or [])
    token_payload["gmail_email_address"] = gmail_profile.get("emailAddress")
    token_payload["calendar_ids"] = [
        item.get("id")
        for item in (calendar_list.get("items") or [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]

    _write_json_secure(token_file, token_payload)
    return token_payload


def _python_for_server() -> str:
    repo_python = REPO_ROOT / "venv" / "bin" / "python3"
    return str(repo_python if repo_python.exists() else Path(sys.executable))


def _update_home_mcp_json(token_file: Path, client_secret_file: Path) -> Path:
    mcp_json_path = Path.home() / ".mcp.json"
    data = _load_json(mcp_json_path)
    servers = data.setdefault("mcpServers", {})
    servers["google_bot"] = {
        "command": _python_for_server(),
        "args": [str(REPO_ROOT / "mcp-servers" / "google_bot" / "mcp_server.py")],
        "env": {
            "GOOGLE_BOT_CLIENT_SECRET_FILE": str(client_secret_file),
            "GOOGLE_BOT_TOKEN_FILE": str(token_file),
        },
    }
    _write_json_secure(mcp_json_path, data)
    return mcp_json_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--client-secret-file",
        help="Absolute path to the downloaded Google OAuth desktop client JSON.",
    )
    parser.add_argument(
        "--token-file",
        default=str(DEFAULT_TOKEN_FILE),
        help=f"Where to store the bot's Google refresh token JSON. Defaults to {DEFAULT_TOKEN_FILE}.",
    )
    parser.add_argument(
        "--credentials-file",
        default=str(DEFAULT_CLIENT_SECRET_FILE),
        help=(
            "Repo-managed copy of the Google OAuth client JSON. "
            f"Defaults to {DEFAULT_CLIENT_SECRET_FILE}."
        ),
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Loopback host to listen on for the OAuth callback. Defaults to 127.0.0.1.",
    )
    parser.add_argument(
        "--port",
        default=8765,
        type=int,
        help="Loopback port to listen on for the OAuth callback. Defaults to 8765.",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Try to open a browser automatically on the current machine. Off by default for headless servers.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    source_client_secret = args.client_secret_file or input(
        "Enter the absolute path to the downloaded Google OAuth client JSON: "
    ).strip()
    if not source_client_secret:
        print("ERROR: A client secret JSON path is required.")
        return 1

    try:
        managed_client_secret = _copy_client_secret_file(
            Path(source_client_secret).expanduser(),
            Path(args.credentials_file).expanduser(),
        )
        token_payload = _run_oauth_flow(
            managed_client_secret,
            Path(args.token_file).expanduser(),
            host=args.host,
            port=args.port,
            open_browser=args.open_browser,
        )
        mcp_json_path = _update_home_mcp_json(
            Path(args.token_file).expanduser(),
            managed_client_secret,
        )
    except SetupError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("\nGoogle bot setup complete.")
    print(f"- Client credentials saved to: {managed_client_secret}")
    print(f"- Tokens saved to:             {Path(args.token_file).expanduser()}")
    print(f"- Connected Google account:    {token_payload.get('gmail_email_address', 'unknown')}")
    print(f"- Granted scopes:              {', '.join(token_payload.get('granted_scopes', []))}")
    print(f"- ~/.mcp.json updated at:      {mcp_json_path}")
    print("\nNext steps:")
    print("1. Restart Claude Code and ATLAS services.")
    print("2. Run `python3 check_google_bot_auth.py --expected-email <bot-email>`.")
    print("3. Ask ATLAS to send a test email and create a test calendar event.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
