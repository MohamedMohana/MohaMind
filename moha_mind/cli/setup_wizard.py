"""Setup wizard for MohaMind - interactive first-run configuration.

Inspired by Hermes agent's onboarding flow:
- Auto-detect existing config
- Guided step-by-step setup
- Validate keys before saving
- Pretty Rich panels and prompts
"""

import os
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

ENV_PATH = Path(".env")

SETUP_STEPS = [
    {
        "key": "PRIMARY_LLM",
        "label": "LLM Provider",
        "category": "brain",
        "choices": ["zai", "openai"],
        "default": "zai",
        "description": "Which AI brain to use as primary",
        "docs": "z.ai = Zhipu GLM (cost-effective) | openai = OpenAI GPT",
    },
    {
        "key": "ZAI_API_KEY",
        "label": "z.ai API Key",
        "category": "brain",
        "default": "",
        "secret": True,
        "description": "Get from https://open.bigmodel.cn",
        "required_if": {"PRIMARY_LLM": "zai"},
    },
    {
        "key": "OPENAI_API_KEY",
        "label": "OpenAI API Key",
        "category": "brain",
        "default": "",
        "secret": True,
        "description": "Get from https://platform.openai.com/api-keys",
        "required_if": {"PRIMARY_LLM": "openai"},
    },
    {
        "key": "TELEGRAM_BOT_TOKEN",
        "label": "Telegram Bot Token",
        "category": "telegram",
        "default": "",
        "secret": True,
        "description": "Create via @BotFather on Telegram",
        "optional": True,
    },
    {
        "key": "TELEGRAM_CHAT_ID",
        "label": "Telegram Chat ID",
        "category": "telegram",
        "default": "",
        "description": "Get from @userinfobot on Telegram",
        "optional": True,
    },
    {
        "key": "TIMEZONE",
        "label": "Timezone",
        "category": "schedule",
        "default": "Asia/Riyadh",
        "description": "Your IANA timezone",
    },
    {
        "key": "MORNING_BRIEFING_TIME",
        "label": "Morning Briefing Time",
        "category": "schedule",
        "default": "08:00",
        "description": "When to send daily briefing (HH:MM)",
    },
]


