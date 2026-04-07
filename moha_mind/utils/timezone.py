"""Timezone helpers for KSA (Asia/Riyadh, UTC+3)."""

from datetime import datetime
from zoneinfo import ZoneInfo

KSA_TZ = ZoneInfo("Asia/Riyadh")


def now_ksa() -> datetime:
    return datetime.now(KSA_TZ)


def to_ksa(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=KSA_TZ)
    return dt.astimezone(KSA_TZ)


def ksa_today_str() -> str:
    return now_ksa().strftime("%Y-%m-%d")


def ksa_time_str() -> str:
    return now_ksa().strftime("%H:%M %Z")


def ksa_day_name() -> str:
    return now_ksa().strftime("%A")


def ksa_date_display() -> str:
    return now_ksa().strftime("%A, %B %d, %Y")


def days_until(target_date: datetime) -> int:
    now = now_ksa()
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
