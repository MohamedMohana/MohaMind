"""Flexible reminder schedule helpers."""

import calendar
import re
from datetime import date, datetime, time, timedelta
from typing import Any

from moha_mind.utils.date_helpers import advance_recurrence, is_weekend
from moha_mind.utils.timezone import now_ksa, to_ksa

DATETIME_FORMAT = "%Y-%m-%d %H:%M"
DATE_FORMAT = "%Y-%m-%d"

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

WEEKDAY_ALIASES = {
    "mon": "mon",
    "monday": "mon",
    "الاثنين": "mon",
    "الإثنين": "mon",
    "tue": "tue",
    "tuesday": "tue",
    "الثلاثاء": "tue",
    "wed": "wed",
    "wednesday": "wed",
    "الأربعاء": "wed",
    "الاربعاء": "wed",
    "thu": "thu",
    "thursday": "thu",
    "الخميس": "thu",
    "fri": "fri",
    "friday": "fri",
    "الجمعة": "fri",
    "sat": "sat",
    "saturday": "sat",
    "السبت": "sat",
    "sun": "sun",
    "sunday": "sun",
    "الأحد": "sun",
    "الاحد": "sun",
}

WEEKDAY_TO_INDEX = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}

INDEX_TO_WEEKDAY = {value: key for key, value in WEEKDAY_TO_INDEX.items()}

RECURRING_REPEATS = {"daily", "weekly", "monthly", "annual", "every_2_days", "every_n_days"}
COUNTDOWN_REPEATS = {"countdown", "annual_countdown"}


