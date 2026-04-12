"""MohaMind CLI Application - The main interactive loop.

Orchestrates the banner, input, spinner, display, and agent
into a seamless terminal experience.
"""

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from moha_mind.agent.core import MohaMindAgent
from moha_mind.agent.energy_tracker import EnergyTracker
from moha_mind.agent.memory import MemoryManager
from moha_mind.cli.banner import build_banner
from moha_mind.cli.commands import Command, CommandRegistry
from moha_mind.cli.display import (
    display_briefing,
    display_error,
    display_expiring,
    display_help,
    display_memory_search,
    display_response,
    display_status_bar,
    display_success,
    display_tasks,
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
            Command(name="briefing", description="Generate morning briefing", handler=self._cmd_briefing)
        )
        self.registry.register(Command(name="expiring", description="Show expiring items", handler=self._cmd_expiring))
        self.registry.register(
            Command(name="search", description="Search memory: /search <query>", handler=self._cmd_search)
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
        self.console.print(Text("\n  👋 Goodbye! MohaMind will miss you.\n", style=f"italic {theme['dim']}"))
        return None

    async def _cmd_tasks(self, args: str = "") -> str | None:
        tasks = self.memory.get_task_section()
        active = [t for t in tasks if not t["done"]]
        if not active:
            self.console.print(display_success("No active tasks - you're all caught up! 🎉"))
        else:
            self.console.print(display_tasks(active, self._current_mood()))
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
            self.console.print(display_success("Nothing expiring soon! ✅"))
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

        self.console.print(
            Panel(
                table,
                title="💾 Memory Banks",
                title_align="left",
                border_style=theme["panel_border"],
                padding=(1, 2),
            )
        )
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
        conversations = sum(len(v) for v in self.agent.conversations.values())
        productive_hours = self.energy.get_productive_hours()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style=theme["accent"], width=20)
        table.add_column(style=theme["primary"])
        table.add_row("LLM Provider:", self.agent.provider)
        table.add_row("Model:", self.agent.model)
        table.add_row("Active Tasks:", str(len(active)))
        table.add_row("Expiring Items:", str(len(expiring)))
        table.add_row("Messages Tracked:", str(conversations))
        table.add_row("Productive Hours:", ", ".join(f"{h}:00" for h in productive_hours))
        table.add_row("Current Mood:", self._current_mood())
        table.add_row("Time:", f"{ksa_date_display()} {ksa_time_str()}")

        self.console.print(
            Panel(
                table,
                title="📊 System Stats",
                title_align="left",
                border_style=theme["panel_border"],
                padding=(1, 2),
            )
        )
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

        self.console.print(
            Panel(
                table,
                title="🧠 Mood & Energy",
                title_align="left",
                border_style=theme["panel_border"],
                padding=(1, 2),
            )
        )
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
            self.console.print(display_success(f"Task completed: {args.strip()} ✅"))
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
                self.console.print(Panel(table, title="📝 Notes", border_style=theme["panel_border"], padding=(1, 2)))
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
        self.console.print(Panel(result, title="👨‍👩‍👧‍👦 Family", border_style=theme["panel_border"], padding=(1, 2)))
        return None

    async def _cmd_social(self, args: str = "") -> str | None:
        from moha_mind.mcp_servers.social.server import SocialServer

        theme = get_theme(self._current_mood())
        server = SocialServer(self.memory)
        neglected = await server._get_neglected(days_threshold=30)
        birthdays = await server._get_upcoming_birthdays(days_ahead=60)

        combined = f"{neglected}\n\n{birthdays}"
        self.console.print(Panel(combined, title="📱 Social", border_style=theme["panel_border"], padding=(1, 2)))
        return None

    async def _cmd_vehicle(self, args: str = "") -> str | None:
        theme = get_theme(self._current_mood())
        content = self.memory.read("vehicle")
        if not content.strip():
            self.console.print(display_success("No vehicle data yet. Tell me about your car!"))
        else:
            self.console.print(Panel(content, title="🚗 Vehicle", border_style=theme["panel_border"], padding=(1, 2)))
        return None

    async def _cmd_health(self, args: str = "") -> str | None:
        theme = get_theme(self._current_mood())
        content = self.memory.read("health")
        if not content.strip():
            self.console.print(display_success("No health data yet. Tell me about your medications or vitals!"))
        else:
            self.console.print(Panel(content, title="🏥 Health", border_style=theme["panel_border"], padding=(1, 2)))
        return None

    async def _cmd_finance(self, args: str = "") -> str | None:
        from moha_mind.mcp_servers.life_tracker.server import LifeTrackerServer

        theme = get_theme(self._current_mood())
        server = LifeTrackerServer(self.memory)
        upcoming = await server._finance_get_upcoming(days_ahead=30)
        self.console.print(Panel(upcoming, title="💰 Finance", border_style=theme["panel_border"], padding=(1, 2)))
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
        table.add_row("Timezone:", settings.timezone)
        table.add_row("Briefing Time:", settings.morning_briefing_time)
        table.add_row("Weekly Review:", f"{settings.weekly_review_day} at {settings.weekly_review_time}")
        table.add_row("Memory Dir:", settings.memory_dir)
        table.add_row("Telegram:", "Configured" if settings.telegram_bot_token else "Not configured")
        table.add_row("Google Cal:", "Configured" if settings.google_credentials_path else "Not configured")
        table.add_row("MS Graph:", "Configured" if settings.ms_client_id else "Not configured")

        self.console.print(Panel(table, title="⚙️ Configuration", border_style=theme["panel_border"], padding=(1, 2)))
        return None

    async def _cmd_today(self, args: str = "") -> str | None:
        theme = get_theme(self._current_mood())
        tasks = self.memory.get_task_section()
        active = [t for t in tasks if not t["done"]]
        expiring = self.memory.get_expiring_items(7)

        parts = []
        parts.append(f"📋 **{len(active)} active tasks**")
        for t in active[:5]:
            due_info = f" (due {t['due']})" if t["due"] else ""
            parts.append(f"  - [{t['priority'].upper()}] {t['text']}{due_info}")

        if expiring:
            parts.append(f"\n⏰ **{len(expiring)} items expiring within 7 days**")
            for item in expiring[:5]:
                parts.append(f"  - {item['category']}: {item['detail']} ({item['days_left']}d)")

        parts.append(f"\n🕐 {ksa_date_display()} • {ksa_time_str()}")

        self.console.print(
            Panel("\n".join(parts), title="📅 Today", border_style=theme["panel_border"], padding=(1, 2))
        )
        return None

    async def _cmd_provider(self, args: str = "") -> str | None:
        from rich.prompt import Prompt

        if args.strip() in ("zai", "openai"):
            provider = args.strip()
        else:
            self.console.print("\n  [bold]Switch LLM provider:[/]")
            self.console.print("  [cyan]zai[/]     z.ai (Zhipu GLM-4)")
            self.console.print("  [cyan]openai[/]  OpenAI (GPT)")
            provider = Prompt.ask(
                "  Provider", choices=["zai", "openai"], default=self.agent.provider, console=self.console
            )

        if provider == "zai":
            from moha_mind.config import settings as s

            self.agent.client.base_url = s.zai_base_url
            self.agent.model = s.zai_model
            self.agent.provider = "zai"
        else:
            self.agent.client.base_url = None
            from moha_mind.config import settings as s

            self.agent.model = s.openai_model
            self.agent.provider = "openai"

        env_path = Path(".env")
        if env_path.exists():
            file_lines = env_path.read_text().splitlines()
            updated = []
            for line in file_lines:
                if line.startswith("PRIMARY_LLM="):
                    updated.append(f"PRIMARY_LLM={provider}")
                else:
                    updated.append(line)
            env_path.write_text("\n".join(updated) + "\n")

        self.console.print(display_success(f"Switched to {provider} ({self.agent.model})"))
        return None

    async def _cmd_model(self, args: str = "") -> str | None:
        if not args.strip():
            self.console.print(display_error("Usage: /model <model-name>"))
            self.console.print(f"  Current: [bold]{self.agent.model}[/]")
            return None

        new_model = args.strip()
        old_model = self.agent.model
        self.agent.model = new_model
        self.console.print(display_success(f"Model changed: {old_model} → {new_model}"))
        return None

    async def _cmd_key(self, args: str = "") -> str | None:
        from rich.prompt import Prompt

        provider = self.agent.provider
        key_name = "z.ai" if provider == "zai" else "OpenAI"
        env_key = "ZAI_API_KEY" if provider == "zai" else "OPENAI_API_KEY"
        url = "https://open.bigmodel.cn" if provider == "zai" else "https://platform.openai.com/api-keys"

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
