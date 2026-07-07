"""Reminder MCP server - timed reminders and repeat schedules."""

from datetime import datetime
from typing import Literal, Optional

from moha_mind.agent.memory import MemoryManager
from moha_mind.utils.reminder_schedule import (
    COUNTDOWN_REPEATS,
    RECURRING_REPEATS,
    format_list_field,
    initial_remind_at,
    normalize_bool,
    normalize_times,
    normalize_weekdays,
    parse_datetime_field,
)
from moha_mind.utils.timezone import (
    format_datetime_ar,
    format_datetime_en,
    format_time_ar,
    format_time_en,
    now_ksa,
)


def _status_label(status: str, language: str) -> str:
    if language != "ar":
        return status
    return "مكتمل" if status == "done" else "نشط"


def _format_times_ar(times: str) -> str:
    return "، ".join(format_time_ar(time) for time in times.split(",") if time.strip())


def _format_times_en(times: str) -> str:
    return ", ".join(format_time_en(time) for time in times.split(",") if time.strip())


ONE_OFF_EVENT_TERMS = (
    "meeting",
    "manager",
    "tomorrow",
    "today",
    "tonight",
    "appointment",
    "call",
    "اجتماع",
    "مدير",
    "بكره",
    "بكرا",
    "غدا",
    "غدًا",
    "اليوم",
    "الليلة",
    "موعد",
    "مكالمة",
)

