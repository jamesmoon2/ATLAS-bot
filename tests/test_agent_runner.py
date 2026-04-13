"""Tests for the provider-agnostic agent runner."""

from __future__ import annotations

import pytest

import agent_runner


class _FakeProcess:
    def __init__(self):
        self.returncode = 0

    async def communicate(self):
        return b"", b""


@pytest.mark.asyncio
async def test_run_codex_exec_uses_argument_separator(tmp_path, monkeypatch):
    captured: dict[str, tuple] = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return _FakeProcess()

    monkeypatch.setattr(agent_runner.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    await agent_runner._run_codex_exec(
        workdir=str(tmp_path),
        prompt="---\nUser request:\nReply with READY",
        model="gpt-5.4",
        bot_dir=str(tmp_path),
        vault_path=str(tmp_path),
        image_paths=[],
        resume_last=False,
        timeout=10,
    )

    args = list(captured["args"])
    separator_index = args.index("--")
    assert args[separator_index + 1] == "---\nUser request:\nReply with READY"
