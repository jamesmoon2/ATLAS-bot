"""Unit tests for Garmin token resolution helpers."""

from __future__ import annotations

import json
from pathlib import Path

from src.auth_manager import (
    _load_json_from_file,
    _write_json_secure,
    copy_token_dir_secure,
    resolve_token_dir,
)
from src.config import GarminSettings


def test_resolve_token_dir_prefers_repo_tokens_when_present(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    legacy_dir = tmp_path / "legacy"
    repo_dir.mkdir()
    legacy_dir.mkdir()
    (repo_dir / "oauth1_token.json").write_text("{}", encoding="utf-8")
    (repo_dir / "oauth2_token.json").write_text("{}", encoding="utf-8")
    (legacy_dir / "oauth1_token.json").write_text("{}", encoding="utf-8")
    (legacy_dir / "oauth2_token.json").write_text("{}", encoding="utf-8")

    resolved, using_repo_tokens = resolve_token_dir(
        GarminSettings(
            explicit_token_dir=None,
            repo_token_dir=repo_dir,
            legacy_token_dir=legacy_dir,
            is_cn=False,
            startup_validate=True,
        ),
    )

    assert resolved == repo_dir
    assert using_repo_tokens is True


def test_resolve_token_dir_falls_back_to_legacy_when_repo_missing(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    (legacy_dir / "oauth1_token.json").write_text("{}", encoding="utf-8")
    (legacy_dir / "oauth2_token.json").write_text("{}", encoding="utf-8")

    resolved, using_repo_tokens = resolve_token_dir(
        GarminSettings(
            explicit_token_dir=None,
            repo_token_dir=repo_dir,
            legacy_token_dir=legacy_dir,
            is_cn=False,
            startup_validate=True,
        ),
    )

    assert resolved == legacy_dir
    assert using_repo_tokens is False


def test_copy_token_dir_secure_copies_required_files(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "oauth1_token.json").write_text('{"oauth_token":"a"}', encoding="utf-8")
    (source_dir / "oauth2_token.json").write_text('{"refresh_token":"b"}', encoding="utf-8")

    destination_dir = copy_token_dir_secure(source_dir, tmp_path / "dest")

    assert (
        json.loads((destination_dir / "oauth1_token.json").read_text(encoding="utf-8"))[
            "oauth_token"
        ]
        == "a"
    )
    assert (destination_dir / "oauth1_token.json").stat().st_mode & 0o777 == 0o600
    assert (destination_dir / "oauth2_token.json").stat().st_mode & 0o777 == 0o600


def test_write_and_load_json_secure_round_trips(tmp_path: Path) -> None:
    json_path = tmp_path / "tokens.json"
    payload = {"access_token": "token"}
    _write_json_secure(json_path, payload)

    assert _load_json_from_file(json_path) == payload
