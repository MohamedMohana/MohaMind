"""Reminder Engine - checks for upcoming events, deadlines, and sends timely reminders."""

import re
from datetime import datetime

from moha_mind.agent.memory import MemoryManager
from moha_mind.telegram_bot.bot import MohaMindBot
from moha_mind.telegram_bot.formatters import truncate_message
from moha_mind.utils.logging_config import log
from moha_mind.utils.occasions import upcoming_occasions
from moha_mind.utils.reminder_schedule import next_reminder_after
from moha_mind.utils.timezone import format_datetime_ar, now_ksa


def _occasion_day_phrase(days: int) -> str:
    if days == 1:
        return "غدًا"
    if days == 2:
        return "بعد يومين"
    if 3 <= days <= 10:
        return f"بعد {days} أيام"
    return f"بعد {days} يومًا"


def _needs_daily_countdown(kind: str, source_line: str) -> bool:
    lowered = source_line.lower()
    return kind == "anniversary" or any(term in lowered for term in ("marriage", "wedding", "زواج"))


class ReminderEngine:
    def __init__(self, memory: MemoryManager, bot: MohaMindBot):
        self.memory = memory
        self.bot = bot
        self._sent_reminders: set[str] = set()

    async def check_and_remind(self) -> None:
        """Check for upcoming events and deadlines, send reminders."""
        now = now_ksa()
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
                    reminders.append(f"📋 مهمة مستحقة بعد 3 أيام: {task['text']}")
                    self._sent_reminders.add(f"3d:{reminder_key}")
                elif days == 1 and f"1d:{reminder_key}" not in self._sent_reminders:
                    reminders.append(f"📋 مهمة مستحقة غدًا: {task['text']}")
                    self._sent_reminders.add(f"1d:{reminder_key}")
                elif days == 0 and f"0d:{reminder_key}" not in self._sent_reminders:
                    reminders.append(f"📋 مهمة مستحقة اليوم: {task['text']}")
                    self._sent_reminders.add(f"0d:{reminder_key}")
                elif days < 0 and f"overdue:{reminder_key}" not in self._sent_reminders:
                    reminders.append(f"⚠️ مهمة متأخرة: {task['text']} (كان موعدها {task['due']})")
                    self._sent_reminders.add(f"overdue:{reminder_key}")
            except ValueError:
                continue

        expiring = self.memory.get_expiring_items(days_ahead=7)
        for item in expiring:
            if item["days_left"] == 1:
                reminder_key = f"expiry:{item['detail']}"
                if reminder_key not in self._sent_reminders:
                    reminders.append(f"🔔 ينتهي غدًا: {item['detail']}")
                    self._sent_reminders.add(reminder_key)

        for occasion in upcoming_occasions(self.memory.read("occasions"), days_ahead=7, reference=now):
            reminder_key = f"occasion:{occasion.kind}:{occasion.title}:{occasion.next_date.strftime('%Y-%m-%d')}"
            if (
                _needs_daily_countdown(occasion.kind, occasion.source_line)
                and 1 <= occasion.days_left <= 7
                and f"{occasion.days_left}d:{reminder_key}" not in self._sent_reminders
            ):
                reminders.append(f"💍 {_occasion_day_phrase(occasion.days_left)}: {occasion.title}")
                self._sent_reminders.add(f"{occasion.days_left}d:{reminder_key}")
            elif occasion.days_left == 7 and f"7d:{reminder_key}" not in self._sent_reminders:
                reminders.append(f"🎉 بعد أسبوع: {occasion.title}")
                self._sent_reminders.add(f"7d:{reminder_key}")
            elif occasion.days_left == 1 and f"1d:{reminder_key}" not in self._sent_reminders:
                reminders.append(f"🎁 غدًا: {occasion.title}")
                self._sent_reminders.add(f"1d:{reminder_key}")
            elif occasion.days_left == 0 and f"0d:{reminder_key}" not in self._sent_reminders:
                reminders.append(f"🎊 اليوم: {occasion.title}")
                self._sent_reminders.add(f"0d:{reminder_key}")

        for reminder in self.memory.get_reminder_section():
            remind_at = reminder.get("remind_at", "")
            if not remind_at:
                continue
            try:
                remind_dt = datetime.strptime(remind_at, "%Y-%m-%d %H:%M").replace(tzinfo=now.tzinfo)
            except ValueError:
                continue

            reminder_key = f"timed:{reminder['text']}:{remind_at}"
            if remind_dt > now or reminder_key in self._sent_reminders:
                continue

            event_suffix = (
                f"\nوقت الحدث: {format_datetime_ar(reminder['event_at'])}" if reminder.get("event_at") else ""
            )
            notes_suffix = f"\nملاحظات: {reminder['notes']}" if reminder.get("notes") else ""
            reminders.append(f"⏰ تذكير: {reminder['text']}{event_suffix}{notes_suffix}")
            self._sent_reminders.add(reminder_key)

            repeat = reminder.get("repeat", "none")
            if repeat and repeat != "none":
                next_due = next_reminder_after(reminder, remind_dt.replace(tzinfo=None), reference=now)
                if not next_due:
                    self.memory.complete_reminder(reminder["text"], remind_at=remind_at)
                    continue
                new_remind_at, new_event_at = next_due
                if new_event_at is None and reminder.get("event_at"):
                    try:
                        event_dt = datetime.strptime(reminder["event_at"], "%Y-%m-%d %H:%M")
                        next_remind_dt = datetime.strptime(new_remind_at, "%Y-%m-%d %H:%M")
                        new_event_at = (next_remind_dt + (event_dt - remind_dt.replace(tzinfo=None))).strftime(
                            "%Y-%m-%d %H:%M"
                        )
                    except ValueError:
                        new_event_at = reminder["event_at"]
                self.memory.reschedule_reminder(
                    reminder["text"],
                    current_remind_at=remind_at,
                    new_remind_at=new_remind_at,
                    new_event_at=new_event_at,
                )
            else:
                self.memory.complete_reminder(reminder["text"], remind_at=remind_at)

        family_content = self.memory.read("family")
        if family_content:
            for line in family_content.split("\n"):
                date_match = re.search(r"\[(\d{4}-\d{2}-\d{2})\]", line)
                if not date_match:
                    continue
                try:
                    from moha_mind.utils.timezone import days_until

                    event_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                    days = days_until(event_date)
                except ValueError:
                    continue

                reminder_key = f"family:{line.strip()}:{date_match.group(1)}"
                if days == 1 and f"1d:{reminder_key}" not in self._sent_reminders:
                    reminders.append(f"👨‍👩‍👧‍👦 غدًا: {line.strip()}")
                    self._sent_reminders.add(f"1d:{reminder_key}")
                elif days == 0 and f"0d:{reminder_key}" not in self._sent_reminders:
                    reminders.append(f"👨‍👩‍👧‍👦 اليوم: {line.strip()}")
                    self._sent_reminders.add(f"0d:{reminder_key}")

        if len(self._sent_reminders) > 200:
            sent = list(self._sent_reminders)
            self._sent_reminders = set(sent[-100:])

        if reminders:
            message = "⏰ التذكيرات:\n\n" + "\n".join(f"- {r}" for r in reminders)
            for part in truncate_message(message):
                await self.bot.send_message(part)
            log.info(f"Reminder Engine: sent {len(reminders)} reminders")
