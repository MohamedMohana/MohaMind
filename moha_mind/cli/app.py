"""MohaMind CLI Application - The main interactive loop.

Orchestrates the banner, input, spinner, display, and agent
into a seamless terminal experience.
"""

import asyncio
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.text import Text

from moha_mind.agent.core import MohaMindAgent
from moha_mind.agent.energy_tracker import EnergyTracker
from moha_mind.agent.memory import MemoryManager
from moha_mind.cli.banner import build_banner
from moha_mind.cli.commands import Command, CommandRegistry
from moha_mind.cli.display import (
    display_attention_radar,
    display_briefing,
    display_calendar_snapshot,
    display_command_center,
    display_error,
    display_expiring,
    display_help,
    display_memory_search,
    display_response,
    display_status_bar,
    display_success,
    display_tasks,
    hermes_panel,
)
from moha_mind.cli.input_handler import InputHandler
from moha_mind.cli.spinner import NeuralPulse
from moha_mind.cli.themes import get_theme
from moha_mind.config import settings
from moha_mind.utils.logging_config import log
from moha_mind.utils.timezone import ksa_date_display, ksa_time_str


class MohaMindCLI:
    def __init__(self, memory: MemoryManager, agent: MohaMindAgent):
        self.memory = memory
        self.agent = agent
        self.energy = EnergyTracker(memory)
        self.console = Console()
        self.registry = CommandRegistry()
        self.spinner: NeuralPulse | None = None
        self._running = False

        self._register_commands()

    def _register_commands(self) -> None:
        self.registry.register(Command(name="help", description="Show available commands", handler=self._cmd_help))
        self.registry.register(
            Command(name="quit", description="Exit MohaMind", aliases=["exit"], handler=self._cmd_quit)
        )
        self.registry.register(Command(name="tasks", description="Show active tasks", handler=self._cmd_tasks))
        self.registry.register(
            Command(name="reminders", description="Show scheduled reminders", handler=self._cmd_reminders)
        )
        self.registry.register(
            Command(name="remind", description="Set a timed reminder", handler=self._cmd_remind)
        )
        self.registry.register(
            Command(name="briefing", description="Generate morning briefing", handler=self._cmd_briefing)
        )
        self.registry.register(Command(name="expiring", description="Show expiring items", handler=self._cmd_expiring))
        self.registry.register(
            Command(name="search", description="Search memory: /search <query>", handler=self._cmd_search)
        )
        self.registry.register(
            Command(
                name="recall",
                description="Search memory and past conversations: /recall <query>",
                handler=self._cmd_recall,
            )
        )
        self.registry.register(Command(name="memory", description="Show memory categories", handler=self._cmd_memory))
        self.registry.register(Command(name="review", description="Generate weekly review", handler=self._cmd_review))
        self.registry.register(Command(name="stats", description="Show system stats", handler=self._cmd_stats))
        self.registry.register(Command(name="clear", description="Clear screen", handler=self._cmd_clear))
        self.registry.register(Command(name="mood", description="Show energy/mood analysis", handler=self._cmd_mood))
        self.registry.register(
            Command(name="add", description="Quick add: /add task <text> or /add note <title>", handler=self._cmd_add)
        )
        self.registry.register(
            Command(
                name="done",
                description="Complete a task: /done <task text>",
                aliases=["complete"],
                handler=self._cmd_done,
            )
        )
        self.registry.register(
            Command(name="family", description="Family overview: upcoming events", handler=self._cmd_family)
        )
        self.registry.register(
            Command(name="social", description="Social connections & neglected contacts", handler=self._cmd_social)
        )
        self.registry.register(
            Command(name="vehicle", description="Vehicle info & next service", handler=self._cmd_vehicle)
        )
        self.registry.register(
            Command(name="health", description="Health: medications & vitals", handler=self._cmd_health)
        )
        self.registry.register(
            Command(name="finance", description="Finance: bills & subscriptions", handler=self._cmd_finance)
        )
        self.registry.register(
            Command(name="setup", description="Re-run setup wizard to change config", handler=self._cmd_setup)
        )
        self.registry.register(
            Command(name="doctor", description="Check configuration health", handler=self._cmd_doctor)
        )
        self.registry.register(
            Command(name="config", description="Show current configuration", handler=self._cmd_config)
        )
        self.registry.register(
            Command(name="note", description="Save a note: /note <title>", aliases=["notes"], handler=self._cmd_note)
        )
        self.registry.register(Command(name="today", description="Show today's overview", handler=self._cmd_today))
        self.registry.register(
            Command(name="radar", description="Show ranked attention radar", handler=self._cmd_radar)
        )
        self.registry.register(
            Command(name="calendar", description="Show calendar integrations", handler=self._cmd_calendar)
        )
        self.registry.register(
            Command(name="mcp", description="Show external MCP servers and their tools", handler=self._cmd_mcp)
        )
        self.registry.register(
            Command(
                name="majlis",
                description="Open MohaMind command center",
                aliases=["hq", "deck"],
                handler=self._cmd_majlis,
            )
        )
        self.registry.register(
            Command(
                name="provider", description="Switch LLM provider: /provider zai|openai", handler=self._cmd_provider
            )
        )
        self.registry.register(
            Command(name="model", description="Change model: /model <name>", handler=self._cmd_model)
        )
        self.registry.register(
            Command(name="key", description="Update API key for current provider", handler=self._cmd_key)
        )

        self.input = InputHandler(self.registry.get_completions())

    async def _cmd_help(self, args: str = "") -> str | None:
        self.console.print(display_help(self.registry.get_help_list(), self._current_mood()))
        return None

    async def _cmd_quit(self, args: str = "") -> str | None:
        self._running = False
        theme = get_theme(self._current_mood())
        self.console.print(Text("\n  signing off — mohamind will keep remembering.\n", style=f"italic {theme['dim']}"))
        return None

    async def _cmd_tasks(self, args: str = "") -> str | None:
        tasks = self.memory.get_task_section()
        active = [t for t in tasks if not t["done"]]
        if not active:
            self.console.print(display_success("No active tasks — you're all caught up."))
        else:
            self.console.print(display_tasks(active, self._current_mood()))
        return None

    async def _cmd_reminders(self, args: str = "") -> str | None:
        from moha_mind.mcp_servers.reminders.server import ReminderServer

        days_ahead = 14
        if args.strip().isdigit():
            days_ahead = int(args.strip())

        server = ReminderServer(self.memory)
        result = await server._list_reminders(days_ahead=days_ahead)
        self.console.print(display_calendar_snapshot(result, self._current_mood()))
        return None

    async def _cmd_remind(self, args: str = "") -> str | None:
        if not args.strip():
            self.console.print(display_error("Usage: /remind <message with date/time>"))
            return None

        response = await self.agent.chat(
            (
                "Set a timed reminder for this request. "
                "Support colloquial Arabic and Saudi/Gulf dialect naturally. "
                "Convert any relative date/time into an exact Asia/Riyadh datetime and use the reminder tools: "
                f"{args.strip()}"
            ),
            chat_id="cli",
        )
        self.console.print(display_response(response, self._current_mood()))
        return None

    async def _cmd_briefing(self, args: str = "") -> str | None:
        self.spinner = NeuralPulse(self.console, self._current_mood())
        self.spinner.start()
        try:
            briefing = await self.agent.generate_briefing()
            self.console.print(display_briefing(briefing, self._current_mood()))
        except Exception as e:
            self.console.print(display_error(f"Failed to generate briefing: {e}"))
        finally:
            if self.spinner:
                self.spinner.stop()
        return None

    async def _cmd_expiring(self, args: str = "") -> str | None:
        days = 90
        if args.strip().isdigit():
            days = int(args.strip())
        items = self.memory.get_expiring_items(days)
        if not items:
            self.console.print(display_success("Nothing expiring soon."))
        else:
            self.console.print(display_expiring(items, self._current_mood()))
        return None

    async def _cmd_search(self, args: str = "") -> str | None:
        query = args.strip()
        if not query:
            self.console.print(display_error("Usage: /search <query>"))
            return None
        results = self.memory.search(query)
        if not results:
            self.console.print(display_success("No results found."))
        else:
            self.console.print(display_memory_search(results, self._current_mood()))
        return None

    async def _cmd_recall(self, args: str = "") -> str | None:
        query = args.strip()
        if not query:
            self.console.print(display_error("Usage: /recall <query>"))
            return None

        theme = get_theme(self._current_mood())
        recalled = self.agent.recall(query, chat_id="cli")
        self.console.print(hermes_panel(recalled, "recall", theme))
        return None

    async def _cmd_memory(self, args: str = "") -> str | None:
        theme = get_theme(self._current_mood())
        table = Table(show_header=True, box=None, padding=(0, 1), expand=True)
        table.add_column("Category", style=f"bold {theme['accent']}", width=16)
        table.add_column("Size", style="dim", width=8)
        table.add_column("Preview", style=theme["primary"])

        categories = [
            "profile",
            "family",
            "tasks",
            "reminders",
            "occasions",
            "vehicle",
            "finances",
            "health",
            "home",
            "documents",
            "travel",
            "learning",
            "shopping",
            "relationships",
            "energy_log",
        ]
        for cat in categories:
            content = self.memory.read(cat)
            size = f"{len(content)} chars"
            preview = content[:80].replace("\n", " ").strip()
            if not preview:
                preview = "(empty)"
            table.add_row(cat, size, Text(preview))

        self.console.print(hermes_panel(table, "memory banks", theme))
        return None

    async def _cmd_review(self, args: str = "") -> str | None:
        self.spinner = NeuralPulse(self.console, self._current_mood())
        self.spinner.start()
        try:
            review = await self.agent.generate_weekly_review()
            self.console.print(display_briefing(review, self._current_mood()))
        except Exception as e:
            self.console.print(display_error(f"Failed to generate review: {e}"))
        finally:
            if self.spinner:
                self.spinner.stop()
        return None

    async def _cmd_stats(self, args: str = "") -> str | None:
        theme = get_theme(self._current_mood())
        tasks = self.memory.get_task_section()
        active = [t for t in tasks if not t["done"]]
        expiring = self.memory.get_expiring_items(90)
        conversations = self.agent.session_store.count_messages()
        productive_hours = self.energy.get_productive_hours()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style=theme["accent"], width=20)
        table.add_column(style=theme["primary"])
        table.add_row("LLM Provider:", self.agent.provider)
        table.add_row("Model:", self.agent.model)
        strategy = getattr(self.agent, "strategy", "fallback")
        table.add_row("Strategy:", strategy)
        verifier = getattr(self.agent, "verifier", None)
        if verifier is not None:
            table.add_row("Verifier:", f"{verifier.provider} ({verifier.model})")
        table.add_row("Active Tasks:", str(len(active)))
        table.add_row("Expiring Items:", str(len(expiring)))
        table.add_row("Messages Tracked:", str(conversations))
        table.add_row("Productive Hours:", ", ".join(f"{h}:00" for h in productive_hours))
        table.add_row("Current Mood:", self._current_mood())
        table.add_row("Time:", f"{ksa_date_display()} {ksa_time_str()}")

        self.console.print(hermes_panel(table, "system stats", theme))
        return None

    async def _cmd_clear(self, args: str = "") -> str | None:
        self.console.clear()
        self._show_status()
        return None

    async def _cmd_mood(self, args: str = "") -> str | None:
        theme = get_theme(self._current_mood())
        productive = self.energy.get_productive_hours()
        suggestion = self.energy.get_energy_suggestion()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style=theme["accent"], width=20)
        table.add_column(style=theme["primary"])
        table.add_row("Current Mood:", self._current_mood())
        table.add_row("Productive Hours:", ", ".join(f"{h}:00" for h in productive))
        table.add_row("Suggestion:", suggestion)

        self.console.print(hermes_panel(table, "mood & energy", theme))
        return None

    async def _cmd_add(self, args: str = "") -> str | None:
        if not args.strip():
            self.console.print(display_error("Usage: /add task <text> or /add note <title>"))
            return None

        parts = args.strip().split(maxsplit=1)
        subcmd = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        if subcmd == "task" and rest:
            self.memory.add_task(text=rest)
            self.console.print(display_success(f"Task added: {rest}"))
        elif subcmd == "note" and rest:
            title_parts = rest.split(maxsplit=1)
            title = title_parts[0]
            content = title_parts[1] if len(title_parts) > 1 else ""
            path = self.memory.save_note(title, content or "(quick note)")
            self.console.print(display_success(f"Note saved: {path.name}"))
        else:
            self.console.print(display_error("Usage: /add task <text> or /add note <title> [content]"))
        return None

    async def _cmd_done(self, args: str = "") -> str | None:
        if not args.strip():
            self.console.print(display_error("Usage: /done <task text>"))
            return None
        success = self.memory.complete_task(args.strip())
        if success:
            self.console.print(display_success(f"Task completed: {args.strip()}"))
        else:
            self.console.print(display_error(f"Task not found: {args.strip()}"))
        return None

    async def _cmd_note(self, args: str = "") -> str | None:
        if not args.strip():
            notes = self.memory.list_notes()
            if not notes:
                self.console.print(display_success("No notes saved yet. Use /note <title> to create one."))
            else:
                theme = get_theme(self._current_mood())
                table = Table(show_header=True, box=None, padding=(0, 1))
                table.add_column("Note", style=f"bold {theme['accent']}")
                for n in notes:
                    table.add_row(n)
                self.console.print(hermes_panel(table, "notes", theme))
            return None

        parts = args.strip().split(maxsplit=1)
        title = parts[0]
        content = parts[1] if len(parts) > 1 else "(quick note)"
        path = self.memory.save_note(title, content)
        self.console.print(display_success(f"Note saved: {path.name}"))
        return None

    async def _cmd_family(self, args: str = "") -> str | None:
        from moha_mind.mcp_servers.family.server import FamilyServer

        theme = get_theme(self._current_mood())
        server = FamilyServer(self.memory)
        result = await server._get_upcoming(days_ahead=30)
        self.console.print(hermes_panel(result, "family", theme))
        return None

    async def _cmd_social(self, args: str = "") -> str | None:
        from moha_mind.mcp_servers.social.server import SocialServer

        theme = get_theme(self._current_mood())
        server = SocialServer(self.memory)
        neglected = await server._get_neglected(days_threshold=30)
        birthdays = await server._get_upcoming_birthdays(days_ahead=60)

        combined = f"{neglected}\n\n{birthdays}"
        self.console.print(hermes_panel(combined, "social", theme))
        return None

    async def _cmd_vehicle(self, args: str = "") -> str | None:
        theme = get_theme(self._current_mood())
        content = self.memory.read("vehicle")
        if not content.strip():
            self.console.print(display_success("No vehicle data yet. Tell me about your car!"))
        else:
            self.console.print(hermes_panel(content, "vehicle", theme))
        return None

    async def _cmd_health(self, args: str = "") -> str | None:
        theme = get_theme(self._current_mood())
        content = self.memory.read("health")
        if not content.strip():
            self.console.print(display_success("No health data yet. Tell me about your medications or vitals!"))
        else:
            self.console.print(hermes_panel(content, "health", theme))
        return None

    async def _cmd_finance(self, args: str = "") -> str | None:
        from moha_mind.mcp_servers.life_tracker.server import LifeTrackerServer

        theme = get_theme(self._current_mood())
        server = LifeTrackerServer(self.memory)
        upcoming = await server._finance_get_upcoming(days_ahead=30)
        self.console.print(hermes_panel(upcoming, "finance", theme))
        return None

    async def _cmd_setup(self, args: str = "") -> str | None:
        from moha_mind.cli.setup_wizard import SetupWizard

        wizard = SetupWizard(self.console)
        wizard.run(quick="--quick" in args)
        self.console.print(display_success("Configuration updated! Restart MohaMind for changes to take effect."))
        return None

    async def _cmd_doctor(self, args: str = "") -> str | None:
        from moha_mind.cli.setup_wizard import run_doctor

        run_doctor()
        return None

    async def _cmd_config(self, args: str = "") -> str | None:
        theme = get_theme(self._current_mood())
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style=theme["accent"], width=24)
        table.add_column(style=theme["primary"])

        table.add_row("LLM Provider:", self.agent.provider)
        table.add_row("Model:", self.agent.model)
        strategy = getattr(self.agent, "strategy", settings.effective_strategy)
        table.add_row("Strategy:", strategy)
        verifier = getattr(self.agent, "verifier", None)
        if verifier is not None:
            table.add_row("Verifier:", f"{verifier.provider} ({verifier.model})")
        table.add_row("Timezone:", settings.timezone)
        table.add_row("Briefing Time:", settings.morning_briefing_time)
        table.add_row("Weekly Review:", f"{settings.weekly_review_day} at {settings.weekly_review_time}")
        table.add_row("Memory Dir:", settings.memory_dir)
        table.add_row("Telegram:", "Configured" if settings.telegram_bot_token else "Not configured")
        table.add_row("Google Cal:", "Configured" if settings.google_credentials_path else "Not configured")
        table.add_row("MS Graph:", "Configured" if settings.ms_client_id else "Not configured")

        self.console.print(hermes_panel(table, "configuration", theme))
        return None

    async def _cmd_today(self, args: str = "") -> str | None:
        theme = get_theme(self._current_mood())
        tasks = self.memory.get_task_section()
        active = [t for t in tasks if not t["done"]]
        expiring = self.memory.get_expiring_items(7)

        parts = []
        parts.append(f"**{len(active)} active tasks**")
        for t in active[:5]:
            due_info = f" (due {t['due']})" if t["due"] else ""
            parts.append(f"  - [{t['priority'].upper()}] {t['text']}{due_info}")

        if expiring:
            parts.append(f"\n**{len(expiring)} items expiring within 7 days**")
            for item in expiring[:5]:
                parts.append(f"  - {item['category']}: {item['detail']} ({item['days_left']}d)")

        parts.append(f"\n{ksa_date_display()} · {ksa_time_str()}")

        self.console.print(hermes_panel("\n".join(parts), "today", theme))
        return None

    async def _cmd_radar(self, args: str = "") -> str | None:
        from moha_mind.mcp_servers.attention.server import AttentionServer

        server = AttentionServer(self.memory)
        radar = await server._get_attention_radar(days_ahead=30, limit=8)
        self.console.print(display_attention_radar(radar, self._current_mood()))
        return None

    async def _calendar_snapshot(self, days_ahead: int = 3) -> str:
        sections = []

        try:
            from moha_mind.mcp_servers.google_calendar.server import GoogleCalendarServer

            google_text = await GoogleCalendarServer(self.memory)._list_events(days_ahead=days_ahead)
            sections.append(f"### Google Calendar\n{google_text}")
        except Exception as e:
            sections.append(f"### Google Calendar\nUnavailable: {e}")

        try:
            from moha_mind.mcp_servers.microsoft_graph.server import MicrosoftGraphServer

            ms_text = await MicrosoftGraphServer(self.memory)._list_calendar_events(days_ahead=days_ahead)
            sections.append(f"### Microsoft Calendar\n{ms_text}")
        except Exception as e:
            sections.append(f"### Microsoft Calendar\nUnavailable: {e}")

        return "\n\n".join(sections)

    async def _cmd_calendar(self, args: str = "") -> str | None:
        days_ahead = 3
        if args.strip().isdigit():
            days_ahead = int(args.strip())

        snapshot = await self._calendar_snapshot(days_ahead=days_ahead)
        self.console.print(display_calendar_snapshot(snapshot, self._current_mood()))
        return None

    async def _cmd_mcp(self, args: str = "") -> str | None:
        theme = get_theme(self._current_mood())
        manager = getattr(self.agent, "external_mcp", None)

        if manager is None or not manager.configs:
            self.console.print(
                hermes_panel(
                    Text.from_markup(
                        "No external MCP servers configured.\n\n"
                        f"Create [bold]{settings.mcp_servers_config}[/] "
                        "(see mcp_servers.example.json) and restart MohaMind.\n"
                        'Format: {"mcpServers": {"name": {"command": ..., "args": [...]}}}',
                        style=theme["primary"],
                    ),
                    "mcp servers",
                    theme,
                )
            )
            return None

        table = Table(show_header=True, box=None, padding=(0, 1), expand=True)
        table.add_column("Server", style=f"bold {theme['accent']}", width=16)
        table.add_column("State", width=12)
        table.add_column("Transport", style="dim", width=10)
        table.add_column("Tools", style=theme["primary"])

        state_styles = {"connected": "bold green", "failed": "bold red", "disabled": "dim"}
        for entry in manager.status():
            tools_text = ", ".join(entry["tools"]) if entry["tools"] else (entry["detail"] or "—")
            table.add_row(
                entry["name"],
                Text(entry["state"], style=state_styles.get(entry["state"], "")),
                entry["transport"],
                Text(tools_text),
            )

        self.console.print(hermes_panel(table, "mcp servers", theme))
        return None

    async def _cmd_majlis(self, args: str = "") -> str | None:
        from moha_mind.mcp_servers.attention.server import AttentionServer
        from moha_mind.mcp_servers.family.server import FamilyServer
        from moha_mind.mcp_servers.life_tracker.server import LifeTrackerServer
        from moha_mind.mcp_servers.social.server import SocialServer

        attention_server = AttentionServer(self.memory)
        family_server = FamilyServer(self.memory)
        life_server = LifeTrackerServer(self.memory)
        social_server = SocialServer(self.memory)

        from moha_mind.mcp_servers.reminders.server import ReminderServer

        reminder_server = ReminderServer(self.memory)

        radar, family, finance, neglected, birthdays, calendar, reminder_queue = await asyncio.gather(
            attention_server._get_attention_radar(days_ahead=14, limit=6),
            family_server._get_upcoming(days_ahead=14),
            life_server._finance_get_upcoming(days_ahead=14),
            social_server._get_neglected(days_threshold=30),
            social_server._get_upcoming_birthdays(days_ahead=30),
            self._calendar_snapshot(days_ahead=3),
            reminder_server._list_reminders(days_ahead=14),
        )

        active_tasks = [t for t in self.memory.get_task_section() if not t["done"]]
        task_lines = ["### Mission Board"]
        if active_tasks:
            for task in active_tasks[:6]:
                due_info = f" (due {task['due']})" if task["due"] else ""
                task_lines.append(f"- [{task['priority'].upper()}] {task['text']}{due_info}")
        else:
            task_lines.append("- No active tasks.")

        expiring = self.memory.get_expiring_items(14)
        expiry_lines = ["### Expiry Watch"]
        if expiring:
            for item in expiring[:6]:
                expiry_lines.append(f"- [{item['days_left']}d] {item['detail']}")
        else:
            expiry_lines.append("- Nothing expiring soon.")

        sections = [
            {"title": "attention radar", "body": radar},
            {"title": "calendar horizon", "body": calendar},
            {"title": "reminder queue", "body": reminder_queue},
            {"title": "mission board", "body": "\n".join(task_lines)},
            {"title": "expiry watch", "body": "\n".join(expiry_lines)},
            {"title": "family orbit", "body": family},
            {"title": "social pulse", "body": f"{neglected}\n\n{birthdays}"},
            {"title": "money horizon", "body": finance},
        ]
        self.console.print(display_command_center(sections, self._current_mood()))
        return None

    async def _cmd_provider(self, args: str = "") -> str | None:
        from rich.prompt import Prompt

        from moha_mind.cli.setup_wizard import OPENAI_MODELS, ZAI_MODELS

        known_models = {"zai": ZAI_MODELS, "openai": OPENAI_MODELS}

        if args.strip() in ("zai", "openai"):
            provider = args.strip()
        else:
            self.console.print(f"\n  [bold]Switch LLM provider[/]  (current: [cyan]{self.agent.provider}[/])")
            self.console.print("  [bold cyan]zai[/]     — z.ai / Zhipu GLM  (cost-effective, fast)")
            self.console.print("  [bold cyan]openai[/]  — OpenAI GPT  (gpt-4o, gpt-4o-mini, …)")
            provider = Prompt.ask(
                "  Provider", choices=["zai", "openai"], default=self.agent.provider, console=self.console
            )

        # --- Pick model for the new provider ---
        from moha_mind.config import settings as s

        if provider == "zai":
            current_model = s.zai_model
            base_url = s.zai_base_url
            api_key = s.zai_api_key
        else:
            current_model = s.openai_model
            base_url = None
            api_key = s.openai_api_key

        model_choices = known_models[provider]
        self.console.print(f"\n  [bold]Model[/]  (current: [cyan]{current_model}[/])")
        for m in model_choices:
            marker = " ←" if m == current_model else ""
            self.console.print(f"    [dim]{m}[/dim]{marker}")
        chosen_model = Prompt.ask(
            "  Model",
            choices=model_choices,
            default=current_model if current_model in model_choices else model_choices[0],
            console=self.console,
        )
        if chosen_model == "custom":
            chosen_model = Prompt.ask("  Custom model name", console=self.console)

        # Apply to running agent
        self.agent.client.base_url = base_url  # type: ignore[assignment]
        self.agent.client.api_key = api_key
        self.agent.model = chosen_model
        self.agent.provider = provider

        # Persist to .env
        env_path = Path(".env")
        model_key = "ZAI_MODEL" if provider == "zai" else "OPENAI_MODEL"
        if env_path.exists():
            file_lines = env_path.read_text().splitlines()
            updated: list[str] = []
            touched = {"PRIMARY_LLM": False, model_key: False}
            for line in file_lines:
                if line.startswith("PRIMARY_LLM="):
                    updated.append(f"PRIMARY_LLM={provider}")
                    touched["PRIMARY_LLM"] = True
                elif line.startswith(f"{model_key}="):
                    updated.append(f"{model_key}={chosen_model}")
                    touched[model_key] = True
                else:
                    updated.append(line)
            for k, was_written in touched.items():
                if not was_written:
                    val = provider if k == "PRIMARY_LLM" else chosen_model
                    updated.append(f"{k}={val}")
            env_path.write_text("\n".join(updated) + "\n")

        self.console.print(display_success(f"Switched to [bold]{provider}[/]  model: [bold]{chosen_model}[/]"))
        return None

    async def _cmd_model(self, args: str = "") -> str | None:
        from rich.prompt import Prompt
        from rich.table import Table

        from moha_mind.cli.setup_wizard import OPENAI_MODELS, ZAI_MODELS

        provider = self.agent.provider
        known = ZAI_MODELS if provider == "zai" else OPENAI_MODELS
        current = self.agent.model

        if not args.strip():
            # Show known models for this provider
            theme = get_theme(self._current_mood())
            table = Table(show_header=False, box=None, padding=(0, 2))
            table.add_column(style=theme["accent"], width=26)
            table.add_column(style="dim")
            for m in known:
                if m == "custom":
                    continue
                marker = " ← active" if m == current else ""
                table.add_row(m, marker)
            self.console.print(hermes_panel(table, f"models · {provider}", theme))
            new_model = Prompt.ask(
                "  Switch to model (or Enter to keep current)",
                default=current,
                console=self.console,
            )
        else:
            new_model = args.strip()

        if not new_model or new_model == current:
            return None

        old_model = current
        self.agent.model = new_model

        # Persist to .env
        env_path = Path(".env")
        model_key = "ZAI_MODEL" if provider == "zai" else "OPENAI_MODEL"
        if env_path.exists():
            file_lines = env_path.read_text().splitlines()
            updated: list[str] = []
            written = False
            for line in file_lines:
                if line.startswith(f"{model_key}="):
                    updated.append(f"{model_key}={new_model}")
                    written = True
                else:
                    updated.append(line)
            if not written:
                updated.append(f"{model_key}={new_model}")
            env_path.write_text("\n".join(updated) + "\n")

        self.console.print(display_success(f"Model: [bold]{old_model}[/] → [bold]{new_model}[/]"))
        return None

    async def _cmd_key(self, args: str = "") -> str | None:
        from rich.prompt import Prompt

        provider = self.agent.provider
        key_name = "z.ai" if provider == "zai" else "OpenAI"
        env_key = "ZAI_API_KEY" if provider == "zai" else "OPENAI_API_KEY"
        url = "https://z.ai" if provider == "zai" else "https://platform.openai.com/api-keys"

        self.console.print(f"\n  Update {key_name} API key")
        self.console.print(f"  Get from [bold cyan]{url}[/]")
        new_key = Prompt.ask(f"  {key_name} key", console=self.console)

        if not new_key.strip():
            self.console.print(display_error("No key provided."))
            return None

        env_path = Path(".env")
        file_lines = env_path.read_text().splitlines() if env_path.exists() else []
        updated = False
        new_lines = []
        for line in file_lines:
            if line.startswith(f"{env_key}="):
                new_lines.append(f"{env_key}={new_key.strip()}")
                updated = True
            else:
                new_lines.append(line)
        if not updated:
            new_lines.append(f"{env_key}={new_key.strip()}")
        env_path.write_text("\n".join(new_lines) + "\n")

        self.agent.client.api_key = new_key.strip()
        self.console.print(display_success(f"{key_name} API key updated!"))
        return None

    def _current_mood(self) -> str:
        recent = self.memory.read("energy_log")
        if not recent.strip():
            return "neutral"
        lines = [ln for ln in recent.strip().split("\n") if ln.strip() and not ln.startswith("#")]
        if not lines:
            return "neutral"
        last_line = lines[-1].lower()
        if any(w in last_line for w in ["high", "great", "awesome", "happy", "excited", "productive"]):
            return "high"
        if any(w in last_line for w in ["low", "tired", "stressed", "sick", "overwhelmed"]):
            return "low"
        return "neutral"

    def _show_status(self) -> None:
        tasks = self.memory.get_task_section()
        active = [t for t in tasks if not t["done"]]
        expiring = self.memory.get_expiring_items(14)
        bar = display_status_bar(
            model=self.agent.model,
            provider=self.agent.provider,
            mood=self._current_mood(),
            tasks_active=len(active),
            expiring_soon=len(expiring),
        )
        self.console.print(bar)

    def show_banner(self) -> None:
        tasks = self.memory.get_task_section()
        active = [t for t in tasks if not t["done"]]
        expiring = self.memory.get_expiring_items(90)

        time_display = f"{ksa_date_display()} • {ksa_time_str()}"

        banner = build_banner(
            version="0.1.0",
            model=self.agent.model,
            provider=self.agent.provider,
            timezone=settings.timezone,
            tasks_count=len(active),
            expiring_count=len(expiring),
            mood=self._current_mood(),
            uptime_hint=time_display,
            telegram_enabled=bool(settings.telegram_bot_token),
            google_enabled=Path(settings.google_credentials_path).exists() or Path(settings.google_token_path).exists(),
            microsoft_enabled=bool(settings.ms_client_id),
        )
        self.console.print(banner)

    async def _handle_command(self, text: str) -> bool:
        if not text.startswith("/"):
            return False

        parts = text[1:].split(maxsplit=1)
        cmd_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        cmd = self.registry.get(cmd_name)
        if cmd and cmd.handler:
            await cmd.handler(args)
            return True

        self.console.print(display_error(f"Unknown command: /{cmd_name}. Type /help for available commands."))
        return True

    async def _process_message(self, text: str) -> None:
        mood = self._current_mood()
        self.spinner = NeuralPulse(self.console, mood)
        self.spinner.start()

        try:
            response = await self.agent.chat(text, chat_id="cli")
            self.spinner.stop()
            self.console.print()
            self.console.print(display_response(response, mood))
            self.console.print()
        except Exception as e:
            self.spinner.stop()
            self.console.print(display_error(f"Something went wrong: {e}"))
            log.error(f"CLI chat error: {e}")

    async def run(self) -> None:
        self._running = True

        self.show_banner()
        self._show_status()
        recent = self.agent.session_store.load_recent_messages("cli", limit=4)
        if recent:
            theme = get_theme(self._current_mood())
            recap_lines = []
            for item in recent:
                recap_lines.append(f"{item['role']}: {self.agent._truncate_text(item['content'], 120)}")
            self.console.print(hermes_panel("\n".join(recap_lines), "previous conversation", theme))

        while self._running:
            try:
                text = await self.input.get_input(self._current_mood())
            except Exception:
                text = self.input.get_input_sync(self._current_mood())

            if not text:
                continue

            if text == "/quit":
                await self._cmd_quit()
                break

            is_command = await self._handle_command(text)

            if not is_command:
                await self._process_message(text)

            if self._running:
                self._show_status()

    async def run_headless(self, message: str) -> str:
        return await self.agent.chat(message, chat_id="cli")
