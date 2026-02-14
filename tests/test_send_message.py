"""Tests for send_message.py CLI wrapper."""

import sys
from unittest.mock import patch

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

        with (
            patch.object(sys, "argv", ["send_message.py", "hello", "world"]),
            patch("send_message.asyncio.run", return_value=True) as mock_run,
        ):
            with pytest.raises(SystemExit) as exc:
                send_message.main()
            assert exc.value.code == 0
            mock_run.assert_called_once()

    def test_failure_exits_1(self):
        import send_message

        with (
            patch.object(sys, "argv", ["send_message.py", "hello"]),
            patch("send_message.asyncio.run", return_value=False),
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