RECURRING_EVENT_TERMS = (
    "daily",
    "weekly",
    "monthly",
    "annually",
    "every",
    "recurring",
    "repeat",
    "يومي",
    "يومياً",
    "يوميا",
    "أسبوعي",
    "اسبوعي",
    "شهري",
    "سنوي",
    "كل ",
    "كرر",
)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _looks_like_one_off_event(text: str, event_at: str, repeat: str) -> bool:
    if repeat not in RECURRING_REPEATS or not event_at:
        return False
    return _contains_any(text, ONE_OFF_EVENT_TERMS) and not _contains_any(text, RECURRING_EVENT_TERMS)


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
        remind_at: str = "",
        event_at: str = "",
        repeat: Literal[
            "none",
            "daily",
            "weekly",
            "monthly",
            "annual",
            "every_2_days",
            "every_n_days",
            "countdown",
            "annual_countdown",
        ] = "none",
        times: list[str] | None = None,
        weekdays: list[str] | None = None,
        skip_weekends: bool = False,
        interval_days: Optional[int] = None,
        lead_days: Optional[int] = None,
        notes: str = "",
        source: str = "agent",
    ) -> str:
        """Schedule one-time, recurring, multi-time, weekday, and countdown reminders."""
        normalized_times = normalize_times(times)
        normalized_weekdays = normalize_weekdays(weekdays)
        normalized_skip_weekends = normalize_bool(skip_weekends)

        if event_at:
            parsed_event_at = parse_datetime_field(event_at, normalized_times[0] if normalized_times else "09:00")
            event_at = parsed_event_at.strftime("%Y-%m-%d %H:%M")
        if _looks_like_one_off_event(text, event_at, repeat):
            repeat = "none"
        if repeat == "none" and not remind_at and event_at:
            remind_at = event_at

        reminder = {
            "text": text,
            "remind_at": remind_at,
            "event_at": event_at,
            "repeat": repeat,
            "times": format_list_field(normalized_times),
            "weekdays": format_list_field(normalized_weekdays),
            "skip_weekends": "true" if normalized_skip_weekends else "false",
            "interval_days": str(interval_days) if interval_days else "",
            "lead_days": str(lead_days) if lead_days else "",
        }
        remind_at = initial_remind_at(reminder)
        event_at = reminder.get("event_at", event_at)
        if reminder.get("times") and not normalized_times:
            normalized_times = normalize_times(reminder["times"])

        self.memory.add_reminder(
            text=text,
            remind_at=remind_at,
            event_at=event_at,
            repeat=repeat,
            times=format_list_field(normalized_times),
            weekdays=format_list_field(normalized_weekdays),
            skip_weekends=normalized_skip_weekends,
            interval_days=interval_days,
            lead_days=lead_days,
            notes=notes,
            source=source,
        )

        repeat_text = "" if repeat == "none" else f" ({repeat})"
        schedule_parts = []
        if normalized_times:
            schedule_parts.append(f"times:{_format_times_ar(format_list_field(normalized_times))}")
        if normalized_weekdays:
            schedule_parts.append(f"weekdays:{','.join(normalized_weekdays)}")
        if normalized_skip_weekends:
            schedule_parts.append("skip weekends")
        if interval_days:
            schedule_parts.append(f"every {interval_days} days")
        if repeat in COUNTDOWN_REPEATS and lead_days:
            schedule_parts.append(f"{lead_days} day countdown")
        schedule_text = f" | {'; '.join(schedule_parts)}" if schedule_parts else ""
        display_remind_at = format_datetime_en(remind_at)
        display_suffix = f" → event at {format_datetime_en(event_at)}" if event_at else ""
        return f"Reminder scheduled: {text} at {display_remind_at}{display_suffix}{repeat_text}{schedule_text}"

    async def _list_reminders(self, days_ahead: int = 14, include_completed: bool = False, language: str = "en") -> str:
        reminders = self.memory.get_reminder_section(include_completed=include_completed)
        if not reminders:
            return "لا توجد تذكيرات مجدولة" if language == "ar" else "No reminders scheduled"

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
            if language == "ar":
                schedule = []
                if reminder.get("times"):
                    schedule.append(f"الأوقات: {_format_times_ar(reminder['times'])}")
                if reminder.get("weekdays"):
                    schedule.append(f"الأيام:{reminder['weekdays']}")
                if str(reminder.get("skip_weekends", "")).lower() == "true":
                    schedule.append("بدون نهاية الأسبوع")
                if reminder.get("interval_days"):
                    schedule.append(f"كل {reminder['interval_days']} يوم")
                if reminder.get("lead_days"):
                    schedule.append(f"قبل {reminder['lead_days']} يوم")
                schedule_suffix = f" | الجدول:{'; '.join(schedule)}" if schedule else ""
                event_suffix = (
                    f" | وقت الحدث: {format_datetime_ar(reminder['event_at'])}" if reminder.get("event_at") else ""
                )
                repeat_suffix = "" if reminder.get("repeat", "none") == "none" else f" | التكرار: {reminder['repeat']}"
                visible.append(
                    f"- [{_status_label(status, language)}] {reminder['text']} | "
                    f"وقت التذكير: {format_datetime_ar(remind_at)}"
                    f"{event_suffix}{repeat_suffix}{schedule_suffix}"
                )
            else:
                schedule = []
                if reminder.get("times"):
                    schedule.append(f"times:{_format_times_en(reminder['times'])}")
                if reminder.get("weekdays"):
                    schedule.append(f"weekdays:{reminder['weekdays']}")
                if str(reminder.get("skip_weekends", "")).lower() == "true":
                    schedule.append("skip_weekends")
                if reminder.get("interval_days"):
                    schedule.append(f"interval:{reminder['interval_days']}d")
                if reminder.get("lead_days"):
                    schedule.append(f"lead:{reminder['lead_days']}d")
                schedule_suffix = f" | schedule:{'; '.join(schedule)}" if schedule else ""
                event_suffix = (
                    f" | event:{format_datetime_en(reminder['event_at'])}" if reminder.get("event_at") else ""
                )
                repeat_suffix = "" if reminder.get("repeat", "none") == "none" else f" | repeat:{reminder['repeat']}"
                visible.append(
                    f"- [{status}] {reminder['text']} | remind:{format_datetime_en(remind_at)}"
                    f"{event_suffix}{repeat_suffix}{schedule_suffix}"
                )

        if not visible:
            if language == "ar":
                return f"لا توجد تذكيرات خلال {days_ahead} يومًا القادمة"
            return f"No reminders in the next {days_ahead} days"
        heading = "⏰ التذكيرات المجدولة:\n" if language == "ar" else "⏰ Scheduled reminders:\n"
        return heading + "\n".join(visible)

    async def _complete_reminder(self, text: str, remind_at: Optional[str] = None) -> str:
        success = self.memory.complete_reminder(text, remind_at=remind_at)
        if success:
            return f"Reminder completed: {text}"
        return f"Reminder not found: {text}"
