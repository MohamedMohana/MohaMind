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
from rich.markup import escape
from rich.prompt import Confirm, Prompt

ENV_PATH = Path(".env")

ZAI_MODELS = [
    "glm-5-turbo",
    "glm-5.1",
    "glm-4.7",
    "glm-4.6",
    "glm-4.5",
    "glm-5v-turbo",
    "custom",
]
OPENAI_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
    "custom",
]

SETUP_STEPS = [
    {
        "key": "PRIMARY_LLM",
        "label": "LLM Provider",
        "category": "brain",
        "choices": ["zai", "openai"],
        "default": "zai",
        "description": "Which AI brain to use as primary",
        "docs": "zai = Zhipu GLM (cost-effective)  |  openai = OpenAI GPT",
    },
    {
        "key": "LLM_STRATEGY",
        "label": "Secondary LLM Role",
        "category": "brain",
        "choices": ["fallback", "verify", "solo"],
        "default": "fallback",
        "description": "How the other provider is used",
        "docs": (
            "fallback = used only if primary fails  |  "
            "verify = double-checks primary replies  |  "
            "solo = don't use a secondary brain"
        ),
    },
    {
        "key": "VERIFIER_STRICTNESS",
        "label": "Verifier Strictness",
        "category": "brain",
        "choices": ["lenient", "balanced", "strict"],
        "default": "balanced",
        "description": "How picky the verifier is when reviewing replies",
        "docs": "lenient = only flag clear errors  |  balanced = default  |  strict = flag tone/format issues too",
        "required_if": {"LLM_STRATEGY": "verify"},
    },
    {
        "key": "ZAI_API_KEY",
        "label": "z.ai API Key",
        "category": "brain",
        "default": "",
        "secret": True,
        "description": "Get from https://z.ai",
        "required_if": {"PRIMARY_LLM": "zai"},
    },
    {
        "key": "ZAI_MODEL",
        "label": "z.ai Model",
        "category": "brain",
        "choices": ZAI_MODELS,
        "default": "glm-5-turbo",
        "description": "Which GLM model to use",
        "docs": "glm-5-turbo = agent/coding  |  glm-5.1 = flagship  |  glm-5v-turbo = vision",
        "required_if": {"PRIMARY_LLM": "zai"},
        "custom_prompt": "Enter custom GLM model name",
    },
    {
        "key": "ZAI_BASE_URL",
        "label": "z.ai API Base URL",
        "category": "brain",
        "default": "https://api.z.ai/api/paas/v4/",
        "description": "API endpoint (leave default unless using a proxy or custom endpoint)",
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
        "key": "OPENAI_MODEL",
        "label": "OpenAI Model",
        "category": "brain",
        "choices": OPENAI_MODELS,
        "default": "gpt-4o-mini",
        "description": "Which GPT model to use",
        "docs": "gpt-4o = best quality  |  gpt-4o-mini = cost-effective  |  gpt-3.5-turbo = cheapest",
        "required_if": {"PRIMARY_LLM": "openai"},
        "custom_prompt": "Enter custom OpenAI-compatible model name",
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
        "description": "Get from @userinfobot on Telegram. Only this chat can talk to the bot.",
        "optional": True,
    },
    {
        "key": "TELEGRAM_ALLOWED_USER_IDS",
        "label": "Extra Allowed Telegram IDs",
        "category": "telegram",
        "default": "",
        "description": "Optional comma-separated user IDs also allowed to talk to the bot",
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
    {
        "key": "GOOGLE_CREDENTIALS_PATH",
        "label": "Google Credentials",
        "category": "calendar",
        "default": "./credentials/google_credentials.json",
        "description": "Path to Google OAuth client JSON. First calendar use opens browser auth.",
        "optional": True,
    },
    {
        "key": "GOOGLE_TOKEN_PATH",
        "label": "Google Token Cache",
        "category": "calendar",
        "default": "./credentials/google_token.json",
        "description": "Where MohaMind stores the Google OAuth token after linking.",
        "optional": True,
    },
    {
        "key": "MS_CLIENT_ID",
        "label": "Microsoft Client ID",
        "category": "calendar",
        "default": "",
        "description": "Azure app client id. If set without a secret, device-code login is used.",
        "optional": True,
    },
    {
        "key": "MS_CLIENT_SECRET",
        "label": "Microsoft Client Secret",
        "category": "calendar",
        "default": "",
        "secret": True,
        "description": "Optional Azure app secret for confidential-client auth.",
        "optional": True,
    },
    {
        "key": "MS_TENANT_ID",
        "label": "Microsoft Tenant ID",
        "category": "calendar",
        "default": "common",
        "description": "Use common for personal/device-code login, or your tenant id.",
        "optional": True,
    },
    {
        "key": "MS_TOKEN_PATH",
        "label": "Microsoft Token Cache",
        "category": "calendar",
        "default": "./credentials/ms_token.json",
        "description": "Reserved token cache path for Microsoft integration.",
        "optional": True,
    },
    # ---------------- Memory upgrades ----------------
    {
        "key": "MEMORY_ROUTER_ENABLED",
        "label": "Memory Router",
        "category": "memory",
        "choices": ["true", "false"],
        "default": "true",
        "description": "Inject only the most relevant memory categories into the system prompt",
        "docs": (
            "true = compact prompt, scales as memory grows (recommended)  |  "
            "false = legacy behavior, pastes every category in full every turn"
        ),
    },
    {
        "key": "MEMORY_SUMMARIES_ENABLED",
        "label": "Rolling Summaries",
        "category": "memory",
        "choices": ["true", "false"],
        "default": "true",
        "description": "Keep a one-paragraph summary per memory category",
        "docs": "Summaries let the agent 'see' every category without loading it in full.",
    },
    {
        "key": "EMBEDDING_BACKEND",
        "label": "Semantic Search",
        "category": "memory",
        "choices": ["none", "openai", "local"],
        "default": "none",
        "description": "Concept-level search across memory + daily log + notes",
        "docs": (
            "none = FTS5 only (no extra deps)  |  "
            "openai = uses OPENAI_API_KEY + text-embedding-3-small  |  "
            "local = uses sentence-transformers (run: uv sync --extra embeddings)"
        ),
    },
    {
        "key": "EMBEDDING_MODEL",
        "label": "Embedding Model",
        "category": "memory",
        "default": "",
        "description": "Override the embedding model (leave empty for the backend default)",
        "docs": (
            "openai default: text-embedding-3-small  |  "
            "local default: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        ),
        "required_if_not": {"EMBEDDING_BACKEND": "none"},
        "optional": True,
    },
    {
        "key": "CONSOLIDATOR_ENABLED",
        "label": "Nightly Consolidator",
        "category": "memory",
        "choices": ["true", "false"],
        "default": "false",
        "description": "Review the day's activity each night and distill durable facts",
        "docs": (
            "Runs once a day. Extracts facts, observations and conflicts from the "
            "last 24h of daily log + messages. Off by default — opt in when ready."
        ),
    },
    {
        "key": "CONSOLIDATOR_MODE",
        "label": "Consolidator Mode",
        "category": "memory",
        "choices": ["hybrid", "auto", "confirm"],
        "default": "hybrid",
        "description": "How much autonomy the nightly consolidator gets",
        "docs": (
            "hybrid = auto-apply safe additions, ask about conflicts/sensitive (recommended)  |  "
            "auto   = apply everything silently  |  "
            "confirm = queue every proposal for approval"
        ),
        "required_if": {"CONSOLIDATOR_ENABLED": "true"},
    },
    {
        "key": "CONSOLIDATOR_TIME",
        "label": "Consolidator Time",
        "category": "memory",
        "default": "02:30",
        "description": "When the nightly consolidator runs (HH:MM, 24h)",
        "required_if": {"CONSOLIDATOR_ENABLED": "true"},
    },
    {
        "key": "CONSOLIDATOR_SEND_DIGEST",
        "label": "Send Digest to Telegram",
        "category": "memory",
        "choices": ["true", "false"],
        "default": "true",
        "description": "Post a morning digest showing what was applied/queued",
        "required_if": {"CONSOLIDATOR_ENABLED": "true"},
    },
    {
        "key": "SENSITIVE_CATEGORIES",
        "label": "Sensitive Categories",
        "category": "memory",
        "default": "finances,health,documents",
        "description": "Comma-separated categories that get redacted before leaving the primary agent",
        "docs": (
            "These are never indexed for semantic search, redacted before being "
            "stored in sessions.db, and redacted before the verifier sees them."
        ),
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
        # When the user wants a secondary brain (fallback/verify), we also need the
        # other provider's key+model even if it isn't their primary.
        key = step.get("key", "")
        strategy = config.get("LLM_STRATEGY", "fallback")
        primary = config.get("PRIMARY_LLM", "zai")
        secondary_needed = strategy in ("fallback", "verify")

        if secondary_needed:
            other = "openai" if primary == "zai" else "zai"
            if other == "openai" and key in ("OPENAI_API_KEY", "OPENAI_MODEL"):
                return True
            if other == "zai" and key in ("ZAI_API_KEY", "ZAI_MODEL", "ZAI_BASE_URL"):
                return True

        if "required_if" in step:
            for req_key, req_val in step["required_if"].items():
                if config.get(req_key) == req_val:
                    return True
            return False
        if "required_if_not" in step:
            for req_key, req_val in step["required_if_not"].items():
                if config.get(req_key, step.get("default", "")) != req_val:
                    return True
            return False
        return True

    def show_welcome(self) -> None:
        from moha_mind.cli.banner import _ascii_title

        g = "#00FF87"
        d = "#555555"

        self.console.print()
        self.console.print(_ascii_title())
        self.console.print(f"  [italic {d}]Your Personal Agent  ·  Always On  ·  Always Remembering[/]")
        self.console.print()
        self.console.print(f"  [bold {g}]Setup Wizard[/]")
        self.console.print(f"  [{d}]Settings are saved to[/] [bold].env[/] [{d}](never committed to git)[/]")
        self.console.print(f"  [{d}]Re-run anytime with[/] [bold {g}]mohamind setup[/]")
        self.console.print()

    def show_current_config(self, config: dict[str, str]) -> None:
        if not config:
            return

        g = "#00FF87"
        d = "#555555"

        self.console.print(f"  [bold {g}]Current Configuration[/]\n")

        category_names = {
            "brain": "Brain",
            "telegram": "Telegram",
            "schedule": "Schedule",
            "calendar": "Calendar",
            "memory": "Memory",
        }
        last_category = None

        for step in SETUP_STEPS:
            key = step["key"]
            value = config.get(key, "") or step.get("default", "")
            if not value:
                if step.get("optional") or not self._is_step_needed(step, config):
                    continue

            cat = step["category"]
            if cat != last_category:
                last_category = cat
                self.console.print(f"  [bold {d}]{category_names.get(cat, cat)}[/]")

            if not value:
                self.console.print(f"    [{d}]{step['label']:<24}[/{d}] [yellow]not set[/]")
            elif step.get("secret"):
                self.console.print(f"    [{d}]{step['label']:<24}[/{d}] [bold]{self._mask(value)}[/]")
            else:
                self.console.print(f"    [{d}]{step['label']:<24}[/{d}] [bold]{escape(value)}[/]")

        self.console.print()

    def configure_step(self, step: dict, config: dict[str, str]) -> str:
        key = step["key"]
        current = config.get(key, "")

        if "choices" in step:
            default_val = current or step["default"]
            # Build choice display — escape values so Rich doesn't treat them as markup tags
            choice_parts = []
            for c in step["choices"]:
                if c == default_val:
                    choice_parts.append(f"[bold cyan]{escape(c)}[/bold cyan]")
                else:
                    choice_parts.append(f"[dim]{escape(c)}[/dim]")
            choice_str = "  |  ".join(choice_parts)

            self.console.print(f"\n  [bold]{escape(step['label'])}[/]")
            if step.get("docs"):
                self.console.print(f"  [dim]{step['docs']}[/]")
            elif step.get("description"):
                self.console.print(f"  [dim]{step['description']}[/]")
            self.console.print(f"  Options: {choice_str}")
            if current:
                self.console.print(f"  Current: [green]{escape(current)}[/]")
            value = Prompt.ask(
                "  Choose",
                choices=step["choices"],
                default=default_val,
                console=self.console,
            )
            # Handle "custom" sentinel for model steps
            if value == "custom" and step.get("custom_prompt"):
                value = Prompt.ask(f"  {step['custom_prompt']}", console=self.console)
        elif step.get("secret"):
            self.console.print(f"\n  [bold]{escape(step['label'])}[/]")
            self.console.print(f"  [dim]{step.get('description', '')}[/]")
            if current:
                self.console.print(f"  Current: [green]{self._mask(current)}[/]")
                if Confirm.ask("  Keep current?", default=True, console=self.console):
                    return current
            value = Prompt.ask("  Enter key", password=True, console=self.console)
        else:
            self.console.print(f"\n  [bold]{escape(step['label'])}[/]")
            self.console.print(f"  [dim]{step.get('description', '')}[/]")
            if current:
                self.console.print(f"  Current: [green]{escape(current)}[/]")
            value = Prompt.ask(
                "  Enter value",
                default=current or step.get("default", ""),
                console=self.console,
            )

        return value.strip()

    def save_config(self, config: dict[str, str]) -> None:
        all_keys = {s["key"] for s in SETUP_STEPS}
        all_keys.update(
            {
                "FALLBACK_LLM",
                "SECONDARY_LLM",
                "LLM_STRATEGY",
                "VERIFIER_STRICTNESS",
                "VERIFIER_MAX_RETRIES",
                "ZAI_MODEL",
                "ZAI_BASE_URL",
                "OPENAI_MODEL",
                "OPENAI_BASE_URL",
                "MEMORY_ROUTER_MAX_CATEGORIES",
                "MEMORY_SUMMARY_MODEL",
                "SEMANTIC_TOP_K",
                "PRIVACY_REDACT_SESSIONS",
                "PRIVACY_REDACT_VERIFIER",
                "PRIVACY_REDACT_DAILY_LOG",
            }
        )

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
        self.console.print(f"\n  [bold #00FF87]Saved[/] [dim]→ {ENV_PATH}[/]")

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
            # Use self.config (in-session choices) merged over self.existing for required_if checks
            merged = {**self.existing, **self.config}
            if not self._is_step_needed(step, merged):
                if step.get("optional"):
                    if quick:
                        continue
                    self.console.print(f"\n  [dim]Optional: {step['label']}[/]")
                    if not Confirm.ask("  Configure?", default=False, console=self.console):
                        self.config[step["key"]] = self.existing.get(step["key"], "")
                        continue
                else:
                    self.config[step["key"]] = self.existing.get(step["key"], step.get("default", ""))
                    continue

            if step["category"] != current_category:
                current_category = step["category"]
                category_names = {
                    "brain": "Brain",
                    "telegram": "Telegram",
                    "schedule": "Schedule",
                    "calendar": "Calendar",
                    "memory": "Memory",
                }
                self.console.print(f"\n  [bold #00FF87]▸ {category_names.get(current_category, current_category)}[/]")

            value = self.configure_step(step, {**self.existing, **self.config})
            self.config[step["key"]] = value

        for key, val in self.existing.items():
            if key not in self.config:
                self.config[key] = val

        primary = self.config.get("PRIMARY_LLM", "zai")
        strategy = self.config.get("LLM_STRATEGY", "fallback")
        secondary = "openai" if primary == "zai" else "zai"

        # Legacy compatibility: keep FALLBACK_LLM in sync so older consumers still work.
        if strategy == "solo":
            self.config["FALLBACK_LLM"] = "none"
            self.config["SECONDARY_LLM"] = "none"
        else:
            self.config["FALLBACK_LLM"] = secondary
            self.config["SECONDARY_LLM"] = secondary

        if primary == "zai" and not self.config.get("ZAI_API_KEY"):
            self.config["ZAI_API_KEY"] = ""
        if primary == "openai" and not self.config.get("OPENAI_API_KEY"):
            self.config["OPENAI_API_KEY"] = ""

        self.save_config(self.config)

        self.show_current_config(self.config)

        g = "#00FF87"
        d = "#555555"
        self.console.print(f"  [bold {g}]Setup complete.[/]\n")
        self.console.print(f"  [bold {g}]mohamind[/]          [{d}]interactive CLI[/{d}]")
        self.console.print(f"  [bold {g}]mohamind --bot[/]    [{d}]telegram bot only[/{d}]")
        self.console.print(f"  [bold {g}]mohamind --all[/]    [{d}]CLI + telegram together[/{d}]")
        self.console.print(f"  [bold {g}]mohamind doctor[/]   [{d}]check config health[/{d}]")
        self.console.print()

        return self.config


def run_setup(quick: bool = False) -> dict[str, str]:
    wizard = SetupWizard()
    return wizard.run(quick=quick)


def _mask_key(key: str) -> str:
    """Show first 4 and last 4 characters of a key, mask the rest."""
    if len(key) <= 8:
        return "****" if key else "(not set)"
    return key[:4] + "****" + key[-4:]


def run_doctor() -> bool:
    console = Console()
    g = "#00FF87"
    d = "#555555"

    console.print(f"\n  [bold {g}]mohamind doctor[/]\n")

    env_path = Path(".env")
    has_env = env_path.exists()

    def _row(label: str, ok: bool, detail: str, warn: bool = False) -> None:
        icon = "[green]✓[/]" if ok else ("[yellow]![/]" if warn else "[red]✗[/]")
        console.print(f"    {icon} [{d}]{label:<24}[/{d}] {detail}")

    _row(".env", has_env, str(env_path.resolve()) if has_env else "run mohamind setup")

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
    fallback = env_vars.get("FALLBACK_LLM", os.environ.get("FALLBACK_LLM", ""))
    secondary = env_vars.get("SECONDARY_LLM", os.environ.get("SECONDARY_LLM", ""))
    strategy = env_vars.get("LLM_STRATEGY", os.environ.get("LLM_STRATEGY", "fallback"))
    strictness = env_vars.get("VERIFIER_STRICTNESS", os.environ.get("VERIFIER_STRICTNESS", "balanced"))
    secondary_resolved = secondary or fallback or ("openai" if primary == "zai" else "zai")
    if fallback == "none" or secondary == "none":
        strategy = "solo"

    console.print(f"\n  [bold {d}]Brain[/]")
    _row("provider", True, f"[bold]{primary}[/]  strategy: {strategy}")
    if strategy != "solo":
        role = "verifier" if strategy == "verify" else "fallback"
        _row("secondary", True, f"[bold]{secondary_resolved}[/]  role: {role}")
    if strategy == "verify":
        _row("verifier strictness", True, strictness)

    if primary == "zai":
        _row("z.ai API key", bool(zai_key), _mask_key(zai_key) if zai_key else "run mohamind setup")
        zai_model = env_vars.get("ZAI_MODEL", os.environ.get("ZAI_MODEL", "glm-5-turbo"))
        zai_base = env_vars.get(
            "ZAI_BASE_URL", os.environ.get("ZAI_BASE_URL", "https://api.z.ai/api/paas/v4/"),
        )
        _row("model", True, zai_model)
        _row("base URL", True, zai_base)
    else:
        _row("OpenAI API key", bool(openai_key), _mask_key(openai_key) if openai_key else "run mohamind setup")
        openai_model = env_vars.get("OPENAI_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
        _row("model", True, openai_model)

    if strategy != "solo" and secondary_resolved != primary:
        fb_key = zai_key if secondary_resolved == "zai" else openai_key
        role = "verifier" if strategy == "verify" else "fallback"
        _row(
            f"{secondary_resolved} {role} key",
            bool(fb_key),
            "configured" if fb_key else ("required" if strategy == "verify" else "optional"),
            warn=not fb_key,
        )

    console.print(f"\n  [bold {d}]Telegram[/]")
    _row("bot token", bool(tg_token), "configured" if tg_token else "optional", warn=not tg_token)
    _row("chat ID", bool(tg_chat), tg_chat if tg_chat else "optional", warn=not tg_chat)

    console.print(f"\n  [bold {d}]Calendar[/]")
    google_credentials = Path(
        env_vars.get(
            "GOOGLE_CREDENTIALS_PATH",
            os.environ.get("GOOGLE_CREDENTIALS_PATH", "./credentials/google_credentials.json"),
        )
    )
    google_token = Path(
        env_vars.get("GOOGLE_TOKEN_PATH", os.environ.get("GOOGLE_TOKEN_PATH", "./credentials/google_token.json"))
    )
    ms_client_id = env_vars.get("MS_CLIENT_ID", os.environ.get("MS_CLIENT_ID", ""))
    ms_client_secret = env_vars.get("MS_CLIENT_SECRET", os.environ.get("MS_CLIENT_SECRET", ""))
    _row("Google OAuth client", google_credentials.exists(), str(google_credentials), warn=True)
    _row("Google token", google_token.exists(), str(google_token), warn=True)
    _row("MS client ID", bool(ms_client_id), "configured" if ms_client_id else "optional", warn=not ms_client_id)
    _row(
        "MS client secret",
        bool(ms_client_secret),
        "configured" if ms_client_secret else "device-code mode",
        warn=False,
    )

    console.print(f"\n  [bold {d}]Memory[/]")
    router_on = env_vars.get("MEMORY_ROUTER_ENABLED", os.environ.get("MEMORY_ROUTER_ENABLED", "true")).lower() == "true"
    summaries_on = (
        env_vars.get("MEMORY_SUMMARIES_ENABLED", os.environ.get("MEMORY_SUMMARIES_ENABLED", "true")).lower() == "true"
    )
    embed_backend = env_vars.get("EMBEDDING_BACKEND", os.environ.get("EMBEDDING_BACKEND", "none")).lower()
    cons_on = (
        env_vars.get("CONSOLIDATOR_ENABLED", os.environ.get("CONSOLIDATOR_ENABLED", "false")).lower() == "true"
    )
    cons_mode = env_vars.get("CONSOLIDATOR_MODE", os.environ.get("CONSOLIDATOR_MODE", "hybrid"))
    cons_time = env_vars.get("CONSOLIDATOR_TIME", os.environ.get("CONSOLIDATOR_TIME", "02:30"))
    sensitive = env_vars.get(
        "SENSITIVE_CATEGORIES", os.environ.get("SENSITIVE_CATEGORIES", "finances,health,documents")
    )

    _row("router", router_on, "on" if router_on else "off (legacy full-dump prompt)", warn=not router_on)
    _row("summaries", summaries_on, "on" if summaries_on else "off", warn=not summaries_on)
    _row(
        "semantic search",
        embed_backend != "none",
        f"backend: {embed_backend}" if embed_backend != "none" else "off (FTS5 only)",
        warn=embed_backend == "none",
    )
    if cons_on:
        _row("consolidator", True, f"on  ·  mode: {cons_mode}  ·  time: {cons_time}")
    else:
        _row("consolidator", False, "off", warn=True)
    _row("sensitive", bool(sensitive), sensitive)

    console.print(f"\n  [bold {d}]Storage[/]")
    memory_dir = Path(env_vars.get("MEMORY_DIR", os.environ.get("MEMORY_DIR", "./memory")))
    _row("memory", memory_dir.exists(), str(memory_dir))
    creds_dir = Path("credentials")
    _row("credentials", creds_dir.exists(), str(creds_dir))

    critical_ok = (primary == "zai" and bool(zai_key)) or (primary == "openai" and bool(openai_key))

    console.print()
    if critical_ok:
        console.print(f"  [bold {g}]Ready.[/] [{d}]Type[/] [bold {g}]mohamind[/] [{d}]to start.[/]")
    else:
        console.print(f"  [bold red]Missing API key.[/] [{d}]Run[/] [bold {g}]mohamind setup[/] [{d}]to configure.[/]")
    console.print()

    return critical_ok
