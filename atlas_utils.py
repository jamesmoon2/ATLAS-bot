"""Shared low-level utilities for ATLAS services."""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import tempfile
from pathlib import Path
from typing import Any


def shell_command(program: str, *args: str) -> str:
    """Build a shell command with safely quoted arguments."""
    return " ".join(shlex.quote(part) for part in (program, *args))


def atomic_write_text(path: str | Path, content: str) -> None:
    """Atomically replace a UTF-8 text file."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(temp_path, target)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def atomic_write_json(path: str | Path, data: dict[str, Any]) -> None:
    """Atomically replace a JSON object file."""
    atomic_write_text(path, json.dumps(data, indent=2))


async def kill_process(process: asyncio.subprocess.Process) -> None:
    """Terminate and reap a subprocess."""
    process.kill()
    await process.communicate()


def format_process_error(
    stdout: bytes,
    stderr: bytes,
    *,
    prefix: str = "Error",
    fallback: str = "Process failed with no output.",
) -> str:
    """Build a user-facing error message from subprocess output."""
    parts = [stdout.decode().strip(), stderr.decode().strip()]
    message = "\n\n".join(part for part in parts if part)
    return f"{prefix}: {message}" if message else f"{prefix}: {fallback}"
