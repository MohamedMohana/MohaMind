import pytest

from moha_mind.mcp_servers.reminders.server import ReminderServer


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
    async def test_list_reminders(self, tmp_memory):
        tmp_memory.add_reminder("Doctor visit", remind_at="2026-04-13 08:00", event_at="2026-04-13 09:00")
        server = ReminderServer(tmp_memory)
        result = await server._list_reminders(days_ahead=365)
        assert "Doctor visit" in result

    @pytest.mark.asyncio
    async def test_complete_reminder(self, tmp_memory):
        tmp_memory.add_reminder("Pay rent", remind_at="2026-04-13 08:00")
        server = ReminderServer(tmp_memory)
        result = await server._complete_reminder(text="Pay rent", remind_at="2026-04-13 08:00")
        assert "completed" in result.lower()
