"""Reminder Engine - checks for upcoming events, deadlines, and sends timely reminders."""

import re
from datetime import datetime

from moha_mind.agent.memory import MemoryManager
from moha_mind.telegram_bot.bot import MohaMindBot
from moha_mind.telegram_bot.formatters import truncate_message
from moha_mind.utils.logging_config import log
from moha_mind.utils.timezone import now_ksa


class ReminderEngine:
    def __init__(self, memory: MemoryManager, bot: MohaMindBot):
        self.memory = memory
        self.bot = bot
        self._sent_reminders: set[str] = set()

    async def check_and_remind(self) -> None:
        """Check for upcoming events and deadlines, send reminders."""
        now_ksa()
        reminders = []

        tasks = self.memory.get_task_section()
        for task in tasks:
            if task["done"] or not task["due"]:
                continue
            try:
                due_date = datetime.strptime(task["due"], "%Y-%m-%d")
                from moha_mind.utils.timezone import days_until

                days = days_until(due_date)
                reminder_key = f"task:{task['text']}:{task['due']}"

                if days == 3 and f"3d:{reminder_key}" not in self._sent_reminders:
                    reminders.append(f"📋 Task due in 3 days: {task['text']}")
                    self._sent_reminders.add(f"3d:{reminder_key}")
                elif days == 1 and f"1d:{reminder_key}" not in self._sent_reminders:
                    reminders.append(f"📋 Task due TOMORROW: {task['text']}")
                    self._sent_reminders.add(f"1d:{reminder_key}")
                elif days == 0 and f"0d:{reminder_key}" not in self._sent_reminders:
                    reminders.append(f"📋 Task due TODAY: {task['text']}")
                    self._sent_reminders.add(f"0d:{reminder_key}")
                elif days < 0 and f"overdue:{reminder_key}" not in self._sent_reminders:
                    reminders.append(f"⚠️ OVERDUE task: {task['text']} (was due {task['due']})")
                    self._sent_reminders.add(f"overdue:{reminder_key}")
            except ValueError:
                continue

        expiring = self.memory.get_expiring_items(days_ahead=7)
        for item in expiring:
            if item["days_left"] == 1:
                reminder_key = f"expiry:{item['detail']}"
                if reminder_key not in self._sent_reminders:
                    reminders.append(f"🔔 Expiring tomorrow: {item['detail']}")
                    self._sent_reminders.add(reminder_key)

        content = self.memory.read("family")
        if content:
            for line in content.split("\n"):
                date_match = re.search(r"\[(\d{4}-\d{2}-\d{2})\]", line)
                if date_match:
                    try:
                        from moha_mind.utils.timezone import days_until

                        event_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                        days = days_until(event_date)
                        if days == 1:
                            reminders.append(f"👨‍👩‍👧‍👦 Tomorrow: {line.strip()}")
                    except ValueError:
                        continue

        if len(self._sent_reminders) > 200:
            self._sent_reminders = set(list(self._sent_reminders)[-100:])

        if reminders:
            message = "⏰ Reminders:\n\n" + "\n".join(f"- {r}" for r in reminders)
            for part in truncate_message(message):
                await self.bot.send_message(part)
            log.info(f"Reminder Engine: sent {len(reminders)} reminders")
