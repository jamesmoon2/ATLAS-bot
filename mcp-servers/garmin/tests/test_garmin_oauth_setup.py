"""Unit tests for the Garmin setup helper."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from oauth_setup import _update_home_mcp_json


def test_update_home_mcp_json_registers_garmin_server(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    token_dir = tmp_path / "garminconnect"
    token_dir.mkdir()
    (token_dir / "oauth1_token.json").write_text("{}", encoding="utf-8")
    (token_dir / "oauth2_token.json").write_text("{}", encoding="utf-8")

    mcp_json_path = _update_home_mcp_json(token_dir)
    payload = json.loads(mcp_json_path.read_text(encoding="utf-8"))

    server = payload["mcpServers"]["garmin"]
    assert server["args"][-1].endswith("mcp-servers/garmin/mcp_server.py")
    assert server["env"]["GARMIN_TOKEN_DIR"] == str(token_dir)
