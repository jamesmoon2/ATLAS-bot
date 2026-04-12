"""Tests for the vault index builder."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from cron.vault_index import build_vault_index, render_vault_index_markdown, write_index_outputs


def _write_note(base: Path, relative_path: str, content: str, *, days_old: int) -> Path:
    path = base / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    timestamp = datetime(2026, 3, 1, tzinfo=UTC).timestamp() - (days_old * 24 * 60 * 60)
    os.utime(path, (timestamp, timestamp))
    return path


def _note_map(index: dict) -> dict[str, dict]:
    return {note["path"]: note for note in index["notes"]}


class TestBuildVaultIndex:
    def test_extracts_metadata_and_status_flags(self, tmp_path):
        vault = tmp_path / "vault"
        _write_note(
            vault,
            "Projects/ATLAS/ATLAS Plan.md",
            """---
tags:
  - atlas
  - planning
---
# ATLAS Plan

This note tracks the ATLAS roadmap. #roadmap

## Decisions
- Build the librarian

## Next Actions
- [ ] Ship the indexer

See [[Training-State]] and [[2026-03-01|daily note]].
""",
            days_old=10,
        )
        _write_note(
            vault,
            "Areas/Health/Training-State.md",
            """# Training State

Current program status.

## Waiting On
Coach response
""",
            days_old=12,
        )
        _write_note(
            vault,
            "Daily/2026-03-01.md",
            """# Daily Note

Reviewed [[ATLAS Plan]] on the train.
""",
            days_old=2,
        )
        _write_note(
            vault,
            "Projects/Old Project/Notes.md",
            """# Old Project

This project still has unresolved work.

## Unresolved
Need to decide whether to archive it.
""",
            days_old=45,
        )
        _write_note(
            vault,
            "Notes/Orphan.md",
            """# Orphan

Standalone thought with no inbound links.
""",
            days_old=40,
        )
        _write_note(
            vault,
            "Inbox/Fresh.md",
            """# Fresh

New capture item.
""",
            days_old=1,
        )

        generated_at = datetime(2026, 3, 1, tzinfo=UTC)
        index = build_vault_index(vault, stale_days=30, generated_at=generated_at)
        notes = _note_map(index)

        atlas_plan = notes["Projects/ATLAS/ATLAS Plan.md"]
        assert atlas_plan["title"] == "ATLAS Plan"
        assert atlas_plan["decision_count"] == 1
        assert atlas_plan["task_open_count"] == 1
        assert atlas_plan["status"]["has_open_loops"] is True
        assert set(atlas_plan["tags"]) >= {"atlas", "planning", "roadmap"}

        training = notes["Areas/Health/Training-State.md"]
        assert training["status"]["has_open_loops"] is True
        assert training["wikilinks_in_count"] == 1

        orphan = notes["Notes/Orphan.md"]
        assert orphan["status"]["is_orphan"] is True
        assert orphan["wikilinks_in_count"] == 0

        stale = notes["Projects/Old Project/Notes.md"]
        assert stale["status"]["is_stale"] is True
        assert stale["status"]["needs_review"] is True

        fresh = notes["Inbox/Fresh.md"]
        assert fresh["status"]["is_orphan"] is False

    def test_writes_json_and_markdown_outputs(self, tmp_path):
        vault = tmp_path / "vault"
        _write_note(
            vault,
            "Projects/ATLAS/ATLAS Plan.md",
            """# ATLAS Plan

This note tracks the ATLAS roadmap.

- [ ] Ship the indexer
""",
            days_old=5,
        )

        index = build_vault_index(vault, generated_at=datetime(2026, 3, 1, tzinfo=UTC))
        json_path, markdown_path = write_index_outputs(index, vault)

        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["notes"][0]["path"] == "Projects/ATLAS/ATLAS Plan.md"

        markdown = markdown_path.read_text(encoding="utf-8")
        assert "# Vault Index" in markdown
        assert "## Recent Notes" in markdown
        assert "Projects/ATLAS/ATLAS Plan.md" in markdown

    def test_markdown_renderer_handles_empty_index(self):
        index = {
            "generated_at": "2026-03-01T00:00:00Z",
            "vault_path": "/tmp/vault",
            "stale_days": 30,
            "notes": [],
        }

        markdown = render_vault_index_markdown(index)

        assert "# Vault Index" in markdown
        assert "- Notes indexed: 0" in markdown
        assert "## Orphan Notes" in markdown
