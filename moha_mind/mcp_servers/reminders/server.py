"""Reminder MCP server - timed reminders and repeat schedules."""

from datetime import datetime
from typing import Literal, Optional

from moha_mind.agent.memory import MemoryManager
from moha_mind.utils.timezone import now_ksa


class ReminderServer:
    def __init__(self, memory: MemoryManager):
        self.memory = memory

    async def handle_tool(self, tool_name: str, arguments: dict) -> str:
        handlers = {
            "add_reminder": self._add_reminder,
            "list_reminders": self._list_reminders,
            "complete_reminder": self._complete_reminder,
        }
        handler = handlers.get(tool_name)
        if handler:
            return await handler(**arguments)
        return f"Unknown tool: {tool_name}"

    async def _add_reminder(
        self,
        text: str,
        remind_at: str,
        event_at: str = "",
        repeat: Literal["none", "daily", "weekly", "monthly", "annual", "every_2_days"] = "none",
        notes: str = "",
        source: str = "agent",
    ) -> str:
        datetime.strptime(remind_at, "%Y-%m-%d %H:%M")
        if event_at:
            datetime.strptime(event_at, "%Y-%m-%d %H:%M")

        self.memory.add_reminder(
            text=text,
            remind_at=remind_at,
            event_at=event_at,
            repeat=repeat,
            notes=notes,
            source=source,
        )

        suffix = f" → event at {event_at}" if event_at else ""
        repeat_text = "" if repeat == "none" else f" ({repeat})"
        return f"Reminder scheduled: {text} at {remind_at}{suffix}{repeat_text}"

    async def _list_reminders(self, days_ahead: int = 14, include_completed: bool = False) -> str:
        reminders = self.memory.get_reminder_section(include_completed=include_completed)
        if not reminders:
            return "No reminders scheduled"

        now = now_ksa().replace(tzinfo=None)
        visible = []
        for reminder in reminders:
            remind_at = reminder.get("remind_at", "")
            try:
                remind_dt = datetime.strptime(remind_at, "%Y-%m-%d %H:%M")
            except ValueError:
                continue

            delta_days = (remind_dt.date() - now.date()).days
            if delta_days > days_ahead:
                continue

            status = "done" if reminder["done"] else "active"
            event_suffix = f" | event:{reminder['event_at']}" if reminder.get("event_at") else ""
            repeat_suffix = "" if reminder.get("repeat", "none") == "none" else f" | repeat:{reminder['repeat']}"
            visible.append(f"- [{status}] {reminder['text']} | remind:{remind_at}{event_suffix}{repeat_suffix}")

        if not visible:
            return f"No reminders in the next {days_ahead} days"
        return "⏰ Scheduled reminders:\n" + "\n".join(visible)

    async def _complete_reminder(self, text: str, remind_at: Optional[str] = None) -> str:
        success = self.memory.complete_reminder(text, remind_at=remind_at)
        if success:
            return f"Reminder completed: {text}"
        return f"Reminder not found: {text}"
