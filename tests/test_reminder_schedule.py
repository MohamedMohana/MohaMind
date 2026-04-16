from datetime import datetime

from moha_mind.utils.reminder_schedule import initial_remind_at, next_reminder_after


class TestReminderSchedule:
    def test_daily_multiple_times_uses_later_time_same_day(self):
        reminder = {
            "repeat": "daily",
            "times": "05:00,17:00",
            "skip_weekends": "false",
        }
        result = next_reminder_after(
            reminder,
            fired_at=datetime(2026, 4, 16, 5, 0),
            reference=datetime(2026, 4, 16, 5, 30),
        )
        assert result == ("2026-04-16 17:00", None)

    def test_daily_skip_weekends_uses_next_workday_in_ksa(self):
        reminder = {
            "repeat": "daily",
            "times": "09:00",
            "skip_weekends": "true",
        }
        result = next_reminder_after(
            reminder,
            fired_at=datetime(2026, 4, 16, 9, 0),
            reference=datetime(2026, 4, 16, 9, 30),
        )
        assert result == ("2026-04-19 09:00", None)

    def test_weekly_multiple_times_uses_same_weekday(self):
        reminder = {
            "repeat": "weekly",
            "times": "05:00,17:00",
            "weekdays": "wed",
        }
        result = next_reminder_after(
            reminder,
            fired_at=datetime(2026, 4, 15, 5, 0),
            reference=datetime(2026, 4, 15, 5, 30),
        )
        assert result == ("2026-04-15 17:00", None)

    def test_initial_weekly_reminder_from_weekday_and_time(self):
        reminder = {
            "repeat": "weekly",
            "times": "17:00",
            "weekdays": "wed",
        }
        result = initial_remind_at(reminder, reference=datetime(2026, 4, 16, 12, 0))
        assert result == "2026-04-22 17:00"

    def test_initial_weekly_without_time_defaults_to_morning(self):
        reminder = {
            "repeat": "weekly",
            "weekdays": "wed",
        }
        result = initial_remind_at(reminder, reference=datetime(2026, 4, 16, 12, 0))
        assert result == "2026-04-22 09:00"
        assert reminder["times"] == "09:00"

    def test_annual_countdown_starts_at_lead_window(self):
        reminder = {
            "repeat": "annual_countdown",
            "event_at": "2026-05-10 09:00",
            "times": "09:00",
            "lead_days": "7",
        }
        result = initial_remind_at(reminder, reference=datetime(2026, 5, 1, 12, 0))
        assert result == "2026-05-03 09:00"

    def test_annual_countdown_rolls_to_next_year_after_day_before(self):
        reminder = {
            "repeat": "annual_countdown",
            "event_at": "2026-05-10 09:00",
            "times": "09:00",
            "lead_days": "7",
        }
        result = next_reminder_after(
            reminder,
            fired_at=datetime(2026, 5, 9, 9, 0),
            reference=datetime(2026, 5, 9, 9, 30),
        )
        assert result == ("2027-05-03 09:00", "2027-05-10 09:00")
