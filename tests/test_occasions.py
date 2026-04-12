from datetime import datetime

from moha_mind.utils.occasions import parse_occasions, upcoming_occasions


class TestOccasionUtilities:
    def test_parse_occasions_from_sections(self):
        content = (
            "# Important Occasions\n\n"
            "## Birthdays\n"
            "- Sarah's birthday: 1992-03-15\n\n"
            "## Anniversaries\n"
            "- Wedding Day: 2020-04-13\n\n"
            "## Annual Events\n"
            "- Saudi National Day: 09-23\n"
        )

        entries = parse_occasions(content, reference=datetime(2026, 4, 12))

        assert len(entries) == 3
        assert {entry.kind for entry in entries} == {"birthday", "anniversary", "annual_event"}
        assert any(entry.title == "Wedding Day" and entry.days_left == 1 for entry in entries)

    def test_upcoming_occasions_filters_window(self):
        content = (
            "# Important Occasions\n\n"
            "## Birthdays\n"
            "- Omar birthday: 2020-04-13\n"
            "- Layla birthday: 2020-05-20\n"
        )

        entries = upcoming_occasions(content, days_ahead=7, reference=datetime(2026, 4, 12))

        assert len(entries) == 1
        assert entries[0].title == "Omar birthday"
        assert entries[0].days_left == 1
