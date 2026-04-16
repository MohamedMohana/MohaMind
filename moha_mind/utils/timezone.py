"""Timezone helpers for KSA (Asia/Riyadh, UTC+3)."""

from datetime import datetime
from zoneinfo import ZoneInfo

KSA_TZ = ZoneInfo("Asia/Riyadh")

ARABIC_DAYS = {
    "Monday": "الاثنين",
    "Tuesday": "الثلاثاء",
    "Wednesday": "الأربعاء",
    "Thursday": "الخميس",
    "Friday": "الجمعة",
    "Saturday": "السبت",
    "Sunday": "الأحد",
}

ARABIC_MONTHS = {
    1: "يناير",
    2: "فبراير",
    3: "مارس",
    4: "أبريل",
    5: "مايو",
    6: "يونيو",
    7: "يوليو",
    8: "أغسطس",
    9: "سبتمبر",
    10: "أكتوبر",
    11: "نوفمبر",
    12: "ديسمبر",
}


def now_ksa() -> datetime:
    return datetime.now(KSA_TZ)


def to_ksa(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=KSA_TZ)
    return dt.astimezone(KSA_TZ)


def ksa_today_str() -> str:
    return now_ksa().strftime("%Y-%m-%d")


def ksa_time_str() -> str:
    """Current KSA time in 12-hour format (e.g. '3:45 PM KSA')."""
    dt = now_ksa()
    suffix = "AM" if dt.hour < 12 else "PM"
    hour_12 = dt.hour % 12 or 12
    tz_name = dt.strftime("%Z") or "KSA"
    return f"{hour_12}:{dt.minute:02d} {suffix} {tz_name}"


def ksa_day_name() -> str:
    return now_ksa().strftime("%A")


def ksa_date_display() -> str:
    return now_ksa().strftime("%A, %B %d, %Y")


def ksa_date_display_ar(reference: datetime | None = None) -> str:
    dt = to_ksa(reference) if reference else now_ksa()
    day = ARABIC_DAYS[dt.strftime("%A")]
    month = ARABIC_MONTHS[dt.month]
    return f"{day}، {dt.day} {month} {dt.year}"


def _parse_time_fields(value: datetime | str) -> tuple[int, int] | None:
    """Return (hour, minute) for a datetime or a 'HH:MM' / 'YYYY-MM-DD HH:MM' string."""
    if isinstance(value, datetime):
        return value.hour, value.minute
    raw = value.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%H:%M"):
        try:
            parsed = datetime.strptime(raw, fmt)
            return parsed.hour, parsed.minute
        except ValueError:
            continue
    return None


def format_time_ar(value: datetime | str) -> str:
    parsed = _parse_time_fields(value)
    if parsed is None:
        return value if isinstance(value, str) else str(value)
    hour, minute = parsed
    suffix = "ص" if hour < 12 else "م"
    hour_12 = hour % 12 or 12
    return f"{hour_12}:{minute:02d} {suffix}"


def format_time_en(value: datetime | str) -> str:
    """Format a time value as 12-hour English (e.g. '5:30 PM')."""
    parsed = _parse_time_fields(value)
    if parsed is None:
        return value if isinstance(value, str) else str(value)
    hour, minute = parsed
    suffix = "AM" if hour < 12 else "PM"
    hour_12 = hour % 12 or 12
    return f"{hour_12}:{minute:02d} {suffix}"


def format_datetime_ar(value: datetime | str) -> str:
    if isinstance(value, datetime):
        dt = value
    else:
        raw = value.strip()
        try:
            dt = datetime.strptime(raw, "%Y-%m-%d %H:%M")
        except ValueError:
            return value
    return f"{dt.strftime('%Y-%m-%d')} {format_time_ar(dt)}"


def format_datetime_en(value: datetime | str) -> str:
    """Format a date+time as 'YYYY-MM-DD h:MM AM/PM'."""
    if isinstance(value, datetime):
        dt = value
    else:
        raw = value.strip()
        try:
            dt = datetime.strptime(raw, "%Y-%m-%d %H:%M")
        except ValueError:
            return value
    return f"{dt.strftime('%Y-%m-%d')} {format_time_en(dt)}"


def format_datetime_auto(value: datetime | str, language: str = "en") -> str:
    """Format a date+time in the requested language's 12-hour style."""
    if language == "ar":
        return format_datetime_ar(value)
    return format_datetime_en(value)


def days_until(target_date: datetime, reference: datetime | None = None) -> int:
    now = to_ksa(reference) if reference is not None else now_ksa()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    target = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    if target.tzinfo is None:
        target = target.replace(tzinfo=KSA_TZ)
    delta = target.astimezone(KSA_TZ) - today
    return delta.days


def hours_until(target_dt: datetime) -> float:
    now = now_ksa()
    if target_dt.tzinfo is None:
        target_dt = target_dt.replace(tzinfo=KSA_TZ)
    delta = target_dt.astimezone(KSA_TZ) - now
    return delta.total_seconds() / 3600