class SetupWizard:
    def __init__(self, console: Console | None = None):
        self.console = console or Console()
        self.config: dict[str, str] = {}
        self.existing: dict[str, str] = {}

    def _load_existing(self) -> dict[str, str]:
        env_vars: dict[str, str] = {}
        if ENV_PATH.exists():
            for line in ENV_PATH.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    env_vars[key.strip()] = value.strip()
        for key in [s["key"] for s in SETUP_STEPS]:
            env_val = os.environ.get(key, "")
            if env_val:
                env_vars[key] = env_val
        return env_vars

    def _mask(self, value: str) -> str:
        if len(value) <= 8:
            return "*" * len(value) if value else "(not set)"
        return value[:4] + "*" * (len(value) - 8) + value[-4:]

    def _is_step_needed(self, step: dict, config: dict[str, str]) -> bool:
        if "required_if" in step:
            for req_key, req_val in step["required_if"].items():
                if config.get(req_key) == req_val:
                    return True
            return False
        return True

    def show_welcome(self) -> None:
        title = Text()
        title.append("M", style="bold red")
        title.append("o", style="bold yellow")
        title.append("h", style="bold green")
        title.append("a", style="bold cyan")
        title.append("M", style="bold blue")
        title.append("i", style="bold magenta")
        title.append("n", style="bold red")
        title.append("d", style="bold yellow")

        welcome = Text()
        welcome.append("Welcome to ")
        welcome.append_text(title)
        welcome.append(" Setup Wizard!\n\n")
        welcome.append("This will guide you through configuring your personal AI agent.\n")
        welcome.append("You can re-run this anytime with ")
        welcome.append("mohamind setup", style="bold cyan")
        welcome.append(".\n\n")
        welcome.append("Your settings are saved to ", style="dim")
        welcome.append(".env", style="bold")
        welcome.append(" (never committed to git).", style="dim")

        self.console.print(Panel(welcome, border_style="cyan", padding=(1, 2), title=title))

    def show_current_config(self, config: dict[str, str]) -> None:
        if not config:
            return

        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("Setting", style="cyan", width=28)
        table.add_column("Current Value", width=40)
        table.add_column("Status", width=10)

        for step in SETUP_STEPS:
            key = step["key"]
            value = config.get(key, "")
            if not value:
                if step.get("optional") or not self._is_step_needed(step, config):
                    continue
                table.add_row(step["label"], "(not set)", "⚠️")
            elif step.get("secret"):
                table.add_row(step["label"], self._mask(value), "✅")
            else:
                table.add_row(step["label"], value, "✅")

        self.console.print(Panel(table, title="📋 Current Configuration", border_style="green", padding=(1, 2)))

    def configure_step(self, step: dict, config: dict[str, str]) -> str:
        key = step["key"]
        current = config.get(key, "")

        if "choices" in step:
            choice_str = " | ".join(f"[{c}]" if c == step["default"] else c for c in step["choices"])
            self.console.print(f"\n  [bold]{step['label']}[/]")
            self.console.print(f"  [dim]{step.get('docs', step.get('description', ''))}[/]")
            self.console.print(f"  Options: {choice_str}")
            if current:
                self.console.print(f"  Current: [green]{current}[/]")
            value = Prompt.ask(
                "  Choose",
                choices=step["choices"],
                default=current or step["default"],
                console=self.console,
            )
        elif step.get("secret"):
            self.console.print(f"\n  [bold]{step['label']}[/]")
            self.console.print(f"  [dim]{step.get('description', '')}[/]")
            if current:
                self.console.print(f"  Current: [green]{self._mask(current)}[/]")
                if Confirm.ask("  Keep current?", default=True, console=self.console):
                    return current
            value = Prompt.ask("  Enter key (hidden)", console=self.console)
        else:
            self.console.print(f"\n  [bold]{step['label']}[/]")
            self.console.print(f"  [dim]{step.get('description', '')}[/]")
            if current:
                self.console.print(f"  Current: [green]{current}[/]")
            value = Prompt.ask(
                "  Enter value",
                default=current or step.get("default", ""),
                console=self.console,
            )

        return value.strip()

    def save_config(self, config: dict[str, str]) -> None:
        all_keys = {s["key"] for s in SETUP_STEPS}
        all_keys.update({"FALLBACK_LLM", "ZAI_MODEL", "ZAI_BASE_URL", "OPENAI_MODEL"})

        existing_lines: list[str] = []
        written_keys: set[str] = set()

        if ENV_PATH.exists():
            for line in ENV_PATH.read_text().splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    existing_lines.append(line)
                    continue
                if "=" in stripped:
                    key = stripped.split("=", 1)[0].strip()
                    if key in config:
                        existing_lines.append(f"{key}={config[key]}")
                        written_keys.add(key)
                    elif key in all_keys:
                        existing_lines.append(line)
                        written_keys.add(key)
                    else:
                        existing_lines.append(line)
                else:
                    existing_lines.append(line)

        for key, value in config.items():
            if key not in written_keys and value:
                existing_lines.append(f"{key}={value}")

        ENV_PATH.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")
        self.console.print(
            Panel(f"Configuration saved to [bold green]{ENV_PATH}[/]", border_style="green", padding=(0, 2))
        )

    def run(self, quick: bool = False) -> dict[str, str]:
        self.show_welcome()

        self.existing = self._load_existing()

        if self.existing:
            self.show_current_config(self.existing)
            if not quick and not Confirm.ask("\n  Update configuration?", default=False, console=self.console):
                self.console.print("\n  [dim]Using existing configuration.[/]")
                return self.existing

        current_category = None
        for step in SETUP_STEPS:
            if not self._is_step_needed(step, self.existing):
                if step.get("optional"):
                    if quick:
                        continue
                    self.console.print(f"\n  [dim]Optional: {step['label']}[/]")
                    if not Confirm.ask("  Configure?", default=False, console=self.console):
                        self.config[step["key"]] = self.existing.get(step["key"], "")
                        continue
                else:
                    self.config[step["key"]] = self.existing.get(step["key"], "")
                    continue

            if step["category"] != current_category:
                current_category = step["category"]
                category_names = {"brain": "🧠 AI Brain", "telegram": "📱 Telegram", "schedule": "⏰ Schedule"}
                self.console.print(f"\n[bold cyan]── {category_names.get(current_category, current_category)} ──[/]")

            value = self.configure_step(step, self.existing)
            self.config[step["key"]] = value

        for key, val in self.existing.items():
            if key not in self.config:
                self.config[key] = val

        primary = self.config.get("PRIMARY_LLM", "zai")
        fallback = "openai" if primary == "zai" else "zai"
        self.config["FALLBACK_LLM"] = fallback

        if primary == "zai" and not self.config.get("ZAI_API_KEY"):
            self.config["ZAI_API_KEY"] = ""
        if primary == "openai" and not self.config.get("OPENAI_API_KEY"):
            self.config["OPENAI_API_KEY"] = ""

        self.save_config(self.config)

        self.show_current_config(self.config)

        self.console.print(
            Panel(
                "[bold green]Setup complete![/] Run [bold cyan]mohamind[/] to start your agent.\n\n"
                "Quick start:\n"
                "  [bold]mohamind[/]          - Start Telegram bot\n"
                "  [bold]mohamind --cli[/]    - Interactive CLI mode\n"
                "  [bold]mohamind setup[/]    - Re-run this wizard\n"
                "  [bold]mohamind doctor[/]   - Check configuration health",
                title="✅ All Done!",
                border_style="green",
                padding=(1, 2),
            )
        )

        return self.config


