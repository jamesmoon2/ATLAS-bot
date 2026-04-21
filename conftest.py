"""Repo-wide pytest import bootstrap for ATLAS and bundled MCP servers."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parent
MCP_SERVER_ROOTS: Final[dict[str, Path]] = {
    name: REPO_ROOT / "mcp-servers" / name for name in ("garmin", "google_bot", "oura", "whoop")
}
AMBIGUOUS_MODULES: Final[set[str]] = {"oauth_setup", "mcp_server"}
_ACTIVE_CONTEXT: str | None = None


def _clear_ambiguous_modules() -> None:
    for module_name in list(sys.modules):
        if module_name == "src" or module_name.startswith("src."):
            sys.modules.pop(module_name, None)
    for module_name in AMBIGUOUS_MODULES:
        sys.modules.pop(module_name, None)


def _set_import_roots(target_root: Path | None) -> None:
    removable = {str(root) for root in MCP_SERVER_ROOTS.values()}
    removable.add(str(REPO_ROOT))
    sys.path[:] = [entry for entry in sys.path if entry not in removable]
    sys.path.insert(0, str(REPO_ROOT))
    if target_root is not None:
        sys.path.insert(0, str(target_root))


def _context_for_path(path: Path) -> tuple[str | None, Path | None]:
    resolved_path = path.resolve()
    for name, root in MCP_SERVER_ROOTS.items():
        tests_root = root / "tests"
        if tests_root in resolved_path.parents:
            return name, root
    return None, None


def _activate_import_context(path: Path) -> None:
    global _ACTIVE_CONTEXT
    context_name, target_root = _context_for_path(path)
    if context_name == _ACTIVE_CONTEXT:
        return
    _clear_ambiguous_modules()
    _set_import_roots(target_root)
    _ACTIVE_CONTEXT = context_name


def pytest_sessionstart(session) -> None:  # noqa: ANN001
    _activate_import_context(REPO_ROOT / "tests")


def pytest_collect_file(file_path: Path, parent):  # noqa: ANN001
    _activate_import_context(Path(str(file_path)))
    return None


def pytest_runtest_setup(item) -> None:  # noqa: ANN001
    _activate_import_context(Path(str(item.path)))
