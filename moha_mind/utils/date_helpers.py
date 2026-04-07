"""Date helper utilities."""

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
