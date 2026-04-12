"""Tests for MohaMind CLI components."""

from rich.console import Console
from rich.text import Text

from moha_mind.cli.themes import (
    BRAIN_COLORS,
    ENERGY_HIGH,
    ENERGY_LOW,
    ENERGY_NEUTRAL,
    colored_text,
    get_brain_colors,
    get_theme,
    style_panel,
    style_prompt,
)


class TestThemes:
    def test_get_theme_neutral(self):
        theme = get_theme("neutral")
        assert theme == ENERGY_NEUTRAL

    def test_get_theme_high(self):
        theme = get_theme("high")
        assert theme == ENERGY_HIGH

    def test_get_theme_low(self):
        theme = get_theme("low")
        assert theme == ENERGY_LOW

    def test_get_theme_unknown_defaults_neutral(self):
        theme = get_theme("unknown")
        assert theme == ENERGY_NEUTRAL

    def test_theme_has_required_keys(self):
        for mood in ("high", "neutral", "low"):
            theme = get_theme(mood)
            assert "primary" in theme
            assert "accent" in theme
            assert "prompt" in theme
            assert "panel_border" in theme
            assert "panel_title" in theme

    def test_brain_colors_returns_list(self):
        colors = get_brain_colors("high")
        assert isinstance(colors, list)
        assert len(colors) == 4

    def test_brain_colors_unknown_mood(self):
        colors = get_brain_colors("unknown")
        assert colors == BRAIN_COLORS["neutral"]

    def test_style_prompt_returns_string(self):
        result = style_prompt("neutral")
        assert isinstance(result, str)
        assert "bold" in result

    def test_style_panel_returns_tuple(self):
        border, title = style_panel("high")
        assert isinstance(border, str)
        assert isinstance(title, str)

    def test_colored_text_returns_text(self):
        result = colored_text("hello", "primary", "neutral")
        assert isinstance(result, Text)


class TestCommands:
    def test_register_and_get(self):
        from moha_mind.cli.commands import Command, CommandRegistry

        registry = CommandRegistry()
        cmd = Command(name="test", description="Test command")
        registry.register(cmd)

        assert registry.get("test") is cmd
        assert registry.get("nonexistent") is None

    def test_aliases(self):
        from moha_mind.cli.commands import Command, CommandRegistry

        registry = CommandRegistry()
        cmd = Command(name="quit", description="Exit", aliases=["exit"])
        registry.register(cmd)

        assert registry.get("exit") is cmd
        assert registry.get("quit") is cmd

    def test_all_commands_sorted(self):
        from moha_mind.cli.commands import Command, CommandRegistry

        registry = CommandRegistry()
        registry.register(Command(name="zebra", description="Z"))
        registry.register(Command(name="alpha", description="A"))
        registry.register(Command(name="mid", description="M"))

        names = [c.name for c in registry.all_commands()]
        assert names == ["alpha", "mid", "zebra"]

    def test_all_commands_no_duplicates(self):
        from moha_mind.cli.commands import Command, CommandRegistry

        registry = CommandRegistry()
        cmd = Command(name="test", description="T", aliases=["t"])
        registry.register(cmd)

        all_cmds = registry.all_commands()
        assert len(all_cmds) == 1

    def test_get_completions(self):
        from moha_mind.cli.commands import Command, CommandRegistry

        registry = CommandRegistry()
        registry.register(Command(name="help", description="Help"))
        registry.register(Command(name="tasks", description="Tasks"))

        completions = registry.get_completions()
        assert "/help" in completions
        assert "/tasks" in completions

    def test_get_help_list(self):
        from moha_mind.cli.commands import Command, CommandRegistry

        registry = CommandRegistry()
        registry.register(Command(name="help", description="Show help"))

        help_list = registry.get_help_list()
        assert len(help_list) == 1
        assert help_list[0]["name"] == "/help"
        assert help_list[0]["description"] == "Show help"


