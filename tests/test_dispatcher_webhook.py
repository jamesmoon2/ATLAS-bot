"""Tests for dispatcher send_webhook() Discord webhook delivery."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import cron.dispatcher as dispatcher


class TestSendWebhook:
    """send_webhook() posts content to Discord webhook URL."""

    @pytest.mark.asyncio
    @patch("cron.dispatcher.aiohttp.ClientSession")
    async def test_short_message_single_chunk(self, mock_session_cls, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/webhook")

        mock_resp = MagicMock()
        mock_resp.status = 204
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        result = await dispatcher.send_webhook("short msg", {"url_env": "DISCORD_WEBHOOK_URL"})
        assert result is True
        mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    @patch("cron.dispatcher.aiohttp.ClientSession")
    async def test_long_message_chunked(self, mock_session_cls, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/webhook")

        mock_resp = MagicMock()
        mock_resp.status = 204
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        long_msg = "x" * 4000  # > 1900 char limit
        result = await dispatcher.send_webhook(long_msg, {"url_env": "DISCORD_WEBHOOK_URL"})
        assert result is True
        assert mock_session.post.call_count >= 2

    @pytest.mark.asyncio
    async def test_missing_url_returns_false(self, monkeypatch):
        monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
        result = await dispatcher.send_webhook("msg", {"url_env": "DISCORD_WEBHOOK_URL"})
        assert result is False

    @pytest.mark.asyncio
    @patch("cron.dispatcher.aiohttp.ClientSession")
    async def test_failure_status_code(self, mock_session_cls, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/webhook")

        mock_resp = MagicMock()
        mock_resp.status = 429  # Rate limited
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        result = await dispatcher.send_webhook("msg", {"url_env": "DISCORD_WEBHOOK_URL"})
        assert result is False

    @pytest.mark.asyncio
    @patch("cron.dispatcher.aiohttp.ClientSession")
    async def test_network_error_returns_false(self, mock_session_cls, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/webhook")

        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=Exception("Connection refused"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        result = await dispatcher.send_webhook("msg", {"url_env": "DISCORD_WEBHOOK_URL"})
        assert result is False

    @pytest.mark.asyncio
    @patch("cron.dispatcher.aiohttp.ClientSession")
    async def test_custom_username(self, mock_session_cls, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/webhook")

        mock_resp = MagicMock()
        mock_resp.status = 204
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        await dispatcher.send_webhook(
            "msg",
            {"url_env": "DISCORD_WEBHOOK_URL", "username": "Custom Bot"},
        )
        call_kwargs = mock_session.post.call_args[1]
        assert call_kwargs["json"]["username"] == "Custom Bot"

    @pytest.mark.asyncio
    @patch("cron.dispatcher.aiohttp.ClientSession")
    async def test_success_status_200(self, mock_session_cls, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/webhook")

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        result = await dispatcher.send_webhook("msg", {"url_env": "DISCORD_WEBHOOK_URL"})
        assert result is True
