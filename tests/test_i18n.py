"""Tests for the AGENT_LANGUAGE catalog and language-aware proactive messages."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from moha_mind.config import settings
from moha_mind.scheduler.reminder_engine import ReminderEngine, _SentKeys
from moha_mind.utils.i18n import (
    CATALOG,
    agent_language,
    days_ago_phrase,
    days_left_phrase,
    occasion_day_phrase,
    t,
)
from moha_mind.utils.timezone import ksa_today_str


class TestCatalog:
    def test_default_language_is_arabic(self):
        with patch.object(settings, "agent_language", "ar"):
            assert t("remind.title") == "⏰ التذكيرات:"

    def test_english_language_switches_strings(self):
        with patch.object(settings, "agent_language", "en"):
            assert t("remind.title") == "⏰ Reminders:"

    def test_unknown_language_falls_back_to_arabic(self):
        with patch.object(settings, "agent_language", "fr"):
            assert agent_language() == "ar"
            assert t("remind.title") == "⏰ التذكيرات:"

    def test_unknown_key_returns_key(self):
        assert t("nope.missing") == "nope.missing"

    def test_formatting_kwargs(self):
        with patch.object(settings, "agent_language", "en"):
            assert t("remind.task_0d", task="renew passport") == "📋 Task due today: renew passport"

    def test_explicit_lang_overrides_setting(self):
        with patch.object(settings, "agent_language", "ar"):
            assert t("chat.done_fallback", lang="en").startswith("Done")

    def test_every_key_has_both_languages(self):
        for key, entry in CATALOG.items():
            assert set(entry) == {"ar", "en"}, f"{key} is missing a language"
            assert entry["ar"].strip() and entry["en"].strip(), f"{key} has an empty string"


class TestPhrases:
    def test_days_left_phrase(self):
        assert days_left_phrase(0, lang="en") == "expires today"
        assert days_left_phrase(1, lang="en") == "1 day left"
        assert days_left_phrase(5, lang="en") == "5 days left"
        assert days_left_phrase(0, lang="ar") == "ينتهي اليوم"
        assert days_left_phrase(2, lang="ar") == "باقي يومان"

    def test_occasion_day_phrase(self):
        assert occasion_day_phrase(1, lang="en") == "tomorrow"
        assert occasion_day_phrase(3, lang="en") == "in 3 days"
        assert occasion_day_phrase(1, lang="ar") == "غدًا"
        assert occasion_day_phrase(2, lang="ar") == "بعد يومين"

    def test_days_ago_phrase(self):
        assert days_ago_phrase(1, lang="en") == "1 day ago"
        assert days_ago_phrase(9, lang="en") == "9 days ago"
        assert days_ago_phrase(2, lang="ar") == "منذ يومين"


class TestSentKeys:
    def test_prune_drops_oldest_keeps_newest(self):
        keys = _SentKeys()
        for i in range(250):
            keys.add(f"key_{i}")
        keys.prune(keep=100)
        assert len(keys) == 100
        assert "key_249" in keys
        assert "key_150" in keys
        assert "key_149" not in keys
        assert "key_0" not in keys

    def test_prune_noop_when_under_limit(self):
        keys = _SentKeys()
        keys.add("a")
        keys.prune(keep=100)
        assert "a" in keys and len(keys) == 1


class TestReminderEngineEnglish:
    @pytest.mark.asyncio
    async def test_task_due_today_sent_in_english(self, tmp_memory):
        tmp_memory.write("tasks", f"# Tasks\n\n## Active\n- [ ] Renew passport due:{ksa_today_str()}\n")
        bot = MagicMock()
        bot.send_message = AsyncMock()
        engine = ReminderEngine(tmp_memory, bot)

        with patch.object(settings, "agent_language", "en"):
            await engine.check_and_remind()

        bot.send_message.assert_awaited()
        message = bot.send_message.await_args.args[0]
        assert "⏰ Reminders:" in message
        assert "Task due today: Renew passport" in message

    @pytest.mark.asyncio
    async def test_task_due_today_sent_in_arabic_by_default(self, tmp_memory):
        tmp_memory.write("tasks", f"# Tasks\n\n## Active\n- [ ] Renew passport due:{ksa_today_str()}\n")
        bot = MagicMock()
        bot.send_message = AsyncMock()
        engine = ReminderEngine(tmp_memory, bot)

        with patch.object(settings, "agent_language", "ar"):
            await engine.check_and_remind()

        message = bot.send_message.await_args.args[0]
        assert "مهمة مستحقة اليوم" in message
