"""Date helper utilities."""

import calendar
from datetime import datetime, timedelta
from typing import Optional


def parse_date_flexible(text: str) -> Optional[datetime]:
    """Try to parse a date from various formats."""
    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    return None


def relative_date_text(days: int) -> str:
    if days == 0:
        return "today"
    elif days == 1:
        return "tomorrow"
    elif days == -1:
        return "yesterday"
    elif days > 0:
        return f"in {days} days"
    else:
        return f"{abs(days)} days ago"


def next_occurrence(month: int, day: int, from_date: Optional[datetime] = None) -> datetime:
    """Get the next occurrence of an annual date (e.g., birthday)."""
    from moha_mind.utils.timezone import now_ksa

    now = from_date or now_ksa()
    year = now.year
    candidate = datetime(year, month, day)
    if candidate < now.replace(tzinfo=None):
        candidate = datetime(year + 1, month, day)
    return candidate


def is_weekend(dt: datetime) -> bool:
    """Check if date is weekend (Friday/Saturday in KSA)."""
    return dt.weekday() in (4, 5)


def date_range_days(start: datetime, days: int) -> list[datetime]:
    return [start + timedelta(days=i) for i in range(days)]


def advance_recurrence(dt: datetime, recurrence: str) -> datetime:
    recurrence = recurrence.lower().strip()
    if recurrence in {"none", ""}:
        return dt
    if recurrence == "daily":
        return dt + timedelta(days=1)
    if recurrence in {"every_2_days", "alternate_days"}:
        return dt + timedelta(days=2)
    if recurrence == "weekly":
        return dt + timedelta(days=7)
    if recurrence == "monthly":
        year = dt.year + (1 if dt.month == 12 else 0)
        month = 1 if dt.month == 12 else dt.month + 1
        day = min(dt.day, calendar.monthrange(year, month)[1])
        return dt.replace(year=year, month=month, day=day)
    if recurrence == "annual":
        year = dt.year + 1
        day = min(dt.day, calendar.monthrange(year, dt.month)[1])
        return dt.replace(year=year, day=day)
    return dt
