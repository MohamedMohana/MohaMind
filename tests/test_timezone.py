"""Tests for timezone utilities."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from moha_mind.utils.timezone import (
    KSA_TZ,
    days_until,
    hours_until,
    ksa_date_display,
    ksa_day_name,
    ksa_time_str,
    ksa_today_str,
    now_ksa,
    to_ksa,
)


class TestTimezone:
    def test_ksa_tz_is_riyadh(self):
        assert KSA_TZ == ZoneInfo("Asia/Riyadh")

    def test_now_ksa_has_timezone(self):
        dt = now_ksa()
        assert dt.tzinfo is not None

    def test_now_ksa_is_utc_plus_3(self):
        dt = now_ksa()
        utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
        diff = dt.replace(tzinfo=None) - utc_now
        assert 2.5 < diff.total_seconds() / 3600 < 3.5

    def test_to_ksa_naive_datetime(self):
        dt = datetime(2026, 4, 7, 12, 0, 0)
        result = to_ksa(dt)
        assert result.tzinfo == KSA_TZ

    def test_to_ksa_aware_datetime(self):
        utc_dt = datetime(2026, 4, 7, 9, 0, 0, tzinfo=ZoneInfo("UTC"))
        result = to_ksa(utc_dt)
        assert result.hour == 12
        assert result.tzinfo == KSA_TZ

    def test_ksa_today_str_format(self):
        result = ksa_today_str()
        assert len(result) == 10
        assert result[4] == "-"
        assert result[7] == "-"

    def test_ksa_time_str_has_timezone(self):
        result = ksa_time_str()
        assert ":" in result
        assert len(result) > 4

    def test_ksa_day_name(self):
        result = ksa_day_name()
        assert result in [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

    def test_ksa_date_display(self):
        result = ksa_date_display()
        assert "2026" in result or "2025" in result

    def test_days_until_future(self):
        future = now_ksa() + timedelta(days=5)
        result = days_until(future)
        assert result == 5

    def test_days_until_today(self):
        today = now_ksa().replace(hour=12)
        result = days_until(today)
        assert result == 0

    def test_days_until_past(self):
        past = now_ksa() - timedelta(days=3)
        result = days_until(past)
        assert result == -3

    def test_days_until_naive_date(self):
        future = (now_ksa() + timedelta(days=7)).replace(tzinfo=None)
        result = days_until(future)
        assert result == 7

    def test_days_until_with_reference(self):
        target = datetime(2026, 4, 13)
        reference = datetime(2026, 4, 12, 23, 30)
        result = days_until(target, reference=reference)
        assert result == 1

    def test_hours_until_future(self):
        future = now_ksa() + timedelta(hours=6)
        result = hours_until(future)
        assert 5.9 < result < 6.1

    def test_hours_until_naive_datetime(self):
        future = (now_ksa() + timedelta(hours=3)).replace(tzinfo=None)
        result = hours_until(future)
        assert 2.9 < result < 3.1
