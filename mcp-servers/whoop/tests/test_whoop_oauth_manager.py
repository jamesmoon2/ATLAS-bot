"""Unit tests for the WHOOP OAuth token manager."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.oauth_manager import (
    OAuthTokenManager,
    RecoverableTokenError,
    UnrecoverableTokenError,
    _load_json_from_file,
    _write_json_secure,
)


class TestOAuthTokenManager:
    """Tests for OAuthTokenManager."""

    def test_get_access_token_returns_current_when_valid(self, tmp_path: Path) -> None:
        manager = OAuthTokenManager(
            client_id="client",
            client_secret="secret",
            access_token="access",
            refresh_token="refresh",
            token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            token_file=tmp_path / "tokens.json",
            validate_on_init=False,
        )

        assert manager.get_access_token() == "access"

    @patch("src.oauth_manager.httpx.post")
    def test_refresh_on_expiration(self, mock_post: MagicMock, tmp_path: Path) -> None:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 3600,
            },
        )

        manager = OAuthTokenManager(
            client_id="client",
            client_secret="secret",
            access_token="old-access",
            refresh_token="refresh",
            token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            token_file=tmp_path / "tokens.json",
            validate_on_init=False,
        )

        assert manager.get_access_token() == "new-access"
        assert mock_post.call_count == 1

    @patch("src.oauth_manager.httpx.post")
    def test_unrecoverable_error_on_401(self, mock_post: MagicMock, tmp_path: Path) -> None:
        mock_post.return_value = MagicMock(status_code=401)

        manager = OAuthTokenManager(
            client_id="client",
            client_secret="secret",
            access_token="access",
            refresh_token="refresh",
            token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            token_file=tmp_path / "tokens.json",
            validate_on_init=False,
        )

        with pytest.raises(UnrecoverableTokenError):
            manager.get_access_token()

    @patch("src.oauth_manager.httpx.post")
    def test_retry_on_network_error(self, mock_post: MagicMock, tmp_path: Path) -> None:
        mock_post.side_effect = [
            httpx.RequestError("boom"),
            httpx.RequestError("boom"),
            MagicMock(
                status_code=200,
                json=lambda: {
                    "access_token": "new-access",
                    "refresh_token": "new-refresh",
                    "expires_in": 3600,
                },
            ),
        ]

        manager = OAuthTokenManager(
            client_id="client",
            client_secret="secret",
            access_token="access",
            refresh_token="refresh",
            token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            token_file=tmp_path / "tokens.json",
            validate_on_init=False,
        )

        assert manager.get_access_token() == "new-access"
        assert mock_post.call_count == 3

    def test_missing_refresh_token_is_unrecoverable(self, tmp_path: Path) -> None:
        manager = OAuthTokenManager(
            client_id="client",
            client_secret="secret",
            access_token=None,
            refresh_token=None,
            token_expires_at=None,
            token_file=tmp_path / "tokens.json",
            validate_on_init=False,
        )

        with pytest.raises(UnrecoverableTokenError):
            manager.get_access_token()


class TestTokenFilePersistence:
    """Tests for WHOOP token file persistence."""

    def test_write_and_load_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        token_file = tmp_path / "whoop-tokens.json"
        monkeypatch.setattr("src.oauth_manager.TOKEN_FILE", token_file)

        data = {"access_token": "access", "refresh_token": "refresh"}
        _write_json_secure(token_file, data)

        assert _load_json_from_file(token_file) == data

    def test_file_permissions(self, tmp_path: Path) -> None:
        token_file = tmp_path / "whoop-tokens.json"
        _write_json_secure(token_file, {"access_token": "access"})

        mode = token_file.stat().st_mode & 0o777
        assert mode == 0o600
