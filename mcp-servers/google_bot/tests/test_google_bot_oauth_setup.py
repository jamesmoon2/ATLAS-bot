from __future__ import annotations

import json
from pathlib import Path

from oauth_setup import _copy_client_secret_file, _update_home_mcp_json


def test_copy_client_secret_file_copies_json(tmp_path):
    source = tmp_path / "source.json"
    destination = tmp_path / "dest.json"
    source.write_text('{"installed": {"client_id": "abc"}}', encoding="utf-8")

    copied = _copy_client_secret_file(source, destination)

    assert copied == destination
    assert destination.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")


def test_update_home_mcp_json_registers_google_bot(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    token_file = tmp_path / "google-bot-tokens.json"
    client_secret_file = tmp_path / "google-bot-client.json"
    token_file.write_text("{}", encoding="utf-8")
    client_secret_file.write_text("{}", encoding="utf-8")

    mcp_json_path = _update_home_mcp_json(token_file, client_secret_file)
    payload = json.loads(mcp_json_path.read_text(encoding="utf-8"))

    server = payload["mcpServers"]["google_bot"]
    assert server["args"][-1].endswith("mcp-servers/google_bot/mcp_server.py")
    assert server["env"]["GOOGLE_BOT_TOKEN_FILE"] == str(token_file)
    assert server["env"]["GOOGLE_BOT_CLIENT_SECRET_FILE"] == str(client_secret_file)
