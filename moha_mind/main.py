"""MohaMind - Main entry point.

Starts the Telegram bot, MCP servers, and scheduler all in one process.
Also supports an interactive CLI mode.

Usage:
    mohamind           Start Telegram bot + scheduler
    mohamind --cli      Interactive CLI mode
    mohamind setup      Run setup wizard
    mohamind doctor     Check configuration health
"""

import asyncio
import signal
import sys
from pathlib import Path

from moha_mind.utils.logging_config import log


def _get_cli_args():
    args = {
        "cli": "--cli" in sys.argv or "-i" in sys.argv,
        "setup": "setup" in sys.argv,
        "doctor": "doctor" in sys.argv,
        "quick_setup": "--quick" in sys.argv,
    }
    return args


def _check_first_run():
    if not Path(".env").exists():
        from rich.console import Console

        console = Console()
        console.print()
        console.print("[bold yellow]⚠️  No .env file found![/]")
        console.print("[dim]It looks like this is your first run.[/]")
        console.print()
        try:
            from rich.prompt import Confirm

            if Confirm.ask("Run setup wizard?", default=True, console=console):
                from moha_mind.cli.setup_wizard import run_setup

                run_setup(quick=False)
                console.print()
            else:
                console.print("[dim]You can run [bold]mohamind setup[/] anytime.[/]")
                console.print()
        except (EOFError, KeyboardInterrupt):
            console.print("[dim]\nRun [bold]mohamind setup[/] to get started.[/]")
            console.print()


async def bootstrap(require_telegram: bool = True):
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

    if require_telegram:
        from moha_mind.telegram_bot.bot import MohaMindBot

        bot = MohaMindBot(agent, memory)
        bot.setup()
        scheduler = SchedulerJobs(agent, memory, bot)

    return memory, agent, bot, scheduler


async def main() -> None:
    from moha_mind.config import settings

    memory, agent, bot, scheduler = await bootstrap(require_telegram=True)

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
    log.info("MohaMind is LIVE!")
    log.info(f"  Timezone: {settings.timezone}")
    log.info(f"  LLM: {settings.primary_llm} ({settings.active_llm_config['model']})")
    log.info(f"  Morning briefing: {settings.morning_briefing_time}")
    log.info(f"  Memory dir: {settings.memory_dir}")
    log.info("=" * 50)

    await shutdown_event.wait()

    log.info("Shutting down MohaMind...")
    scheduler.stop()
    await bot.stop()
    bot_task.cancel()
    try:
        await bot_task
    except asyncio.CancelledError:
        pass
    log.info("MohaMind stopped. Goodbye!")


async def main_cli() -> None:
    memory, agent, bot, scheduler = await bootstrap(require_telegram=False)

    if scheduler:
        scheduler.start()

    from moha_mind.cli.app import MohaMindCLI

    cli = MohaMindCLI(memory, agent)

    bot_task = None
    if bot:
        bot_task = asyncio.create_task(bot.start())

    try:
        await cli.run()
    finally:
        if scheduler:
            scheduler.stop()
        if bot:
            await bot.stop()
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass


def run() -> None:
    args = _get_cli_args()

    if args["setup"]:
        from moha_mind.cli.setup_wizard import run_setup

        run_setup(quick=args["quick_setup"])
        return

    if args["doctor"]:
        from moha_mind.cli.setup_wizard import run_doctor

        run_doctor()
        return

    _check_first_run()

    try:
        if args["cli"]:
            asyncio.run(main_cli())
        else:
            asyncio.run(main())
    except KeyboardInterrupt:
        log.info("MohaMind interrupted by user")


if __name__ == "__main__":
    run()
