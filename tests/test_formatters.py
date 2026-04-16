"""Tests for Telegram message formatters (HTML output)."""

from moha_mind.telegram_bot.formatters import (
    escape_html,
    escape_markdown,
    format_briefing,
    format_expiry_alert,
    format_task_list,
    format_telegram_html,
    format_telegram_markdown,
    truncate_message,
)


class TestEscapeMarkdown:
    def test_plain_text(self):
        assert escape_markdown("hello world") == "hello world"

    def test_special_chars(self):
        assert "\\_" in escape_markdown("hello_world")

    def test_asterisk(self):
        assert "\\*" in escape_markdown("hello*world")

    def test_brackets(self):
        result = escape_markdown("[test]")
        assert "\\[" in result
        assert "\\]" in result

    def test_empty_string(self):
        assert escape_markdown("") == ""


class TestEscapeHtml:
    def test_plain_text(self):
        assert escape_html("hello world") == "hello world"

    def test_angle_brackets(self):
        assert escape_html("<script>") == "&lt;script&gt;"

    def test_ampersand(self):
        assert escape_html("a & b") == "a &amp; b"

    def test_arabic_untouched(self):
        text = "مرحبا يا صديقي"
        assert escape_html(text) == text


class TestFormatTelegramHtml:
    def test_double_asterisk_bold(self):
        assert format_telegram_html("**Omega-3**") == "<b>Omega-3</b>"

    def test_single_asterisk_bold(self):
        assert format_telegram_html("*أوميغا 3*") == "<b>أوميغا 3</b>"

    def test_underscore_bold(self):
        assert format_telegram_html("__important__") == "<b>important</b>"

    def test_time_with_period_passes_through(self):
        result = format_telegram_html("الساعة 1:30 م.")
        assert result == "الساعة 1:30 م."

    def test_heading_becomes_bold(self):
        assert format_telegram_html("## أوميقا-3") == "<b>أوميقا-3</b>"

    def test_bullet_line(self):
        result = format_telegram_html("- بعد الغدا على الساعة **1:30 م**")
        assert result.startswith("• ")
        assert "<b>1:30 م</b>" in result

    def test_ordered_list_preserved(self):
        result = format_telegram_html("1. خذ الدواء")
        assert result == "1. خذ الدواء"

    def test_angle_brackets_escaped(self):
        assert format_telegram_html("use <tag>") == "use &lt;tag&gt;"

    def test_ampersand_escaped(self):
        assert format_telegram_html("tea & coffee") == "tea &amp; coffee"

    def test_inline_code(self):
        result = format_telegram_html("run `/help` now")
        assert "<code>/help</code>" in result

    def test_code_fence_block(self):
        text = "```\nline1\nline2\n```"
        result = format_telegram_html(text)
        assert "<pre>line1\nline2</pre>" in result

    def test_pipe_table_rendered_as_bullets(self):
        table = (
            "| Medication | Time | Frequency |\n"
            "|---|---|---|\n"
            "| Omega-3 | 8:00 AM | daily |\n"
            "| Vit D | 1:00 PM | weekly |\n"
        )
        result = format_telegram_html(table)
        assert "<b>Medication:</b> Omega-3" in result
        assert "<b>Time:</b> 8:00 AM" in result
        assert "<b>Frequency:</b> daily" in result
        assert "<b>Medication:</b> Vit D" in result
        assert "|" not in result

    def test_horizontal_rule(self):
        assert "────────" in format_telegram_html("---")

    def test_format_telegram_markdown_alias(self):
        assert format_telegram_markdown("*bold*") == format_telegram_html("*bold*")

    def test_empty_string(self):
        assert format_telegram_html("") == ""


class TestFormatBriefing:
    def test_plain_text(self):
        assert "Hello world" in format_briefing("Hello world")

    def test_bold_conversion(self):
        assert "<b>bold</b>" in format_briefing("This is **bold** text")

    def test_heading_conversion(self):
        assert format_briefing("# Morning Report") == "<b>Morning Report</b>"

    def test_list_items(self):
        result = format_briefing("- Item one\n- Item two")
        assert "• Item one" in result
        assert "• Item two" in result

    def test_empty_string(self):
        assert format_briefing("") == ""


class TestFormatTaskList:
    def test_passthrough(self):
        assert format_task_list("any text") == "any text"

    def test_empty(self):
        assert format_task_list("") == ""


class TestFormatExpiryAlert:
    def test_urgent_today(self):
        assert "🔴 URGENT" in format_expiry_alert("[0d] Passport expires")

    def test_urgent_one_day(self):
        assert "🔴 URGENT" in format_expiry_alert("[1d] Insurance expires")

    def test_warning_seven_days(self):
        assert "🟡" in format_expiry_alert("[7d] Something expires")

    def test_info_far_future(self):
        assert "🟢" in format_expiry_alert("[30d] License expires")

    def test_mixed_urgency(self):
        text = "[0d] Today\n[5d] This week\n[60d] Later"
        result = format_expiry_alert(text)
        assert "🔴" in result
        assert "🟡" in result
        assert "🟢" in result


class TestTruncateMessage:
    def test_short_message(self):
        assert truncate_message("Hello") == ["Hello"]

    def test_exact_limit(self):
        text = "a" * 4096
        assert len(truncate_message(text)) == 1

    def test_over_limit_splits(self):
        text = "Line 1\n" + "a" * 5000
        assert len(truncate_message(text, max_length=100)) > 1

    def test_preserves_short_content(self):
        assert truncate_message("Hello World")[0] == "Hello World"

    def test_newlines_preferred_split_point(self):
        text = "A" * 50 + "\n" + "B" * 50 + "\n" + "C" * 50
        result = truncate_message(text, max_length=75)
        assert all(len(part) <= 75 for part in result)
