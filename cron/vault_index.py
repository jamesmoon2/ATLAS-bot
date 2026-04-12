#!/usr/bin/env python3
"""Build a lightweight, queryable index of markdown notes in the vault."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BOT_DIR / ".env")

DEFAULT_EXCLUDED_DIRS = {".obsidian", "Archive", "Templates"}
OPEN_LOOP_HEADINGS = {"open questions", "unresolved", "next actions", "waiting on", "tbd"}
OPEN_LOOP_PATTERNS = (
    re.compile(r"^\s*[-*]\s+\[ \]\s+", re.MULTILINE),
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"\bTBD\b", re.IGNORECASE),
    re.compile(r"\bfollow up\b", re.IGNORECASE),
    re.compile(r"\bwaiting on\b", re.IGNORECASE),
)
INLINE_TAG_RE = re.compile(r"(?<!\w)#([A-Za-z][A-Za-z0-9/_-]*)")
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def _atomic_write_text(path: Path, content: str) -> None:
    """Atomically replace a text file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as tmp:
        tmp.write(content)
        temp_path = Path(tmp.name)
    temp_path.replace(path)


def _isoformat(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _strip_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    if not content.startswith("---\n"):
        return {}, content

    marker = "\n---\n"
    end_index = content.find(marker, 4)
    if end_index == -1:
        return {}, content

    frontmatter = content[4:end_index]
    body = content[end_index + len(marker) :]
    data: dict[str, Any] = {}
    lines = frontmatter.splitlines()
    index = 0

    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            index += 1
            continue

        if ":" not in line:
            index += 1
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        if value.startswith("[") and value.endswith("]"):
            items = [item.strip().strip("'\"") for item in value[1:-1].split(",") if item.strip()]
            data[key] = items
            index += 1
            continue

        if not value:
            items: list[str] = []
            next_index = index + 1
            while next_index < len(lines):
                next_line = lines[next_index].strip()
                if next_line.startswith("- "):
                    items.append(next_line[2:].strip().strip("'\""))
                    next_index += 1
                    continue
                break
            if items:
                data[key] = items
                index = next_index
                continue

        data[key] = value.strip("'\"")
        index += 1

    return data, body


def _extract_tags(frontmatter: dict[str, Any], body: str) -> list[str]:
    tags: set[str] = set()
    raw_tags = frontmatter.get("tags", [])
    if isinstance(raw_tags, str):
        raw_tags = [raw_tags]
    for tag in raw_tags:
        cleaned = str(tag).strip().lstrip("#")
        if cleaned:
            tags.add(cleaned)

    for match in INLINE_TAG_RE.finditer(body):
        tags.add(match.group(1))

    return sorted(tags)


def _extract_title(body: str, fallback: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def _normalize_link_target(raw_target: str) -> str:
    target = raw_target.split("|", 1)[0].split("#", 1)[0].split("^", 1)[0].strip()
    if target.endswith(".md"):
        target = target[:-3]
    return target.lstrip("/")


def _extract_wikilinks(body: str) -> list[str]:
    links = {
        normalized
        for match in WIKILINK_RE.finditer(body)
        if (normalized := _normalize_link_target(match.group(1)))
    }
    return sorted(links)


def _extract_heading_names(body: str) -> set[str]:
    return {match.group(2).strip().lower() for match in HEADING_RE.finditer(body)}


def _count_open_tasks(body: str) -> int:
    return len(re.findall(r"^\s*[-*]\s+\[ \]\s+", body, flags=re.MULTILINE))


def _count_decisions(body: str) -> int:
    lines = body.splitlines()
    count = 0
    in_decisions = False
    decision_level = 0

    for raw_line in lines:
        heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", raw_line)
        if heading_match:
            heading_text = heading_match.group(2).strip().lower()
            level = len(heading_match.group(1))
            if heading_text == "decisions":
                in_decisions = True
                decision_level = level
                continue
            if in_decisions and level <= decision_level:
                in_decisions = False

        if in_decisions and re.match(r"^\s*[-*]\s+", raw_line):
            count += 1

    return count


def _extract_summary(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith(("- ", "* ", "|", ">")):
            continue
        if stripped == "---":
            continue
        return stripped[:160]
    return "No summary available."


def _word_count(body: str) -> int:
    return len(re.findall(r"\b\w+\b", body))


def _should_exclude(relative_path: Path) -> bool:
    parts = set(relative_path.parts)
    if parts & DEFAULT_EXCLUDED_DIRS:
        return True
    return relative_path.as_posix().startswith("System/vault-index.")


def _collect_markdown_files(vault_path: Path) -> list[Path]:
    return sorted(
        path
        for path in vault_path.rglob("*.md")
        if path.is_file() and not _should_exclude(path.relative_to(vault_path))
    )


def _build_lookup(notes: list[dict[str, Any]]) -> dict[str, str]:
    candidates: dict[str, str | None] = {}
    for note in notes:
        rel_no_ext = Path(note["path"]).with_suffix("").as_posix()
        keys = {rel_no_ext, Path(note["path"]).stem}
        for key in keys:
            existing = candidates.get(key)
            if existing is None and key in candidates:
                continue
            if existing and existing != note["path"]:
                candidates[key] = None
            else:
                candidates[key] = note["path"]

    return {key: value for key, value in candidates.items() if value is not None}


def _has_open_loops(note: dict[str, Any]) -> bool:
    if note["task_open_count"] > 0:
        return True
    headings = set(note["heading_names"])
    if headings & OPEN_LOOP_HEADINGS:
        return True
    return any(pattern.search(note["body"]) for pattern in OPEN_LOOP_PATTERNS[1:])


def _note_created_datetime(note: dict[str, Any]) -> datetime:
    created_at = _parse_iso_datetime(note["created_at"])
    if created_at is not None:
        return created_at
    return _parse_iso_datetime(note["last_modified"]) or datetime.now(UTC)


def build_vault_index(
    vault_path: Path,
    *,
    stale_days: int = 30,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a deterministic vault index."""
    generated_at = generated_at or datetime.now(UTC)
    notes: list[dict[str, Any]] = []

    for path in _collect_markdown_files(vault_path):
        content = path.read_text(encoding="utf-8")
        frontmatter, body = _strip_frontmatter(content)
        relative_path = path.relative_to(vault_path).as_posix()
        stat = path.stat()
        created_at = (
            frontmatter.get("created") or frontmatter.get("created_at") or frontmatter.get("date")
        )

        note = {
            "path": relative_path,
            "title": _extract_title(body, path.stem),
            "folder": path.relative_to(vault_path).parent.as_posix()
            if path.parent != vault_path
            else ".",
            "tags": _extract_tags(frontmatter, body),
            "wikilinks_out": _extract_wikilinks(body),
            "wikilinks_in_count": 0,
            "task_open_count": _count_open_tasks(body),
            "decision_count": _count_decisions(body),
            "word_count": _word_count(body),
            "last_modified": _isoformat(datetime.fromtimestamp(stat.st_mtime, UTC)),
            "created_at": (
                created_at
                if isinstance(created_at, str)
                else _isoformat(datetime.fromtimestamp(stat.st_mtime, UTC))
            ),
            "summary": _extract_summary(body),
            "status": {},
            "heading_names": sorted(_extract_heading_names(body)),
            "body": body,
        }
        notes.append(note)

    link_lookup = _build_lookup(notes)
    backlinks: dict[str, int] = {note["path"]: 0 for note in notes}

    for note in notes:
        for link in note["wikilinks_out"]:
            target = link_lookup.get(link)
            if target and target != note["path"]:
                backlinks[target] += 1

    for note in notes:
        note["wikilinks_in_count"] = backlinks[note["path"]]
        last_modified = _parse_iso_datetime(note["last_modified"]) or generated_at
        created_dt = _note_created_datetime(note)
        age_days = (generated_at - last_modified).days
        created_age_days = (generated_at - created_dt).days
        top_level_folder = Path(note["path"]).parts[0] if Path(note["path"]).parts else ""
        has_open_loops = _has_open_loops(note)
        is_orphan = (
            note["wikilinks_in_count"] == 0
            and top_level_folder not in {"Daily", "Inbox"}
            and created_age_days >= 7
        )
        is_stale = age_days >= stale_days and (has_open_loops or top_level_folder == "Projects")

        note["status"] = {
            "is_orphan": is_orphan,
            "is_stale": is_stale,
            "has_open_loops": has_open_loops,
            "needs_review": is_orphan or is_stale or has_open_loops,
        }
        del note["heading_names"]
        del note["body"]

    notes.sort(key=lambda note: note["path"])

    return {
        "generated_at": _isoformat(generated_at),
        "vault_path": str(vault_path),
        "stale_days": stale_days,
        "notes": notes,
    }


def render_vault_index_markdown(index: dict[str, Any]) -> str:
    """Render a human-readable summary."""
    notes = index["notes"]
    generated_at = index["generated_at"]

    def sort_recent(note: dict[str, Any]) -> str:
        return note["last_modified"]

    recent_notes = sorted(notes, key=sort_recent, reverse=True)[:10]
    orphan_notes = [note for note in notes if note["status"]["is_orphan"]][:10]
    stale_notes = [note for note in notes if note["status"]["is_stale"]][:10]
    open_loop_notes = [note for note in notes if note["status"]["has_open_loops"]][:10]
    top_linked = sorted(notes, key=lambda note: note["wikilinks_in_count"], reverse=True)[:10]

    lines = [
        "# Vault Index",
        "",
        f"Generated: {generated_at}",
        "",
        "## Index Summary",
        "",
        f"- Notes indexed: {len(notes)}",
        f"- Orphan notes: {sum(1 for note in notes if note['status']['is_orphan'])}",
        f"- Stale notes: {sum(1 for note in notes if note['status']['is_stale'])}",
        f"- Notes with open loops: {sum(1 for note in notes if note['status']['has_open_loops'])}",
        "",
        "## Recent Notes",
        "",
    ]

    lines.extend(
        f"- `{note['path']}` — {note['summary']} (updated {note['last_modified']})"
        for note in recent_notes
    )
    if not recent_notes:
        lines.append("- None")

    lines.extend(["", "## Orphan Notes", ""])
    lines.extend(f"- `{note['path']}` — {note['summary']}" for note in orphan_notes)
    if not orphan_notes:
        lines.append("- None")

    lines.extend(["", "## Stale Notes", ""])
    lines.extend(
        f"- `{note['path']}` — {note['summary']} (last updated {note['last_modified']})"
        for note in stale_notes
    )
    if not stale_notes:
        lines.append("- None")

    lines.extend(["", "## Notes With Open Loops", ""])
    lines.extend(
        f"- `{note['path']}` — {note['task_open_count']} open tasks" for note in open_loop_notes
    )
    if not open_loop_notes:
        lines.append("- None")

    lines.extend(["", "## Top Linked Notes", ""])
    lines.extend(
        f"- `{note['path']}` — {note['wikilinks_in_count']} inbound links" for note in top_linked
    )
    if not top_linked:
        lines.append("- None")

    return "\n".join(lines) + "\n"


def write_index_outputs(index: dict[str, Any], vault_path: Path) -> tuple[Path, Path]:
    """Persist machine-readable and human-readable index outputs."""
    system_dir = vault_path / "System"
    json_path = system_dir / "vault-index.json"
    markdown_path = system_dir / "vault-index.md"

    _atomic_write_text(json_path, json.dumps(index, indent=2))
    _atomic_write_text(markdown_path, render_vault_index_markdown(index))
    return json_path, markdown_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ATLAS vault index")
    parser.add_argument("--stale-days", type=int, default=30, help="Days before a note is stale")
    args = parser.parse_args()

    vault_env = os.getenv("VAULT_PATH")
    if not vault_env:
        print("VAULT_PATH is not configured")
        return 1
    vault_path = Path(vault_env).expanduser()
    if not vault_path.exists():
        print(f"Vault path not found: {vault_path}")
        return 1

    index = build_vault_index(vault_path, stale_days=args.stale_days)
    json_path, markdown_path = write_index_outputs(index, vault_path)

    print(
        f"Vault index refreshed: {len(index['notes'])} notes -> "
        f"{json_path.relative_to(vault_path)} / {markdown_path.relative_to(vault_path)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
