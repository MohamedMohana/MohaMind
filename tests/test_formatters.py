"""Tests for Telegram message formatters."""

from moha_mind.telegram_bot.formatters import (
    escape_markdown,
    format_briefing,
    format_expiry_alert,
    format_task_list,
    truncate_message,
)


class TestEscapeMarkdown:
    def test_plain_text(self):
        assert escape_markdown("hello world") == "hello world"

    def test_special_chars(self):
        result = escape_markdown("hello_world")
        assert "\\_" in result

    def test_asterisk(self):
        result = escape_markdown("hello*world")
        assert "\\*" in result

    def test_brackets(self):
        result = escape_markdown("[test]")
        assert "\\[" in result
        assert "\\]" in result

    def test_empty_string(self):
        assert escape_markdown("") == ""

    def test_all_special(self):
        text = "_*[]()~`>#+-=|{}.!"
        result = escape_markdown(text)
        assert result.startswith("\\_")

    def test_numbers_unchanged(self):
        assert escape_markdown("123") == "123"


class TestFormatBriefing:
    def test_plain_text(self):
        result = format_briefing("Hello world")
        assert "Hello world" in result

    def test_bold_conversion(self):
        result = format_briefing("This is **bold** text")
        assert "*bold*" in result
        assert "**" not in result

    def test_heading_conversion(self):
        result = format_briefing("# Morning Report")
        assert "*Morning Report*" in result

    def test_list_items(self):
        result = format_briefing("- Item one\n- Item two")
        assert "  - Item one" in result

    def test_empty_string(self):
        assert format_briefing("") == ""


class TestFormatTaskList:
    def test_passthrough(self):
        assert format_task_list("any text") == "any text"

    def test_empty(self):
        assert format_task_list("") == ""


class TestFormatExpiryAlert:
    def test_urgent_today(self):
        result = format_expiry_alert("[0d] Passport expires")
        assert "🔴 URGENT" in result

    def test_urgent_one_day(self):
        result = format_expiry_alert("[1d] Insurance expires")
        assert "🔴 URGENT" in result

    def test_warning_seven_days(self):
        result = format_expiry_alert("[7d] Something expires")
        assert "🟡" in result

    def test_warning_three_days(self):
        result = format_expiry_alert("[3d] Registration expires")
        assert "🟡" in result

    def test_info_far_future(self):
        result = format_expiry_alert("[30d] License expires")
        assert "🟢" in result

    def test_mixed_urgency(self):
        text = "[0d] Today\n[5d] This week\n[60d] Later"
        result = format_expiry_alert(text)
        assert "🔴" in result
        assert "🟡" in result
        assert "🟢" in result

    def test_empty(self):
        result = format_expiry_alert("")
        assert "🟢" in result


class TestTruncateMessage:
    def test_short_message(self):
        result = truncate_message("Hello")
        assert len(result) == 1
        assert result[0] == "Hello"

    def test_exact_limit(self):
        text = "a" * 4096
        result = truncate_message(text)
        assert len(result) == 1

    def test_over_limit_splits(self):
        text = "Line 1\n" + "a" * 5000
        result = truncate_message(text, max_length=100)
        assert len(result) > 1

    def test_custom_max_length(self):
        text = "a" * 300
        result = truncate_message(text, max_length=100)
        assert len(result) > 1

    def test_no_newlines_splits_at_max(self):
        text = "a" * 200
        result = truncate_message(text, max_length=50)
        assert len(result) >= 4

    def test_preserves_content(self):
        text = "Hello World"
        result = truncate_message(text)
        assert result[0] == text

    def test_newlines_preferred_split_point(self):
        text = "A" * 50 + "\n" + "B" * 50 + "\n" + "C" * 50
        result = truncate_message(text, max_length=75)
        assert len(result) == 3
        assert all(len(part) <= 75 for part in result)
