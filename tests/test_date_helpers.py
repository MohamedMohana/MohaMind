"""Tests for date helper utilities."""

from datetime import datetime

from moha_mind.utils.date_helpers import (
    advance_recurrence,
    date_range_days,
    is_weekend,
    next_occurrence,
    parse_date_flexible,
    relative_date_text,
)


class TestParseDateFlexible:
    def test_iso_format(self):
        result = parse_date_flexible("2026-04-15")
        assert result == datetime(2026, 4, 15)

    def test_slash_format(self):
        result = parse_date_flexible("15/04/2026")
        assert result == datetime(2026, 4, 15)

    def test_dash_eu_format(self):
        result = parse_date_flexible("15-04-2026")
        assert result == datetime(2026, 4, 15)

    def test_full_month_name(self):
        result = parse_date_flexible("April 15, 2026")
        assert result == datetime(2026, 4, 15)

    def test_short_month_name(self):
        result = parse_date_flexible("Apr 15, 2026")
        assert result == datetime(2026, 4, 15)

    def test_day_month_year(self):
        result = parse_date_flexible("15 April 2026")
        assert result == datetime(2026, 4, 15)

    def test_short_day_month_year(self):
        result = parse_date_flexible("15 Apr 2026")
        assert result == datetime(2026, 4, 15)

    def test_invalid_returns_none(self):
        assert parse_date_flexible("not a date") is None

    def test_empty_returns_none(self):
        assert parse_date_flexible("") is None

    def test_partial_date_returns_none(self):
        assert parse_date_flexible("2026") is None


class TestRelativeDateText:
    def test_today(self):
        assert relative_date_text(0) == "today"

    def test_tomorrow(self):
        assert relative_date_text(1) == "tomorrow"

    def test_yesterday(self):
        assert relative_date_text(-1) == "yesterday"

    def test_future(self):
        assert relative_date_text(5) == "in 5 days"

    def test_past(self):
        assert relative_date_text(-5) == "5 days ago"

    def test_far_future(self):
        assert relative_date_text(365) == "in 365 days"


class TestNextOccurrence:
    def test_future_date_this_year(self):
        from moha_mind.utils.timezone import now_ksa

        now = now_ksa()
        future_month = now.month + 1 if now.month < 12 else 1
        future_year = now.year if now.month < 12 else now.year + 1
        result = next_occurrence(future_month, 15, now)
        assert result.month == future_month
        assert result.year == future_year

    def test_past_date_next_year(self):
        from moha_mind.utils.timezone import now_ksa

        now = now_ksa()
        past_month = now.month - 1 if now.month > 1 else 12
        result = next_occurrence(past_month, 15, now)
        assert result.year == now.year + 1

    def test_custom_from_date(self):
        from_date = datetime(2026, 1, 1)
        result = next_occurrence(6, 15, from_date)
        assert result == datetime(2026, 6, 15)

    def test_same_day(self):
        from_date = datetime(2026, 6, 15)
        result = next_occurrence(6, 15, from_date)
        assert result == datetime(2026, 6, 15)

    def test_same_day_returns_next_year_after_passing(self):
        from_date = datetime(2026, 6, 16)
        result = next_occurrence(6, 15, from_date)
        assert result == datetime(2027, 6, 15)


class TestIsWeekend:
    def test_friday_is_weekend(self):
        fri = datetime(2026, 4, 10)
        assert is_weekend(fri) is True

    def test_saturday_is_weekend(self):
        sat = datetime(2026, 4, 11)
        assert is_weekend(sat) is True

    def test_sunday_is_not_weekend(self):
        sun = datetime(2026, 4, 12)
        assert is_weekend(sun) is False

    def test_monday_is_not_weekend(self):
        mon = datetime(2026, 4, 6)
        assert is_weekend(mon) is False


class TestDateRangeDays:
    def test_zero_days(self):
        start = datetime(2026, 4, 7)
        result = date_range_days(start, 0)
        assert result == []

    def test_one_day(self):
        start = datetime(2026, 4, 7)
        result = date_range_days(start, 1)
        assert len(result) == 1
        assert result[0] == start

    def test_seven_days(self):
        start = datetime(2026, 4, 7)
        result = date_range_days(start, 7)
        assert len(result) == 7
        assert result[0] == start
        assert result[-1] == datetime(2026, 4, 13)


class TestAdvanceRecurrence:
    def test_every_2_days(self):
        start = datetime(2026, 4, 14, 16, 0)
        result = advance_recurrence(start, "every_2_days")
        assert result == datetime(2026, 4, 16, 16, 0)