def normalize_list_field(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        raw_items = value
    else:
        raw_items = str(value).split(",")
    return [str(item).strip() for item in raw_items if str(item).strip()]


def normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def normalize_time_value(value: str) -> str:
    raw = value.translate(ARABIC_DIGITS).strip().lower()
    raw = re.sub(r"\s+", "", raw)
    raw = raw.replace(".", ":")

    am_pm_match = re.match(r"^(\d{1,2})(?::(\d{2}))?(am|pm)$", raw)
    if am_pm_match:
        hour = int(am_pm_match.group(1))
        minute = int(am_pm_match.group(2) or "0")
        period = am_pm_match.group(3)
        if hour < 1 or hour > 12 or minute > 59:
            raise ValueError(f"Invalid time: {value}")
        if period == "am":
            hour = 0 if hour == 12 else hour
        else:
            hour = 12 if hour == 12 else hour + 12
        return f"{hour:02d}:{minute:02d}"

    if re.match(r"^\d{1,2}$", raw):
        hour = int(raw)
        if hour > 23:
            raise ValueError(f"Invalid time: {value}")
        return f"{hour:02d}:00"

    time_match = re.match(r"^(\d{1,2}):(\d{2})$", raw)
    if not time_match:
        raise ValueError(f"Invalid time: {value}")

    hour = int(time_match.group(1))
    minute = int(time_match.group(2))
    if hour > 23 or minute > 59:
        raise ValueError(f"Invalid time: {value}")
    return f"{hour:02d}:{minute:02d}"


def normalize_times(value: Any) -> list[str]:
    times = [normalize_time_value(item) for item in normalize_list_field(value)]
    return sorted(set(times))


def normalize_weekdays(value: Any) -> list[str]:
    weekdays = []
    for item in normalize_list_field(value):
        key = item.translate(ARABIC_DIGITS).strip().lower()
        normalized = WEEKDAY_ALIASES.get(key)
        if not normalized:
            raise ValueError(f"Invalid weekday: {item}")
        weekdays.append(normalized)
    return sorted(set(weekdays), key=lambda day: WEEKDAY_TO_INDEX[day])


def format_list_field(values: list[str]) -> str:
    return ",".join(values)


def parse_datetime_field(value: str, default_time: str = "09:00") -> datetime:
    raw = value.translate(ARABIC_DIGITS).strip()
    if not raw:
        raise ValueError("Missing datetime")

    try:
        return datetime.strptime(raw, DATETIME_FORMAT)
    except ValueError:
        pass

    parsed_date = datetime.strptime(raw, DATE_FORMAT)
    hour, minute = map(int, default_time.split(":"))
    return parsed_date.replace(hour=hour, minute=minute)


def format_datetime_field(value: datetime) -> str:
    return value.strftime(DATETIME_FORMAT)


def _time_to_obj(value: str) -> time:
    hour, minute = map(int, value.split(":"))
    return time(hour=hour, minute=minute)


def _combine(candidate_date: date, candidate_time: str) -> datetime:
    return datetime.combine(candidate_date, _time_to_obj(candidate_time))


def _allowed_day(candidate_date: date, weekdays: list[str], skip_weekends: bool) -> bool:
    candidate = datetime.combine(candidate_date, time())
    if skip_weekends and is_weekend(candidate):
        return False
    if weekdays and candidate.weekday() not in {WEEKDAY_TO_INDEX[day] for day in weekdays}:
        return False
    return True


def _add_year(value: datetime) -> datetime:
    year = value.year + 1
    day = min(value.day, calendar.monthrange(year, value.month)[1])
    return value.replace(year=year, day=day)


def _next_interval_candidate(
    *,
    fired_at: datetime,
    reference: datetime,
    interval_days: int,
    times: list[str],
    weekdays: list[str],
    skip_weekends: bool,
) -> datetime | None:
    base_date = fired_at.date()
    for offset in range(0, 370 * 3):
        candidate_date = base_date + timedelta(days=offset)
        if offset % interval_days != 0:
            continue
        if not _allowed_day(candidate_date, weekdays, skip_weekends):
            continue
        for candidate_time in times:
            candidate = _combine(candidate_date, candidate_time)
            if candidate > fired_at and candidate > reference:
                return candidate
    return None


def _next_weekly_candidate(
    *,
    fired_at: datetime,
    reference: datetime,
    times: list[str],
    weekdays: list[str],
    skip_weekends: bool,
) -> datetime | None:
    active_weekdays = weekdays or [INDEX_TO_WEEKDAY[fired_at.weekday()]]
    for offset in range(0, 370 * 3):
        candidate_date = fired_at.date() + timedelta(days=offset)
        if not _allowed_day(candidate_date, active_weekdays, skip_weekends):
            continue
        for candidate_time in times:
            candidate = _combine(candidate_date, candidate_time)
            if candidate > fired_at and candidate > reference:
                return candidate
    return None


def _next_calendar_candidate(
    *,
    fired_at: datetime,
    reference: datetime,
    repeat: str,
    times: list[str],
    skip_weekends: bool,
) -> datetime | None:
    for candidate_time in times:
        candidate = _combine(fired_at.date(), candidate_time)
        if candidate > fired_at and candidate > reference:
            return candidate

    candidate = advance_recurrence(fired_at, repeat)
    candidate = _combine(candidate.date(), times[0])
    for _ in range(370 * 3):
        if not skip_weekends or not is_weekend(candidate):
            return candidate
        candidate += timedelta(days=1)
    return None


def _countdown_candidate(
    *,
    reminder: dict,
    fired_at: datetime,
    reference: datetime,
) -> tuple[datetime, datetime | None] | None:
    repeat = reminder.get("repeat", "none")
    event_at = reminder.get("event_at", "")
    if not event_at:
        return None

    lead_days = max(int(reminder.get("lead_days") or 7), 1)
    skip_weekends = normalize_bool(reminder.get("skip_weekends", False))
    event_dt = parse_datetime_field(event_at, fired_at.strftime("%H:%M"))
    reminder_time = fired_at.strftime("%H:%M")
    next_date = fired_at.date() + timedelta(days=1)
    final_date = event_dt.date() - timedelta(days=1)

    while next_date <= final_date:
        if _allowed_day(next_date, [], skip_weekends):
            candidate = _combine(next_date, reminder_time)
            if candidate > reference:
                return candidate, event_dt
        next_date += timedelta(days=1)

    if repeat != "annual_countdown":
        return None

    next_event = _add_year(event_dt)
    while next_event.date() - timedelta(days=lead_days) <= reference.date():
        next_event = _add_year(next_event)

    next_remind = _combine(next_event.date() - timedelta(days=lead_days), reminder_time)
    while skip_weekends and is_weekend(next_remind):
        next_remind += timedelta(days=1)
        if next_remind.date() >= next_event.date():
            next_event = _add_year(next_event)
            next_remind = _combine(next_event.date() - timedelta(days=lead_days), reminder_time)
    return next_remind, next_event


def next_reminder_after(
    reminder: dict,
    fired_at: datetime,
    reference: datetime | None = None,
) -> tuple[str, str | None] | None:
    repeat = reminder.get("repeat", "none").strip() or "none"
    if repeat == "none":
        return None

    ref = to_ksa(reference).replace(tzinfo=None) if reference else now_ksa().replace(tzinfo=None)
    fired = fired_at.replace(tzinfo=None)

    if repeat in COUNTDOWN_REPEATS:
        countdown = _countdown_candidate(reminder=reminder, fired_at=fired, reference=ref)
        if not countdown:
            return None
        next_remind, next_event = countdown
        return format_datetime_field(next_remind), format_datetime_field(next_event) if next_event else None

    times = normalize_times(reminder.get("times")) or [fired.strftime("%H:%M")]
    weekdays = normalize_weekdays(reminder.get("weekdays"))
    skip_weekends = normalize_bool(reminder.get("skip_weekends", False))

    if repeat == "daily":
        candidate = _next_interval_candidate(
            fired_at=fired,
            reference=ref,
            interval_days=1,
            times=times,
            weekdays=[],
            skip_weekends=skip_weekends,
        )
    elif repeat == "every_2_days":
        candidate = _next_interval_candidate(
            fired_at=fired,
            reference=ref,
            interval_days=2,
            times=times,
            weekdays=[],
            skip_weekends=skip_weekends,
        )
    elif repeat == "every_n_days":
        interval_days = max(int(reminder.get("interval_days") or 1), 1)
        candidate = _next_interval_candidate(
            fired_at=fired,
            reference=ref,
            interval_days=interval_days,
            times=times,
            weekdays=[],
            skip_weekends=skip_weekends,
        )
    elif repeat == "weekly":
        candidate = _next_weekly_candidate(
            fired_at=fired,
            reference=ref,
            times=times,
            weekdays=weekdays,
            skip_weekends=skip_weekends,
        )
    elif repeat in {"monthly", "annual"}:
        candidate = _next_calendar_candidate(
            fired_at=fired,
            reference=ref,
            repeat=repeat,
            times=times,
            skip_weekends=skip_weekends,
        )
    else:
        candidate = advance_recurrence(fired, repeat)
        if candidate <= fired:
            return None

    return (format_datetime_field(candidate), None) if candidate else None


def initial_remind_at(reminder: dict, reference: datetime | None = None) -> str:
    ref = to_ksa(reference).replace(tzinfo=None) if reference else now_ksa().replace(tzinfo=None)

    if reminder.get("remind_at"):
        return format_datetime_field(parse_datetime_field(reminder["remind_at"]))

    repeat = reminder.get("repeat", "none").strip() or "none"
    if repeat == "none":
        raise ValueError("remind_at is required for one-time reminders")

    if repeat in COUNTDOWN_REPEATS:
        event_at = reminder.get("event_at", "")
        if not event_at:
            raise ValueError("event_at is required for countdown reminders")

        times = normalize_times(reminder.get("times")) or ["09:00"]
        lead_days = max(int(reminder.get("lead_days") or 7), 1)
        skip_weekends = normalize_bool(reminder.get("skip_weekends", False))
        event_dt = parse_datetime_field(event_at, times[0])

        if repeat == "annual_countdown":
            while event_dt.date() - timedelta(days=1) < ref.date():
                event_dt = _add_year(event_dt)

        start_date = event_dt.date() - timedelta(days=lead_days)
        final_date = event_dt.date() - timedelta(days=1)
        candidate_date = max(start_date, ref.date())
        while candidate_date <= final_date:
            if _allowed_day(candidate_date, [], skip_weekends):
                for candidate_time in times:
                    candidate = _combine(candidate_date, candidate_time)
                    if candidate > ref:
                        return format_datetime_field(candidate)
            candidate_date += timedelta(days=1)

        if repeat == "annual_countdown":
            next_event = _add_year(event_dt)
            reminder["event_at"] = format_datetime_field(next_event)
            next_date = next_event.date() - timedelta(days=lead_days)
            return format_datetime_field(_combine(next_date, times[0]))
        raise ValueError("countdown reminder window has already passed")

    if not reminder.get("times"):
        reminder["times"] = "09:00"
    synthetic_fired_at = ref - timedelta(minutes=1)
    if reminder.get("weekdays"):
        synthetic_fired_at = datetime.combine(ref.date(), time())
    next_due = next_reminder_after(reminder, synthetic_fired_at, reference=ref)
    if not next_due:
        raise ValueError("Could not calculate next reminder time")
    return next_due[0]
