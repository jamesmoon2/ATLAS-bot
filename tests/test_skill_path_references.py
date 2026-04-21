"""Regression checks for explicit ATLAS skill path references."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / ".claude" / "skills"


def test_no_skill_contains_unresolved_vault_path_placeholder():
    for skill_path in SKILLS_DIR.glob("*.md"):
        text = skill_path.read_text(encoding="utf-8")
        assert "{vault_path}" not in text, f"{skill_path.name} still contains {{vault_path}}"


def test_training_and_vault_skills_use_explicit_paths():
    expectations = {
        "weekly-review.md": [
            "/home/jmooney/vault/Areas/Health/Training-State.md",
            "/home/jmooney/vault/Areas/Health/Workout-Logs/",
            "/home/jmooney/vault/Areas/Health/Medications.md",
            "/home/jmooney/vault/Daily/",
        ],
        "log-workout.md": [
            "/home/jmooney/vault/Areas/Health/Training-State.md",
            "/home/jmooney/vault/Areas/Health/Workout-Logs/",
        ],
        "log-cardio.md": [
            "/home/jmooney/vault/Areas/Health/Training-State.md",
            "/home/jmooney/vault/Areas/Health/Workout-Logs/",
        ],
        "log-medication.md": [
            "/home/jmooney/vault/Areas/Health/Medications.md",
        ],
        "second-brain-librarian.md": [
            "/home/jmooney/vault/System/vault-index.json",
            "/home/jmooney/vault/System/vault-index.md",
        ],
    }

    for filename, required_paths in expectations.items():
        text = (SKILLS_DIR / filename).read_text(encoding="utf-8")
        for required_path in required_paths:
            assert required_path in text, f"{filename} is missing {required_path}"


def test_daily_summary_skill_targets_plain_daily_note_filename():
    text = (SKILLS_DIR / "daily-summary.md").read_text(encoding="utf-8")

    assert "/home/jmooney/vault/Daily/[YYYY-MM-DD].md" in text
    assert "-atlas-summary.md" not in text


def test_workout_logging_uses_status_entries_not_training_checklists():
    skill_text = (SKILLS_DIR / "log-workout.md").read_text(encoding="utf-8")
    hook_text = (ROOT / "hooks" / "workout_oura_data.sh").read_text(encoding="utf-8")

    assert "status line" in skill_text
    assert "checklist after creating the log" not in skill_text
    assert "'This Week' checklist" not in hook_text
    assert "workout checkbox" not in hook_text
