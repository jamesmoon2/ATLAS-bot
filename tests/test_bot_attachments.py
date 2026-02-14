"""Tests for bot attachment download and prompt building."""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

import bot


class TestDownloadAttachments:
    """download_attachments() saves supported files to session dir."""

    @pytest.fixture(autouse=True)
    def _patch(self, sessions_dir, monkeypatch):
        monkeypatch.setattr(bot, "SESSIONS_DIR", str(sessions_dir))
        self.sessions_dir = sessions_dir

    def _make_att(self, filename):
        att = MagicMock()
        att.filename = filename
        att.save = AsyncMock()
        return att

    @pytest.mark.asyncio
    async def test_downloads_png(self):
        att = self._make_att("photo.png")
        paths = await bot.download_attachments(100, [att])
        assert len(paths) == 1
        att.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_downloads_pdf(self):
        att = self._make_att("doc.pdf")
        paths = await bot.download_attachments(100, [att])
        assert len(paths) == 1

    @pytest.mark.asyncio
    async def test_skips_unsupported_type(self):
        att = self._make_att("data.csv")
        paths = await bot.download_attachments(100, [att])
        assert len(paths) == 0
        att.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_uuid_prefix_in_filename(self):
        att = self._make_att("photo.jpg")
        paths = await bot.download_attachments(100, [att])
        filename = os.path.basename(paths[0])
        # UUID hex prefix is 8 chars + underscore
        assert filename[8] == "_"
        assert filename.endswith("photo.jpg")

    @pytest.mark.asyncio
    async def test_empty_list_returns_empty(self):
        paths = await bot.download_attachments(100, [])
        assert paths == []

    @pytest.mark.asyncio
    async def test_multiple_supported_files(self):
        atts = [self._make_att("a.png"), self._make_att("b.jpg"), self._make_att("c.gif")]
        paths = await bot.download_attachments(100, atts)
        assert len(paths) == 3

    @pytest.mark.asyncio
    async def test_mixed_supported_unsupported(self):
        atts = [self._make_att("a.png"), self._make_att("b.txt"), self._make_att("c.webp")]
        paths = await bot.download_attachments(100, atts)
        assert len(paths) == 2

    @pytest.mark.asyncio
    async def test_save_failure_skips_file(self):
        att = self._make_att("photo.png")
        att.save = AsyncMock(side_effect=Exception("network error"))
        paths = await bot.download_attachments(100, [att])
        assert len(paths) == 0

    @pytest.mark.asyncio
    async def test_case_insensitive_extension(self):
        att = self._make_att("PHOTO.PNG")
        paths = await bot.download_attachments(100, [att])
        assert len(paths) == 1


class TestBuildPromptWithFiles:
    """build_prompt_with_files() appends file references to content."""

    def test_no_files_passthrough(self):
        result = bot.build_prompt_with_files("hello", [])
        assert result == "hello"

    def test_files_appended(self):
        result = bot.build_prompt_with_files("analyze", ["/tmp/a.png"])
        assert "/tmp/a.png" in result
        assert "analyze" in result

    def test_empty_content_default(self):
        result = bot.build_prompt_with_files("", ["/tmp/a.png"])
        assert "analyze the attached" in result.lower()
