"""Tests for memory backups and reliability checks."""

import json
import zipfile
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from moha_mind.scheduler.reliability_guardian import ReliabilityGuardian
from moha_mind.utils.timezone import now_ksa


def _make_mock_bot():
    bot = MagicMock()
    bot.send_message = AsyncMock()
    return bot


class TestReliabilityGuardian:
    def test_create_backup_writes_zip_and_manifest(self, tmp_memory):
        tmp_memory.write("family", "Family data")
        guardian = ReliabilityGuardian(tmp_memory)

        backup = guardian.create_backup()

        assert backup.exists()
        manifest_path = guardian._manifest_path_for_backup(backup)
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "family.md" in manifest["memory_files"]
        with zipfile.ZipFile(backup) as archive:
            assert "family.md" in archive.namelist()
            assert "backup_manifest.json" in archive.namelist()

    def test_scan_detects_large_memory_shrink(self, tmp_memory):
        tmp_memory.write("family", "# Family\n" + "\n".join(f"- important fact {idx}" for idx in range(100)))
        guardian = ReliabilityGuardian(tmp_memory)
        guardian.create_backup()
        tmp_memory.write("family", "tiny")

        report = guardian.scan()

        assert any("family.md shrank" in issue for issue in report.critical)

    def test_scan_detects_stale_one_off_recurring_meeting(self, tmp_memory):
        now = now_ksa()
        past = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
        tmp_memory.add_reminder("Meeting tomorrow with manager", remind_at=past, event_at=past, repeat="daily")
        guardian = ReliabilityGuardian(tmp_memory)

        report = guardian.scan()

        assert any("One-off meeting reminder is still recurring" in issue for issue in report.critical)

    def test_repair_malformed_reminder_blocks(self, tmp_memory):
        old = (now_ksa() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M")
        tmp_memory.write(
            "reminders",
            "# Reminders\n\n## Scheduled\n"
            "- [ ] Multiline reminder:\n"
            "first detail\n"
            f"second detail | remind_at:{old} | repeat:none | source:agent\n",
        )
        guardian = ReliabilityGuardian(tmp_memory)

        repaired = guardian.repair_malformed_reminder_blocks()

        content = tmp_memory.read("reminders")
        assert repaired == 1
        assert "- [x] Multiline reminder:" in content
        assert "first detail second detail" in content

    @pytest.mark.asyncio
    async def test_run_creates_backup_and_sends_digest(self, tmp_memory, monkeypatch):
        monkeypatch.setattr("moha_mind.scheduler.reliability_guardian.settings.reliability_send_digest", True)
        tmp_memory.write("profile", "Name: Moha")
        bot = _make_mock_bot()
        guardian = ReliabilityGuardian(tmp_memory, bot)

        report = await guardian.run()

        assert report.info
        assert list((tmp_memory.memory_path / ".backups").glob("*.zip"))
        bot.send_message.assert_called()


class TestSummarySelfHealing:
    def _make_stale_summaries(self, tmp_memory, categories):
        from moha_mind.agent.memory_summarizer import MemorySummarizer

        summarizer = MemorySummarizer(tmp_memory)
        for category in categories:
            tmp_memory.write(category, f"# {category}\n\n- original entry\n")
            summarizer.get_summary(category)  # caches summary + hash
            tmp_memory.append(category, "- newer entry the cache has not seen\n")
        return summarizer

    @pytest.mark.asyncio
    async def test_run_heals_stale_summaries_instead_of_warning(self, tmp_memory):
        summarizer = self._make_stale_summaries(tmp_memory, ["reminders", "energy_log"])
        guardian = ReliabilityGuardian(tmp_memory, _make_mock_bot(), summarizer=summarizer)

        report = await guardian.run()

        assert not any("Summary cache is stale" in item for item in report.warnings)
        assert any("Refreshed stale summaries" in item for item in report.info)
        healed = next(item for item in report.info if "Refreshed stale summaries" in item)
        assert "reminders" in healed and "energy_log" in healed
        # The caches now match their sources again.
        assert guardian._stale_summary_categories() == []

    @pytest.mark.asyncio
    async def test_run_without_summarizer_still_warns(self, tmp_memory):
        self._make_stale_summaries(tmp_memory, ["reminders"])
        guardian = ReliabilityGuardian(tmp_memory, _make_mock_bot())

        report = await guardian.run()

        assert any("Summary cache is stale: reminders" in item for item in report.warnings)

    @pytest.mark.asyncio
    async def test_healing_failure_leaves_warning_in_place(self, tmp_memory):
        summarizer = self._make_stale_summaries(tmp_memory, ["reminders"])
        summarizer.refresh_async = AsyncMock(side_effect=RuntimeError("llm down"))
        guardian = ReliabilityGuardian(tmp_memory, _make_mock_bot(), summarizer=summarizer)

        report = await guardian.run()

        assert any("Summary cache is stale: reminders" in item for item in report.warnings)
        assert not any("Refreshed stale summaries" in item for item in report.info)
