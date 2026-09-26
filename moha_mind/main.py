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

from moha_mind.utils.logging_config import configure_logging, log


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
    parser.add_argument("--schedule", action="store_true", help="Enable scheduled notifications in WhatsApp mode")
    parser.add_argument("--minutes", type=int, default=60, help="Focus/demo time budget, 5–480 minutes")
    parser.add_argument("--energy", choices=["low", "neutral", "high"], default="neutral", help="Focus/demo energy")
    parser.add_argument("--json", action="store_true", help="Print focus/demo as JSON")
    parser.add_argument(
        "command", nargs="?", default=None, help="Subcommand: setup, doctor, focus, demo, whatsapp [setup]"
    )

    known, _ = parser.parse_known_args()
    return known


def _has_api_key():
    from moha_mind.cli.setup_wizard import SetupWizard, is_configured_key

    config = SetupWizard()._load_existing()
    return any(is_configured_key(config.get(key, "")) for key in ("ZAI_API_KEY", "OPENAI_API_KEY"))


def _first_run_auth():
    from moha_mind.cli.setup_wizard import run_setup
    from moha_mind.config import Settings, settings

    run_setup(quick=True)
    updated = Settings()
    for name in Settings.model_fields:
        setattr(settings, name, getattr(updated, name))


async def bootstrap(require_telegram: bool = False):
    from moha_mind.agent.core import MohaMindAgent
    from moha_mind.agent.focus import FocusPlanner
    from moha_mind.agent.memory import MemoryManager
    from moha_mind.config import settings
    from moha_mind.mcp_servers.attention.server import AttentionServer
    from moha_mind.mcp_servers.family.server import FamilyServer
    from moha_mind.mcp_servers.life_tracker.server import LifeTrackerServer
    from moha_mind.mcp_servers.memory_store.server import MemoryStoreServer
    from moha_mind.mcp_servers.reminders.server import ReminderServer
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
    attention_server = AttentionServer(memory)
    reminder_server = ReminderServer(memory)

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
    agent.register_tool("add_reminder", reminder_server._add_reminder)
    agent.register_tool("list_reminders", reminder_server._list_reminders)
    agent.register_tool("complete_reminder", reminder_server._complete_reminder)
    agent.register_tool("get_attention_radar", attention_server._get_attention_radar)
    agent.register_tool("get_focus_plan", FocusPlanner(memory).get_focus_plan)

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

    try:
        from moha_mind.mcp_servers.external import ExternalMCPManager

        external_mcp = ExternalMCPManager.from_config(settings.mcp_servers_config)
        if external_mcp.configs:
            await external_mcp.connect_all()
            count = external_mcp.register_into(agent)
            log.info(f"External MCP servers: {len(external_mcp.connections)} configured, {count} tools registered")
        agent.external_mcp = external_mcp
    except Exception as e:
        log.warning(f"External MCP servers not available: {e}")

    log.info("All MCP servers registered")

    bot = None
    scheduler = None

    if require_telegram and settings.telegram_bot_token:
        from moha_mind.telegram_bot.bot import MohaMindBot

        bot = MohaMindBot(agent, memory)
        bot.setup()
        scheduler = SchedulerJobs(agent, memory, bot)
        bot.handlers.attach_consolidator(scheduler.memory_consolidator)

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
    if agent.external_mcp:
        await agent.external_mcp.aclose()
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
        if agent.external_mcp:
            await agent.external_mcp.aclose()


async def run_one_shot(prompt: str) -> None:
    memory, agent, bot, scheduler = await bootstrap(require_telegram=False)
    try:
        response = await agent.chat(prompt, chat_id="one-shot")
        print(response)
    finally:
        if agent.external_mcp:
            await agent.external_mcp.aclose()


def run() -> None:
    args = _parse_args()

    command = args.prompt if not (args.one_shot is not None or args.bot or args.all_services) else None

    if args.schedule and command != "whatsapp":
        print("Use --schedule with: uv run mohamind whatsapp --schedule", file=sys.stderr)
        sys.exit(2)

    if command == "whatsapp":
        if args.command not in (None, "setup"):
            print("Usage: mohamind whatsapp [setup] [--schedule]", file=sys.stderr)
            sys.exit(2)
        if args.command == "setup":
            from moha_mind.whatsapp_bot.bot import run_whatsapp

            configure_logging("quiet")
            try:
                asyncio.run(run_whatsapp(pair=True))
            except KeyboardInterrupt:
                pass
            except (RuntimeError, OSError) as exc:
                print(str(exc), file=sys.stderr)
                sys.exit(1)
            return

    if command in {"focus", "demo"}:
        from pydantic import ValidationError

        from moha_mind.agent.focus import FocusRequest
        from moha_mind.cli.focus import run_focus

        try:
            request = FocusRequest(minutes=args.minutes, energy=args.energy)
        except ValidationError:
            print("Focus budget must be between 5 and 480 minutes.", file=sys.stderr)
            sys.exit(2)
        asyncio.run(run_focus(request, demo=command == "demo", as_json=args.json))
        return

    if command == "setup":
        from moha_mind.cli.setup_wizard import run_setup

        try:
            run_setup(quick=args.quick)
        except (EOFError, KeyboardInterrupt):
            print("\nSetup cancelled. Run: uv run mohamind setup --quick")
            sys.exit(1)
        return

    if command == "doctor":
        from moha_mind.cli.setup_wizard import run_doctor

        if not run_doctor():
            sys.exit(1)
        return

    if not _has_api_key():
        if not sys.stdin.isatty() or args.bot or args.one_shot is not None:
            print(
                "No API key configured. Run: uv run mohamind setup --quick\n"
                "To try MohaMind without a key: uv run mohamind demo",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            _first_run_auth()
        except (EOFError, KeyboardInterrupt):
            print("\nSetup cancelled. Run: uv run mohamind setup --quick")
            sys.exit(1)

    try:
        if command == "whatsapp":
            from moha_mind.whatsapp_bot.bot import run_whatsapp

            configure_logging("quiet")
            try:
                asyncio.run(run_whatsapp(schedule=args.schedule))
            except (RuntimeError, OSError) as exc:
                print(str(exc), file=sys.stderr)
                sys.exit(1)
        elif args.bot:
            # Daemon: console for systemd/docker capture, plus the log file.
            configure_logging("daemon")
            asyncio.run(run_bot_only())
        elif args.one_shot:
            # One-shot: stdout is the answer, logs go to the file.
            configure_logging("quiet")
            asyncio.run(run_one_shot(args.one_shot))
        elif args.all_services:
            # Interactive CLI owns the terminal; logs go to the file.
            configure_logging("cli")
            asyncio.run(run_cli(with_bot=True, initial_prompt=args.prompt))
        else:
            configure_logging("cli")
            asyncio.run(run_cli(with_bot=False, initial_prompt=args.prompt))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
