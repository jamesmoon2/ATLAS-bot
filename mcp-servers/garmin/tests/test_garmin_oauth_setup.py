"""Unit tests for the Garmin setup helper."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import ANY, MagicMock

import pytest

from oauth_setup import _authenticate_to_directory, _update_home_mcp_json


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


def test_authenticate_to_directory_uses_login_tokenstore_for_fresh_auth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token_dir = tmp_path / "garminconnect"
    fake_client = MagicMock()
    fake_client.get_full_name.return_value = "James Mooney"
    fake_client_cls = MagicMock(return_value=fake_client)

    monkeypatch.setattr("oauth_setup._require_garmin_client", lambda: fake_client_cls)
    monkeypatch.setattr(
        "oauth_setup._prompt_for_credentials",
        lambda: ("jamesmoon2@gmail.com", "secret"),
    )

    resolved_dir, full_name = _authenticate_to_directory(
        token_dir,
        force_reauth=True,
        is_cn=False,
    )

    fake_client_cls.assert_called_once_with(
        email="jamesmoon2@gmail.com",
        password="secret",
        is_cn=False,
        prompt_mfa=ANY,
    )
    fake_client.login.assert_called_once_with(str(token_dir))
    assert resolved_dir == token_dir
    assert full_name == "James Mooney"
