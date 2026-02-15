"""Tests for bot.log_medication_dose() string parsing and file editing."""

import pytest

import bot


class TestMedrolDosing:
    """Medrol medication entries inserted into ## Dosing Log table."""

    @pytest.fixture(autouse=True)
    def _patch_vault(self, vault_dir, medications_file, med_config, monkeypatch):
        monkeypatch.setattr(bot, "VAULT_PATH", str(vault_dir))
        self.med_file = medications_file

    @pytest.mark.asyncio
    async def test_medrol_entry_inserted(self):
        result = await bot.log_medication_dose("Medrol 5mg", "2025-06-11T12:00:00Z")
        assert result is True
        content = self.med_file.read_text()
        assert "2025-06-11" in content
        assert "Auto-logged via" in content

    @pytest.mark.asyncio
    async def test_medrol_entry_after_last_row(self):
        """New entry appears after the last existing table row."""
        await bot.log_medication_dose("Medrol 5mg", "2025-06-11T12:00:00Z")
        lines = self.med_file.read_text().splitlines()
        # Find the new entry
        new_idx = next(i for i, line in enumerate(lines) if "2025-06-11" in line)
        # It should be after the "2025-01-01" row
        old_idx = next(i for i, line in enumerate(lines) if "2025-01-01" in line)
        assert new_idx > old_idx

    @pytest.mark.asyncio
    async def test_medrol_date_formatting(self):
        result = await bot.log_medication_dose("Medrol 5mg", "2025-03-15T08:30:00+00:00")
        assert result is True
        content = self.med_file.read_text()
        assert "2025-03-15" in content

    @pytest.mark.asyncio
    async def test_medrol_day_of_week_included(self):
        # 2025-06-11 is a Wednesday
        await bot.log_medication_dose("Medrol 5mg", "2025-06-11T08:00:00+00:00")
        content = self.med_file.read_text()
        assert "Wed AM" in content


class TestVitaplexDosing:
    """Vitaplex entries inserted into ### Dosing Log table."""

    @pytest.fixture(autouse=True)
    def _patch_vault(self, vault_dir, medications_file, med_config, monkeypatch):
        monkeypatch.setattr(bot, "VAULT_PATH", str(vault_dir))
        self.med_file = medications_file

    @pytest.mark.asyncio
    async def test_vitaplex_entry_inserted(self):
        result = await bot.log_medication_dose("Vitaplex", "2025-06-12T20:00:00Z")
        assert result is True
        content = self.med_file.read_text()
        assert "Vitaplex" in content
        assert "2025-06-12" in content

    @pytest.mark.asyncio
    async def test_vitaplex_neupro_combined_entry(self):
        result = await bot.log_medication_dose("Vitaplex + Neupro 300 units", "2025-06-12T20:00:00Z")
        assert result is True
        content = self.med_file.read_text()
        assert "Vitaplex + Neupro" in content

    @pytest.mark.asyncio
    async def test_vitaplex_after_last_vitaplex_row(self):
        """Vitaplex entry goes into the Vitaplex table, not the Medrol table."""
        await bot.log_medication_dose("Vitaplex", "2025-06-12T20:00:00Z")
        lines = self.med_file.read_text().splitlines()
        new_idx = next(i for i, line in enumerate(lines) if "2025-06-12" in line)
        old_vitaplex_idx = next(i for i, line in enumerate(lines) if "2025-01-02" in line)
        assert new_idx > old_vitaplex_idx


class TestEdgeCases:
    """Missing file, missing marker, timezone edge cases."""

    @pytest.mark.asyncio
    async def test_missing_file_returns_false(self, vault_dir, med_config, monkeypatch):
        monkeypatch.setattr(bot, "VAULT_PATH", str(vault_dir))
        result = await bot.log_medication_dose("Medrol 5mg", "2025-06-11T12:00:00Z")
        assert result is False

    @pytest.mark.asyncio
    async def test_missing_table_marker_returns_false(self, vault_dir, med_config, monkeypatch):
        monkeypatch.setattr(bot, "VAULT_PATH", str(vault_dir))
        health_dir = vault_dir / "Areas" / "Health"
        health_dir.mkdir(parents=True)
        (health_dir / "Medications.md").write_text("# Medications\n\nNo tables here.\n")
        result = await bot.log_medication_dose("Medrol 5mg", "2025-06-11T12:00:00Z")
        assert result is False

    @pytest.mark.asyncio
    async def test_utc_z_suffix_parsed(self, vault_dir, medications_file, med_config, monkeypatch):
        monkeypatch.setattr(bot, "VAULT_PATH", str(vault_dir))
        result = await bot.log_medication_dose("Medrol 5mg", "2025-06-11T12:00:00Z")
        assert result is True

    @pytest.mark.asyncio
    async def test_timezone_offset_parsed(
        self, vault_dir, medications_file, med_config, monkeypatch
    ):
        monkeypatch.setattr(bot, "VAULT_PATH", str(vault_dir))
        result = await bot.log_medication_dose("Medrol 5mg", "2025-06-11T05:00:00-07:00")
        assert result is True
