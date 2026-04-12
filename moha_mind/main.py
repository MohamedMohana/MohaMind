"""MohaMind - Main entry point.

CLI-first design. Running `mohamind` opens the interactive REPL.

Usage:
    mohamind                Interactive CLI (default)
    mohamind "query"        Start with initial message
    mohamind -p "query"     One-shot mode (print answer, exit)
    mohamind --bot          Start Telegram bot daemon
    mohamind --all          CLI + Telegram bot together
    mohamind setup          Run setup wizard
    mohamind doctor         Check configuration health
"""

import argparse
import asyncio
import signal
import sys
from pathlib import Path

from moha_mind.utils.logging_config import log


def _parse_args():
    parser = argparse.ArgumentParser(
        prog="mohamind",
        description="MohaMind - Your personal AI agent",
    )
    parser.add_argument("prompt", nargs="?", default=None, help="Start with an initial message")
    parser.add_argument("-p", "--print", dest="one_shot", help="One-shot mode: print answer and exit")
    parser.add_argument("-c", "--continue", dest="continue_session", action="store_true", help="Continue last session")
    parser.add_argument("--bot", action="store_true", help="Start Telegram bot daemon (no CLI)")
    parser.add_argument("--all", dest="all_services", action="store_true", help="CLI + Telegram bot together")
    parser.add_argument("--quick", action="store_true", help="Quick setup (skip optional fields)")
    parser.add_argument("command", nargs="?", default=None, help="Subcommand: setup, doctor")

    known, _ = parser.parse_known_args()
    return known


def _has_api_key():
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("ZAI_API_KEY=") and len(line.split("=", 1)[1].strip()) > 5:
                return True
            if line.startswith("OPENAI_API_KEY=") and len(line.split("=", 1)[1].strip()) > 5:
                return True
    for key in ("ZAI_API_KEY", "OPENAI_API_KEY"):
        val = __import__("os").environ.get(key, "")
        if val and len(val) > 5:
            return True
    return False


