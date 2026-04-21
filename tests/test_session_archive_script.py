"""Regression tests for the session archive shell script."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "cron" / "session_archive.sh"


def test_session_archive_preserves_skills_symlink_and_resets_session(tmp_path):
    bot_dir = tmp_path / "bot"
    session_dir = bot_dir / "sessions" / "123"
    claude_dir = session_dir / ".claude"
    skills_target = bot_dir / ".claude" / "skills"
    home_dir = tmp_path / "home"

    skills_target.mkdir(parents=True)
    claude_dir.mkdir(parents=True)
    (claude_dir / "settings.json").write_text("{}", encoding="utf-8")
    (claude_dir / "skills").symlink_to(skills_target)
    (session_dir / "AGENTS.md").write_text("agents", encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "BOT_DIR": str(bot_dir),
            "DISCORD_CHANNEL_ID": "123",
            "HOME": str(home_dir),
        }
    )

    subprocess.run(
        ["bash", str(SCRIPT)],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
        timeout=10,
    )

    archive_root = session_dir / ".archive"
    archives = sorted(archive_root.iterdir())
    assert len(archives) == 1

    archived_claude = archives[0] / ".claude"
    archived_skills = archived_claude / "skills"
    assert archived_claude.is_dir()
    assert archived_skills.is_symlink()
    assert archived_skills.resolve() == skills_target.resolve()

    assert not claude_dir.exists()
    assert not (session_dir / "AGENTS.md").exists()
