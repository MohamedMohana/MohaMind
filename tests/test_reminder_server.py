from datetime import timedelta

import pytest

from moha_mind.mcp_servers.reminders.server import ReminderServer
from moha_mind.utils.timezone import now_ksa


class TestReminderServer:
    @pytest.mark.asyncio
    async def test_add_reminder(self, tmp_memory):
        server = ReminderServer(tmp_memory)
        result = await server._add_reminder(
            text="Call Ahmad",
            remind_at="2026-04-13 09:00",
            event_at="2026-04-13 09:30",
            repeat="none",
        )
        assert "Reminder scheduled" in result
        assert "Call Ahmad" in tmp_memory.read("reminders")

    @pytest.mark.asyncio
    async def test_add_daily_reminder_with_multiple_times(self, tmp_memory):
        server = ReminderServer(tmp_memory)
        result = await server._add_reminder(
            text="Take medicine 2",
            repeat="daily",
            times=["05:00", "17:00"],
        )
        content = tmp_memory.read("reminders")
        assert "Reminder scheduled" in result
        assert "5:00 ص" in result
        assert "5:00 م" in result
        assert "times:05:00,17:00" in content
        assert "repeat:daily" in content

    @pytest.mark.asyncio
    async def test_add_weekly_reminder_with_weekday(self, tmp_memory):
        server = ReminderServer(tmp_memory)
        await server._add_reminder(
            text="Take medicine 1",
            repeat="weekly",
            times=["09:00"],
            weekdays=["wed"],
        )
        reminder = tmp_memory.get_reminder_section()[0]
        assert reminder["weekdays"] == "wed"
        assert reminder["remind_at"].endswith("09:00")

    @pytest.mark.asyncio
    async def test_one_off_meeting_is_not_left_recurring(self, tmp_memory):
        server = ReminderServer(tmp_memory)
        event_at = (now_ksa() + timedelta(days=1)).strftime("%Y-%m-%d 09:00")

        await server._add_reminder(
            text="Meeting tomorrow with my manager",
            event_at=event_at,
            repeat="daily",
            times=["09:00"],
        )

        reminder = tmp_memory.get_reminder_section()[0]
        assert reminder["repeat"] == "none"
        assert reminder["remind_at"] == event_at

    @pytest.mark.asyncio
    async def test_add_annual_countdown_reminder(self, tmp_memory):
        server = ReminderServer(tmp_memory)
        await server._add_reminder(
            text="Marriage anniversary",
            event_at="2026-05-10 09:00",
            repeat="annual_countdown",
            times=["09:00"],
            lead_days=7,
        )
        content = tmp_memory.read("reminders")
        assert "repeat:annual_countdown" in content
        assert "lead_days:7" in content

    @pytest.mark.asyncio
    async def test_list_reminders(self, tmp_memory):
        tmp_memory.add_reminder("Doctor visit", remind_at="2026-04-13 08:00", event_at="2026-04-13 09:00")
        server = ReminderServer(tmp_memory)
        result = await server._list_reminders(days_ahead=365)
        assert "Doctor visit" in result

    @pytest.mark.asyncio
    async def test_list_reminders_arabic(self, tmp_memory):
        tmp_memory.add_reminder("زيارة الطبيب", remind_at="2026-04-13 08:00", event_at="2026-04-13 09:00")
        server = ReminderServer(tmp_memory)
        result = await server._list_reminders(days_ahead=365, language="ar")
        assert "التذكيرات المجدولة" in result
        assert "زيارة الطبيب" in result
        assert "وقت التذكير" in result
        assert "8:00 ص" in result
        assert "9:00 ص" in result

    @pytest.mark.asyncio
    async def test_complete_reminder(self, tmp_memory):
        tmp_memory.add_reminder("Pay rent", remind_at="2026-04-13 08:00")
        server = ReminderServer(tmp_memory)
        result = await server._complete_reminder(text="Pay rent", remind_at="2026-04-13 08:00")
        assert "completed" in result.lower()