def _first_run_auth():
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt

    console = Console()

    console.print(
        Panel(
            "[bold]Welcome to MohaMind![/]\n\n"
            "No API key found. Let's get you set up in 30 seconds.\n"
            "Your key is saved to [bold].env[/] (never committed to git).",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    providers = {"1": ("z.ai (GLM-4)", "zai"), "2": ("OpenAI", "openai")}
    console.print("\n  [bold]Choose your AI provider:[/]")
    console.print("  [cyan]1[/] z.ai (GLM-4) - recommended, cost-effective")
    console.print("  [cyan]2[/] OpenAI (GPT-4)")
    choice = Prompt.ask("  Choice", choices=["1", "2"], default="1", console=console)

    provider = providers[choice][1]
    key_name = "z.ai" if provider == "zai" else "OpenAI"
    key_url = "https://open.bigmodel.cn" if provider == "zai" else "https://platform.openai.com/api-keys"
    env_key = "ZAI_API_KEY" if provider == "zai" else "OPENAI_API_KEY"

    console.print(f"\n  Get your key from [bold cyan]{key_url}[/]")
    api_key = Prompt.ask(f"  {key_name} API key", console=console)

    if not api_key.strip():
        console.print("[red]No key provided. Run [bold]mohamind setup[/] when ready.[/]")
        sys.exit(1)

    tz = Prompt.ask("  Your timezone", default="Asia/Riyadh", console=console)

    lines = [
        f"PRIMARY_LLM={provider}",
        f"{env_key}={api_key.strip()}",
        f"FALLBACK_LLM={'openai' if provider == 'zai' else 'zai'}",
        f"TIMEZONE={tz}",
        "MORNING_BRIEFING_TIME=08:00",
    ]
    Path(".env").write_text("\n".join(lines) + "\n")

    console.print(Panel("[bold green]Saved![/] You're ready to go.\n", border_style="green", padding=(0, 2)))

    tg = Confirm.ask("\n  Configure Telegram bot? (optional)", default=False, console=console)
    if tg:
        from moha_mind.cli.setup_wizard import SetupWizard

        wizard = SetupWizard(console)
        wizard.run(quick=True)


async def bootstrap(require_telegram: bool = False):
    from moha_mind.agent.core import MohaMindAgent
    from moha_mind.agent.memory import MemoryManager
    from moha_mind.config import settings
    from moha_mind.mcp_servers.family.server import FamilyServer
    from moha_mind.mcp_servers.life_tracker.server import LifeTrackerServer
    from moha_mind.mcp_servers.memory_store.server import MemoryStoreServer
    from moha_mind.mcp_servers.social.server import SocialServer
    from moha_mind.mcp_servers.tasks.server import TaskServer
    from moha_mind.scheduler.jobs import SchedulerJobs

    log.info("=" * 50)
    log.info("MohaMind - Personal AI Agent")
    log.info("=" * 50)

    Path(settings.memory_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.memory_dir).parent.joinpath("credentials").mkdir(exist_ok=True)

    memory = MemoryManager()
    memory.ensure_templates()
    log.info("Memory system initialized")

    agent = MohaMindAgent(memory)

    memory_server = MemoryStoreServer(memory)
    task_server = TaskServer(memory)
    life_server = LifeTrackerServer(memory)
    family_server = FamilyServer(memory)
    social_server = SocialServer(memory)

    agent.register_tool("save_memory", memory_server._save)
    agent.register_tool("search_memory", memory_server._search)
    agent.register_tool("add_task", task_server._add_task)
    agent.register_tool("complete_task", task_server._complete_task)
    agent.register_tool("list_tasks", task_server._list_tasks)
    agent.register_tool("get_expiring", life_server._get_expiring_items)
    agent.register_tool("append_to_section", memory_server._append_to_section)
    agent.register_tool("save_note", memory_server._save_note)
    agent.register_tool("save_daily_log", memory_server._save_daily_log)
    agent.register_tool("family_add_appointment", family_server._add_appointment)
    agent.register_tool("family_get_upcoming", family_server._get_upcoming)
    agent.register_tool("family_update_pregnancy_week", family_server._update_pregnancy_week)
    agent.register_tool("family_add_kid_event", family_server._add_kid_event)
    agent.register_tool("family_add_vaccination", family_server._add_vaccination)
    agent.register_tool("family_get_vaccination_schedule", family_server._get_vaccination_schedule)
    agent.register_tool("social_add_person", social_server._add_person)
    agent.register_tool("social_log_contact", social_server._log_contact)
    agent.register_tool("social_get_neglected", social_server._get_neglected)
    agent.register_tool("social_add_gift_idea", social_server._add_gift_idea)
    agent.register_tool("social_get_upcoming_birthdays", social_server._get_upcoming_birthdays)

    try:
        from moha_mind.mcp_servers.google_calendar.server import GoogleCalendarServer

        google_cal = GoogleCalendarServer(memory)
        agent.register_tool("get_calendar_events", google_cal._list_events)
        log.info("Google Calendar integration loaded")
    except Exception as e:
        log.warning(f"Google Calendar not available: {e}")

    try:
        from moha_mind.mcp_servers.microsoft_graph.server import MicrosoftGraphServer

        ms_graph = MicrosoftGraphServer(memory)
        agent.register_tool("get_ms_calendar_events", ms_graph._list_calendar_events)
        log.info("Microsoft Graph integration loaded")
    except Exception as e:
        log.warning(f"Microsoft Graph not available: {e}")

    log.info("All MCP servers registered")

    bot = None
    scheduler = None

    if require_telegram and settings.telegram_bot_token:
        from moha_mind.telegram_bot.bot import MohaMindBot

        bot = MohaMindBot(agent, memory)
        bot.setup()
        scheduler = SchedulerJobs(agent, memory, bot)

    return memory, agent, bot, scheduler


async def run_bot_only() -> None:
    from moha_mind.config import settings

    memory, agent, bot, scheduler = await bootstrap(require_telegram=True)
    if not bot:
        print("Error: TELEGRAM_BOT_TOKEN not configured. Run: mohamind setup")
        return

    scheduler.start()
    log.info("Scheduler started")

    shutdown_event = asyncio.Event()

    def signal_handler(sig, frame):
        log.info("Shutdown signal received...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    log.info("Starting MohaMind Telegram bot...")
    bot_task = asyncio.create_task(bot.start())

    log.info("=" * 50)
    log.info("MohaMind Bot is LIVE!")
    log.info(f"  Timezone: {settings.timezone}")
    log.info(f"  LLM: {settings.primary_llm} ({settings.active_llm_config['model']})")
    log.info(f"  Morning briefing: {settings.morning_briefing_time}")
    log.info("=" * 50)

    await shutdown_event.wait()

    log.info("Shutting down...")
    scheduler.stop()
    await bot.stop()
    bot_task.cancel()
    try:
        await bot_task
    except asyncio.CancelledError:
        pass
    log.info("MohaMind stopped. Goodbye!")


async def run_cli(with_bot: bool = False, initial_prompt: str | None = None) -> None:
    memory, agent, bot, scheduler = await bootstrap(require_telegram=with_bot)

    if with_bot and scheduler:
        scheduler.start()

    from moha_mind.cli.app import MohaMindCLI

    cli = MohaMindCLI(memory, agent)

    bot_task = None
    if with_bot and bot:
        bot_task = asyncio.create_task(bot.start())

    try:
        if initial_prompt:
            await cli._process_message(initial_prompt)
            cli._show_status()

        await cli.run()
    finally:
        if scheduler:
            scheduler.stop()
        if bot:
            await bot.stop()
            if bot_task:
                bot_task.cancel()
                try:
                    await bot_task
                except asyncio.CancelledError:
                    pass


async def run_one_shot(prompt: str) -> None:
    memory, agent, bot, scheduler = await bootstrap(require_telegram=False)
    response = await agent.chat(prompt, chat_id="one-shot")
    print(response)


def run() -> None:
    args = _parse_args()

    if "setup" in sys.argv:
        from moha_mind.cli.setup_wizard import run_setup

        run_setup(quick="--quick" in sys.argv)
        return

    if "doctor" in sys.argv:
        from moha_mind.cli.setup_wizard import run_doctor

        run_doctor()
        return

    if not _has_api_key():
        try:
            _first_run_auth()
        except (EOFError, KeyboardInterrupt):
            print("\nRun: mohamind setup")
            sys.exit(0)

    try:
        if args.bot:
            asyncio.run(run_bot_only())
        elif args.one_shot:
            asyncio.run(run_one_shot(args.one_shot))
        elif args.all_services:
            asyncio.run(run_cli(with_bot=True, initial_prompt=args.prompt))
        else:
            asyncio.run(run_cli(with_bot=False, initial_prompt=args.prompt))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