class TestDisplay:
    def test_display_response(self):
        from moha_mind.cli.display import display_response

        result = display_response("Hello **world**")
        assert result is not None

    def test_display_briefing(self):
        from moha_mind.cli.display import display_briefing

        panel = display_briefing("Today is great", "neutral")
        assert panel is not None

    def test_display_calendar_snapshot(self):
        from moha_mind.cli.display import display_calendar_snapshot

        panel = display_calendar_snapshot("### Google Calendar\n- Team sync")
        assert panel is not None

    def test_display_command_center(self):
        from moha_mind.cli.display import display_command_center

        view = display_command_center(
            [
                {"title": "🎯 Attention Radar", "body": "- Submit report"},
                {"title": "🗓 Calendar Horizon", "body": "- Team sync at 9"},
            ]
        )
        assert view is not None

    def test_display_tasks_empty(self):
        from moha_mind.cli.display import display_tasks

        panel = display_tasks([], "neutral")
        assert panel is not None

    def test_display_tasks_with_items(self):
        from moha_mind.cli.display import display_tasks

        tasks = [
            {"text": "Buy milk", "priority": "high", "due": "2026-04-10", "done": False},
            {"text": "Clean house", "priority": "medium", "due": None, "done": False},
            {"text": "Old task", "priority": "low", "due": None, "done": True},
        ]
        panel = display_tasks(tasks, "high")
        assert panel is not None

    def test_display_expiring_empty(self):
        from moha_mind.cli.display import display_expiring

        panel = display_expiring([], "neutral")
        assert panel is not None

    def test_display_expiring_with_items(self):
        from moha_mind.cli.display import display_expiring

        items = [
            {"category": "documents", "detail": "Passport", "days_left": 1},
            {"category": "vehicle", "detail": "Insurance", "days_left": 5},
            {"category": "health", "detail": "Prescription", "days_left": 30},
        ]
        panel = display_expiring(items, "low")
        assert panel is not None

    def test_display_memory_search(self):
        from moha_mind.cli.display import display_memory_search

        results = [
            {"category": "family", "line_number": 5, "context": "Wife birthday"},
            {"category": "tasks", "line_number": 10, "context": "Plan party"},
        ]
        panel = display_memory_search(results, "neutral")
        assert panel is not None

    def test_display_error(self):
        from moha_mind.cli.display import display_error

        panel = display_error("Something went wrong")
        assert panel is not None

    def test_display_success(self):
        from moha_mind.cli.display import display_success

        panel = display_success("All done!")
        assert panel is not None

    def test_display_help(self):
        from moha_mind.cli.display import display_help

        commands = [
            {"name": "/help", "description": "Show help"},
            {"name": "/tasks", "description": "Show tasks"},
        ]
        panel = display_help(commands, "neutral")
        assert panel is not None

    def test_display_status_bar(self):
        from moha_mind.cli.display import display_status_bar

        bar = display_status_bar("glm-4", "z.ai", "neutral", 5, 2)
        assert isinstance(bar, Text)

    def test_display_status_bar_no_expiring(self):
        from moha_mind.cli.display import display_status_bar

        bar = display_status_bar("gpt-4", "openai", "high", 0, 0)
        assert isinstance(bar, Text)


class TestBanner:
    def test_build_banner(self):
        from moha_mind.cli.banner import build_banner

        banner = build_banner(
            version="0.1.0",
            model="glm-4-plus",
            provider="z.ai",
            timezone="Asia/Riyadh",
            tasks_count=5,
            expiring_count=2,
            mood="neutral",
            uptime_hint="10:30 AM",
        )
        assert banner is not None

    def test_build_banner_no_expiring(self):
        from moha_mind.cli.banner import build_banner

        banner = build_banner(mood="high")
        assert banner is not None

    def test_render_brain(self):
        from moha_mind.cli.banner import _render_brain

        result = _render_brain("neutral")
        assert isinstance(result, Text)

    def test_render_brain_high_mood(self):
        from moha_mind.cli.banner import _render_brain

        result = _render_brain("high")
        assert isinstance(result, Text)


class TestSpinner:
    def test_spinner_start_stop(self):
        from moha_mind.cli.spinner import NeuralPulse

        console = Console(force_terminal=True, width=80)
        spinner = NeuralPulse(console, "neutral")
        spinner.start()
        assert spinner._active
        spinner.stop()
        assert not spinner._active

    def test_spinner_double_start(self):
        from moha_mind.cli.spinner import NeuralPulse

        console = Console(force_terminal=True, width=80)
        spinner = NeuralPulse(console, "high")
        spinner.start()
        spinner.start()
        assert spinner._active
        spinner.stop()

    def test_spinner_stop_when_not_active(self):
        from moha_mind.cli.spinner import NeuralPulse

        console = Console(force_terminal=True, width=80)
        spinner = NeuralPulse(console, "low")
        spinner.stop()
        assert not spinner._active

    def test_build_frame(self):
        from moha_mind.cli.spinner import NeuralPulse

        console = Console(force_terminal=True, width=80)
        spinner = NeuralPulse(console, "neutral")
        frame = spinner._build_frame(0, 0)
        assert frame is not None
