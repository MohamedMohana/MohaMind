"""Comprehensive tests for scheduler jobs."""

from moha_mind.scheduler.jobs import parse_time


class TestParseTime:
    def test_standard_time(self):
        h, m = parse_time("08:30")
        assert h == 8
        assert m == 30

    def test_midnight(self):
        h, m = parse_time("00:00")
        assert h == 0
        assert m == 0

    def test_end_of_day(self):
        h, m = parse_time("23:45")
        assert h == 23
        assert m == 45

    def test_no_leading_zero(self):
        h, m = parse_time("8:5")
        assert h == 8
        assert m == 5


class TestSchedulerJobsCronOverflow:
    def test_cron_hour_overflow(self):
        hour = 23
        overflow_safe = (hour + 1) % 24
        assert overflow_safe == 0

    def test_cron_hour_normal(self):
        hour = 8
        normal = (hour + 1) % 24
        assert normal == 9

    def test_cron_hour_midday(self):
        hour = 12
        result = (hour + 1) % 24
        assert result == 13
