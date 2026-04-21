#!/usr/bin/env python3
"""One-time WHOOP OAuth setup for the repo-managed MCP server."""

from __future__ import annotations

import getpass
import json
import secrets
import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CREDENTIALS_FILE = REPO_ROOT / "mcp-servers" / "credentials" / "whoop-oauth.keys.json"
DEFAULT_TOKEN_FILE = REPO_ROOT / "mcp-servers" / "credentials" / "whoop-tokens.json"
DEFAULT_REDIRECT_URI = "http://localhost:3000/callback"
AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
VALIDATION_URL = "https://api.prod.whoop.com/developer/v2/user/profile/basic"
SCOPES = "read:recovery read:cycles read:sleep read:workout read:profile offline"


def _write_json_secure(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = path.with_suffix(".tmp")
    temp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temp_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
    temp_file.replace(path)


def _load_json(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _validate_access_token(access_token: str) -> bool:
    try:
        response = httpx.get(
            VALIDATION_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
    except httpx.RequestError:
        return False
    return response.status_code == 200


def _update_home_mcp_json(credentials_file: Path, token_file: Path) -> Path:
    mcp_json_path = Path.home() / ".mcp.json"
    data = _load_json(mcp_json_path)
    servers = data.setdefault("mcpServers", {})
    servers["whoop"] = {
        "command": sys.executable,
        "args": [str(REPO_ROOT / "mcp-servers" / "whoop" / "mcp_server.py")],
        "env": {
            "WHOOP_OAUTH_CREDENTIALS": str(credentials_file),
            "WHOOP_TOKEN_FILE": str(token_file),
        },
    }
    _write_json_secure(mcp_json_path, data)
    return mcp_json_path


def main() -> int:
    print("=" * 70)
    print("WHOOP OAuth Setup")
    print("=" * 70)

    existing_credentials = _load_json(DEFAULT_CREDENTIALS_FILE)

    client_id = (
        existing_credentials.get("client_id")
        or input("\nEnter your WHOOP Client ID: ").strip()
    )
    if not client_id:
        print("ERROR: WHOOP Client ID is required")
        return 1

    existing_secret = existing_credentials.get("client_secret")
    client_secret = existing_secret or getpass.getpass("Enter your WHOOP Client Secret: ").strip()
    if not client_secret:
        print("ERROR: WHOOP Client Secret is required")
        return 1

    redirect_uri = (
        existing_credentials.get("redirect_uri")
        or input(
            f"Enter your WHOOP Redirect URI [{DEFAULT_REDIRECT_URI}]: ",
        ).strip()
        or DEFAULT_REDIRECT_URI
    )

    oauth_state = secrets.token_urlsafe(24)
    auth_url = f"{AUTH_URL}?{urlencode({
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': SCOPES,
        'state': oauth_state,
    })}"

    print("\nOpen this URL in your browser and authorize the app:\n")
    print(auth_url)
    print("\nAfter authorization, copy the full callback URL from the browser.")

    callback_url = input("\nPaste the full callback URL here: ").strip()
    try:
        parsed = urlparse(callback_url)
        query_params = parse_qs(parsed.query)
        error = query_params.get("error", [None])[0]
        if error:
            description = query_params.get("error_description", ["Unknown OAuth error"])[0]
            hint = query_params.get("error_hint", [None])[0]
            print(f"ERROR: WHOOP authorization failed: {description}")
            if hint:
                print(f"Hint: {hint}")
            return 1

        returned_state = query_params.get("state", [None])[0]
        if returned_state != oauth_state:
            print("ERROR: WHOOP returned an invalid OAuth state. Please retry the setup flow.")
            return 1

        code = query_params["code"][0]
    except Exception as exc:
        print(f"ERROR: Failed to extract authorization code: {exc}")
        return 1

    print("\nExchanging authorization code for tokens...")
    try:
        response = httpx.post(
            TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            timeout=30.0,
        )
    except httpx.RequestError as exc:
        print(f"ERROR: Network error during token exchange: {exc}")
        return 1

    if response.status_code != 200:
        print(f"ERROR: WHOOP token exchange failed (HTTP {response.status_code})")
        return 1

    payload = response.json()
    access_token = payload["access_token"]
    refresh_token = payload["refresh_token"]
    expires_in = int(payload.get("expires_in", 3600))

    if not _validate_access_token(access_token):
        print("ERROR: WHOOP access token validation failed")
        return 1

    _write_json_secure(
        DEFAULT_CREDENTIALS_FILE,
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        },
    )
    _write_json_secure(
        DEFAULT_TOKEN_FILE,
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat(),
        },
    )

    mcp_json_path = _update_home_mcp_json(DEFAULT_CREDENTIALS_FILE, DEFAULT_TOKEN_FILE)

    print("\nSetup complete.")
    print(f"- Credentials saved to: {DEFAULT_CREDENTIALS_FILE}")
    print(f"- Tokens saved to:      {DEFAULT_TOKEN_FILE}")
    print(f"- Claude MCP config updated: {mcp_json_path}")
    print(f"- Token lifetime: about {expires_in // 60} minutes")
    print("\nRestart Claude Code and the ATLAS bot services before using WHOOP tools.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
