"""Comprehensive tests for scheduler components."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from moha_mind.scheduler.expiry_guardian import ExpiryGuardian
from moha_mind.scheduler.reminder_engine import ReminderEngine
from moha_mind.scheduler.social_pulse import SocialPulse
from moha_mind.utils.reminder_schedule import next_reminder_after
from moha_mind.utils.timezone import now_ksa


def _make_mock_bot():
    bot = MagicMock()
    bot.send_message = AsyncMock()
    return bot


class TestExpiryGuardianExtended:
    @pytest.mark.asyncio
    async def test_no_alerts_when_empty(self, tmp_memory):
        bot = _make_mock_bot()
        guardian = ExpiryGuardian(tmp_memory, bot)
        await guardian.check_and_alert()
        bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_alert_with_items(self, tmp_memory):
        soon = (now_ksa() + timedelta(days=1)).strftime("%Y-%m-%d")
        tmp_memory.write(
            "documents",
            f"# Documents\n## Other Documents\n- Passport: A123 - Expires: {soon}\n",
        )
        bot = _make_mock_bot()
        guardian = ExpiryGuardian(tmp_memory, bot)
        await guardian.check_and_alert()
        bot.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_no_alerts_for_far_future(self, tmp_memory):
        tmp_memory.write(
            "documents",
            "# Documents\n## Other Documents\n- Passport: A123 - Expires: 2099-01-01\n",
        )
        bot = _make_mock_bot()
        guardian = ExpiryGuardian(tmp_memory, bot)
        await guardian.check_and_alert()
        bot.send_message.assert_not_called()


class TestReminderEngineExtended:
    @pytest.mark.asyncio
    async def test_no_reminders_when_empty(self, tmp_memory):
        bot = _make_mock_bot()
        engine = ReminderEngine(tmp_memory, bot)
        await engine.check_and_remind()
        bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_occasion_reminder_for_tomorrow(self, tmp_memory):
        tomorrow = (now_ksa() + timedelta(days=1)).strftime("%Y-%m-%d")
        tmp_memory.write(
            "occasions",
            f"# Important Occasions\n\n## Birthdays\n- Sara birthday: {tomorrow}\n",
        )
        bot = _make_mock_bot()
        engine = ReminderEngine(tmp_memory, bot)
        await engine.check_and_remind()
        bot.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_anniversary_reminder_sends_daily_countdown(self, tmp_memory):
        soon = (now_ksa() + timedelta(days=3)).strftime("%Y-%m-%d")
        tmp_memory.write(
            "occasions",
            f"# Important Occasions\n\n## Anniversaries\n- Marriage anniversary: {soon}\n",
        )
        bot = _make_mock_bot()
        engine = ReminderEngine(tmp_memory, bot)
        await engine.check_and_remind()
        bot.send_message.assert_called()
        message = bot.send_message.call_args.args[0]
        assert "بعد 3 أيام" in message

    @pytest.mark.asyncio
    async def test_timed_reminder_fires_and_completes(self, tmp_memory):
        now = now_ksa()
        remind_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
        event_at = (now + timedelta(minutes=25)).strftime("%Y-%m-%d %H:%M")
        tmp_memory.add_reminder("Join standup", remind_at=remind_at, event_at=event_at)

        bot = _make_mock_bot()
        engine = ReminderEngine(tmp_memory, bot)
        await engine.check_and_remind()

        bot.send_message.assert_called()
        reminders = tmp_memory.get_reminder_section(include_completed=True)
        assert any(r["text"] == "Join standup" and r["done"] for r in reminders)

    @pytest.mark.asyncio
    async def test_recurring_reminder_reschedules(self, tmp_memory):
        now = now_ksa()
        remind_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
        event_at = (now + timedelta(minutes=25)).strftime("%Y-%m-%d %H:%M")
        tmp_memory.add_reminder("Daily vitamins", remind_at=remind_at, event_at=event_at, repeat="daily")

        bot = _make_mock_bot()
        engine = ReminderEngine(tmp_memory, bot)
        await engine.check_and_remind()

        reminders = tmp_memory.get_reminder_section()
        assert any(r["text"] == "Daily vitamins" and r["repeat"] == "daily" and not r["done"] for r in reminders)

    @pytest.mark.asyncio
    async def test_multi_time_daily_reminder_reschedules_to_next_slot(self, tmp_memory):
        now = now_ksa()
        fired_at = (now - timedelta(minutes=5)).replace(second=0, microsecond=0, tzinfo=None)
        later_at = (now + timedelta(hours=1)).replace(second=0, microsecond=0, tzinfo=None)
        tmp_memory.add_reminder(
            "Medicine",
            remind_at=fired_at.strftime("%Y-%m-%d %H:%M"),
            repeat="daily",
            times=f"{fired_at.strftime('%H:%M')},{later_at.strftime('%H:%M')}",
        )
        expected = next_reminder_after(tmp_memory.get_reminder_section()[0], fired_at, reference=now)[0]

        bot = _make_mock_bot()
        engine = ReminderEngine(tmp_memory, bot)
        await engine.check_and_remind()

        reminders = tmp_memory.get_reminder_section()
        assert reminders[0]["remind_at"] == expected

    @pytest.mark.asyncio
    async def test_sent_reminders_dedup(self, tmp_memory):
        bot = _make_mock_bot()
        engine = ReminderEngine(tmp_memory, bot)
        assert len(engine._sent_reminders) == 0
        engine._sent_reminders.add("test_key")
        assert "test_key" in engine._sent_reminders

    @pytest.mark.asyncio
    async def test_pruning_at_threshold(self, tmp_memory):
        bot = _make_mock_bot()
        engine = ReminderEngine(tmp_memory, bot)
        for i in range(250):
            engine._sent_reminders.add(f"key_{i}")
        assert len(engine._sent_reminders) == 250


class TestSocialPulseExtended:
    @pytest.mark.asyncio
    async def test_no_nudges_when_empty(self, tmp_memory):
        bot = _make_mock_bot()
        pulse = SocialPulse(tmp_memory, bot)
        await pulse.check_and_nudge()
        bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_nudges_recent_contact(self, tmp_memory):
        tmp_memory.write(
            "relationships",
            "### Ahmed\n- Last contacted: 2026-04-07\n- Contact frequency: monthly\n",
        )
        bot = _make_mock_bot()
        pulse = SocialPulse(tmp_memory, bot)
        await pulse.check_and_nudge()
        bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_nudge_overdue_contact(self, tmp_memory):
        tmp_memory.write(
            "relationships",
            "### Ahmed\n- Last contacted: 2025-01-01\n- Contact frequency: monthly\n",
        )
        bot = _make_mock_bot()
        pulse = SocialPulse(tmp_memory, bot)
        await pulse.check_and_nudge()
        bot.send_message.assert_called()
