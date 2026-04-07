"""MohaMind - Main entry point.

Starts the Telegram bot, MCP servers, and scheduler all in one process.
"""

import asyncio
import signal
from pathlib import Path

from moha_mind.agent.core import MohaMindAgent
from moha_mind.agent.memory import MemoryManager
from moha_mind.config import settings
from moha_mind.mcp_servers.family.server import FamilyServer
from moha_mind.mcp_servers.life_tracker.server import LifeTrackerServer
from moha_mind.mcp_servers.memory_store.server import MemoryStoreServer
from moha_mind.mcp_servers.social.server import SocialServer
from moha_mind.mcp_servers.tasks.server import TaskServer
from moha_mind.scheduler.jobs import SchedulerJobs
from moha_mind.telegram_bot.bot import MohaMindBot
from moha_mind.utils.logging_config import log


async def bootstrap() -> tuple[MemoryManager, MohaMindAgent, MohaMindBot, SchedulerJobs]:
    """Initialize all MohaMind components."""
    log.info("=" * 50)
    log.info("MohaMind - Personal AI Agent")
    log.info("=" * 50)

    Path(settings.memory_dir).mkdir(parents=True, exist_ok=True)
    Path("credentials").mkdir(exist_ok=True)

    memory = MemoryManager()
    memory.ensure_templates()
    log.info("Memory system initialized")

    agent = MohaMindAgent(memory)

    memory_server = MemoryStoreServer(memory)
    task_server = TaskServer(memory)
    life_server = LifeTrackerServer(memory)
    FamilyServer(memory)
    SocialServer(memory)

    agent.register_tool("save_memory", memory_server._save)
    agent.register_tool("search_memory", memory_server._search)
    agent.register_tool("add_task", task_server._add_task)
    agent.register_tool("complete_task", task_server._complete_task)
    agent.register_tool("list_tasks", task_server._list_tasks)
    agent.register_tool("get_expiring", life_server._get_expiring_items)
    agent.register_tool("append_to_section", memory_server._append_to_section)
    agent.register_tool("save_note", memory_server._save_note)
    agent.register_tool("save_daily_log", memory_server._save_daily_log)

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

    bot = MohaMindBot(agent, memory)
    bot.setup()

    scheduler = SchedulerJobs(agent, memory, bot)

    return memory, agent, bot, scheduler


async def main() -> None:
    """Main async entry point."""
    memory, agent, bot, scheduler = await bootstrap()

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


def run() -> None:
    """Synchronous entry point for uv/pip script."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("MohaMind interrupted by user")


if __name__ == "__main__":
    run()
