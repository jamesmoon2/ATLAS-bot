"""Tests for the Google calendar context hook."""

from __future__ import annotations

import subprocess
from pathlib import Path


def test_calendar_context_hook_includes_bot_identity_rules():
    repo_root = Path(__file__).resolve().parents[1]
    hook_path = repo_root / "hooks" / "calendar_context.sh"

    result = subprocess.run(
        ["bash", str(hook_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    output = result.stdout
    assert "claudiamooney00@gmail.com" in output
    assert "jamesmoon2@gmail.com" in output
    assert "lorzem15@gmail.com" in output
    assert "Outbound email must come from claudiamooney00@gmail.com" in output