def run_setup(quick: bool = False) -> dict[str, str]:
    wizard = SetupWizard()
    return wizard.run(quick=quick)


def run_doctor() -> bool:
    console = Console()
    console.print(Panel("🔍 MohaMind Configuration Doctor", border_style="cyan", padding=(1, 2)))

    env_path = Path(".env")
    has_env = env_path.exists()

    table = Table(show_header=True, box=None, padding=(0, 2))
    table.add_column("Check", style="bold", width=35)
    table.add_column("Status", width=10)
    table.add_column("Details", style="dim")

    table.add_row(
        ".env file exists", "✅" if has_env else "❌", str(env_path.resolve()) if has_env else "Run: mohamind setup"
    )

    env_vars: dict[str, str] = {}
    if has_env:
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env_vars[k.strip()] = v.strip()

    primary = env_vars.get("PRIMARY_LLM", os.environ.get("PRIMARY_LLM", "zai"))
    zai_key = env_vars.get("ZAI_API_KEY", os.environ.get("ZAI_API_KEY", ""))
    openai_key = env_vars.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
    tg_token = env_vars.get("TELEGRAM_BOT_TOKEN", os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    tg_chat = env_vars.get("TELEGRAM_CHAT_ID", os.environ.get("TELEGRAM_CHAT_ID", ""))

    if primary == "zai":
        table.add_row(
            "Primary: z.ai API key",
            "✅" if zai_key else "❌",
            zai_key[:8] + "..." if zai_key else "Run: mohamind setup",
        )
    else:
        table.add_row(
            "Primary: OpenAI API key",
            "✅" if openai_key else "❌",
            openai_key[:8] + "..." if openai_key else "Run: mohamind setup",
        )

    table.add_row(
        "Telegram bot token", "✅" if tg_token else "⚠️", "Configured" if tg_token else "Optional - for Telegram mode"
    )
    table.add_row(
        "Telegram chat ID", "✅" if tg_chat else "⚠️", "Configured" if tg_chat else "Optional - for Telegram mode"
    )

    memory_dir = Path(env_vars.get("MEMORY_DIR", os.environ.get("MEMORY_DIR", "./memory")))
    table.add_row(
        "Memory directory",
        "✅" if memory_dir.exists() else "📁",
        str(memory_dir) + (" (exists)" if memory_dir.exists() else " (will create)"),
    )

    creds_dir = Path("credentials")
    table.add_row(
        "Credentials directory",
        "✅" if creds_dir.exists() else "📁",
        str(creds_dir) + (" (exists)" if creds_dir.exists() else " (will create)"),
    )

    console.print(table)

    critical_ok = (primary == "zai" and bool(zai_key)) or (primary == "openai" and bool(openai_key))

    if critical_ok:
        console.print(Panel("[bold green]Core configuration looks good![/]", border_style="green", padding=(0, 2)))
    else:
        console.print(
            Panel(
                "[bold red]Missing required API key![/]\nRun [bold cyan]mohamind setup[/] to configure.",
                border_style="red",
                padding=(0, 2),
            )
        )

    return critical_ok
