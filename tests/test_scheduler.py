"""Tests for scheduler components."""

from unittest.mock import AsyncMock

import pytest

from moha_mind.agent.memory import MemoryManager
from moha_mind.scheduler.expiry_guardian import ExpiryGuardian
from moha_mind.scheduler.reminder_engine import ReminderEngine
from moha_mind.scheduler.social_pulse import SocialPulse
from moha_mind.utils.timezone import now_ksa


@pytest.fixture
def memory(tmp_path):
    return MemoryManager(memory_dir=str(tmp_path))


@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


class TestExpiryGuardian:
    @pytest.mark.asyncio
    async def test_no_alerts_when_empty(self, memory, mock_bot):
        guardian = ExpiryGuardian(memory, mock_bot)
        await guardian.check_and_alert()
        mock_bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_alert_on_expiring(self, memory, mock_bot):
        from datetime import timedelta

        tomorrow = (now_ksa() + timedelta(days=3)).strftime("%Y-%m-%d")
        memory.write("documents", f"# Docs\nPassport: ABC - Expires: {tomorrow}\n")
        guardian = ExpiryGuardian(memory, mock_bot)
        await guardian.check_and_alert()
        mock_bot.send_message.assert_called()


class TestReminderEngine:
    @pytest.mark.asyncio
    async def test_no_reminders_when_empty(self, memory, mock_bot):
        engine = ReminderEngine(memory, mock_bot)
        await engine.check_and_remind()
        mock_bot.send_message.assert_not_called()


class TestSocialPulse:
    @pytest.mark.asyncio
    async def test_no_nudges_when_empty(self, memory, mock_bot):
        pulse = SocialPulse(memory, mock_bot)
        await pulse.check_and_nudge()
        mock_bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_nudge_overdue_contact(self, memory, mock_bot):
        memory.write(
            "relationships",
            "# Relationships\n\n## Close Friends\n"
            "### Ahmed\n- Last contacted: 2025-06-15 (phone)\n"
            "- Contact frequency: monthly\n- Birthday: 1990-07-20\n",
        )
        pulse = SocialPulse(memory, mock_bot)
        await pulse.check_and_nudge()
        mock_bot.send_message.assert_called()
