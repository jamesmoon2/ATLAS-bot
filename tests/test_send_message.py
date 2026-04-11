"""Tests for send_message.py CLI wrapper."""

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


class TestMainCli:
    """send_message.main() argument handling."""

    def test_no_args_exits(self):
        import send_message

        with patch.object(sys, "argv", ["send_message.py"]):
            with pytest.raises(SystemExit) as exc:
                send_message.main()
            assert exc.value.code == 1

    def test_args_joined_and_run(self):
        import send_message

        def run_and_close(coro):
            coro.close()
            return True

        with (
            patch.object(sys, "argv", ["send_message.py", "hello", "world"]),
            patch("send_message.asyncio.run", side_effect=run_and_close) as mock_run,
        ):
            with pytest.raises(SystemExit) as exc:
                send_message.main()
            assert exc.value.code == 0
            mock_run.assert_called_once()

    def test_failure_exits_1(self):
        import send_message

        def run_and_close(coro):
            coro.close()
            return False

        with (
            patch.object(sys, "argv", ["send_message.py", "hello"]),
            patch("send_message.asyncio.run", side_effect=run_and_close),
        ):
            with pytest.raises(SystemExit) as exc:
                send_message.main()
            assert exc.value.code == 1


class TestSendMessageFunction:
    """send_message.send_message() is callable with correct signature."""

    def test_channel_id_from_env(self, monkeypatch):
        """CHANNEL_ID reads from env with default fallback."""
        import send_message

        assert isinstance(send_message.CHANNEL_ID, int)

    @pytest.mark.asyncio
    async def test_returns_false_when_channel_missing(self, monkeypatch):
        import send_message

        class FakeClient:
            def __init__(self, intents):
                self._on_ready = None

            def event(self, func):
                self._on_ready = func
                return func

            def get_channel(self, channel_id):
                return None

            async def start(self, token):
                await self._on_ready()

            async def close(self):
                return None

        monkeypatch.setattr(send_message, "DISCORD_TOKEN", "token")
        monkeypatch.setattr(send_message, "CHANNEL_ID", 123)
        monkeypatch.setattr(send_message.discord, "Client", FakeClient)

        assert await send_message.send_message("hello") is False

    @pytest.mark.asyncio
    async def test_returns_true_only_after_successful_send(self, monkeypatch):
        import send_message

        channel = SimpleNamespace(send=AsyncMock())

        class FakeClient:
            def __init__(self, intents):
                self._on_ready = None

            def event(self, func):
                self._on_ready = func
                return func

            def get_channel(self, channel_id):
                return channel

            async def start(self, token):
                await self._on_ready()

            async def close(self):
                return None

        monkeypatch.setattr(send_message, "DISCORD_TOKEN", "token")
        monkeypatch.setattr(send_message, "CHANNEL_ID", 123)
        monkeypatch.setattr(send_message.discord, "Client", FakeClient)

        assert await send_message.send_message("hello") is True
        channel.send.assert_awaited_once_with("hello")
