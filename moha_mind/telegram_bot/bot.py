"""Telegram bot setup and lifecycle management."""

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

from moha_mind.agent.core import MohaMindAgent
from moha_mind.agent.memory import MemoryManager
from moha_mind.config import settings
from moha_mind.telegram_bot.formatters import format_telegram_html
from moha_mind.telegram_bot.handlers import Handlers
from moha_mind.utils.logging_config import log


class MohaMindBot:
    def __init__(self, agent: MohaMindAgent, memory: MemoryManager):
        self.agent = agent
        self.memory = memory
        self.handlers = Handlers(agent, memory)
        self.app: Application | None = None

    def setup(self) -> Application:
        """Create and configure the Telegram bot application."""
        if not settings.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")

        self.app = Application.builder().token(settings.telegram_bot_token).build()

        self._register_handlers()
        return self.app

    def _register_handlers(self) -> None:
        """Register all command and message handlers."""
        app = self.app

        # Owner lock: runs in group -1, before every other handler, and drops
        # updates from anyone not allowed via TELEGRAM_CHAT_ID /
        # TELEGRAM_ALLOWED_USER_IDS.
        app.add_handler(TypeHandler(Update, self.handlers.guard), group=-1)

        app.add_handler(CommandHandler("start", self.handlers.start))
        app.add_handler(CommandHandler("help", self.handlers.help))
        app.add_handler(CommandHandler("status", self.handlers.status))
        app.add_handler(CommandHandler("today", self.handlers.today))
        app.add_handler(CommandHandler("tomorrow", self.handlers.tomorrow))
        app.add_handler(CommandHandler("week", self.handlers.week))
        app.add_handler(CommandHandler("tasks", self.handlers.tasks))
        app.add_handler(CommandHandler("reminders", self.handlers.reminders))
        app.add_handler(CommandHandler("remind", self.handlers.remind))
        app.add_handler(CommandHandler("add", self.handlers.add_task))
        app.add_handler(CommandHandler("done", self.handlers.done))
        app.add_handler(CommandHandler("untask", self.handlers.untask))
        app.add_handler(CommandHandler("car", self.handlers.car))
        app.add_handler(CommandHandler("pay", self.handlers.pay))
        app.add_handler(CommandHandler("health", self.handlers.health))
        app.add_handler(CommandHandler("family", self.handlers.family))
        app.add_handler(CommandHandler("social", self.handlers.social))
        app.add_handler(CommandHandler("expiry", self.handlers.expiry))
        app.add_handler(CommandHandler("remember", self.handlers.remember))
        app.add_handler(CommandHandler("recall", self.handlers.recall))
        app.add_handler(CommandHandler("forget", self.handlers.forget))
        app.add_handler(CommandHandler("memory", self.handlers.memory_overview))
        app.add_handler(CommandHandler("show", self.handlers.show_memory))
        app.add_handler(CommandHandler("notes", self.handlers.notes_list))
        app.add_handler(CommandHandler("note", self.handlers.note))
        app.add_handler(CommandHandler("read_note", self.handlers.read_note))
        app.add_handler(CommandHandler("delete_note", self.handlers.delete_note))
        app.add_handler(CommandHandler("calendar", self.handlers.calendar))
        app.add_handler(CommandHandler("shopping", self.handlers.shopping))
        app.add_handler(CommandHandler("briefing", self.handlers.briefing))
        app.add_handler(CommandHandler("review", self.handlers.review))
        app.add_handler(CommandHandler("radar", self.handlers.radar))
        app.add_handler(CommandHandler("undo", self.handlers.undo))
        app.add_handler(CommandHandler("why", self.handlers.why))
        app.add_handler(CommandHandler("consolidate", self.handlers.consolidate))
        app.add_handler(CommandHandler("pending", self.handlers.pending))

        app.add_handler(CallbackQueryHandler(self.handlers.on_callback))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlers.message))

        app.add_error_handler(self.handlers.error_handler)
        log.info("All Telegram handlers registered")

    async def start(self) -> None:
        """Start the bot in polling mode."""
        if not self.app:
            self.setup()

        log.info("Starting MohaMind Telegram bot...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
        )
        log.info("MohaMind bot is running!")

    async def stop(self) -> None:
        """Stop the bot gracefully."""
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            log.info("MohaMind bot stopped")

    async def send_message(self, text: str, chat_id: str | None = None) -> None:
        """Send a proactive message (used by scheduler)."""
        target_chat = chat_id or settings.telegram_chat_id
        if not text or not text.strip():
            log.warning("Skipped empty Telegram message")
            return
        if not target_chat or not self.app:
            log.warning("Cannot send message: no chat_id or app not initialized")
            return
        try:
            await self.app.bot.send_message(
                chat_id=target_chat,
                text=format_telegram_html(text),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            try:
                await self.app.bot.send_message(chat_id=target_chat, text=text)
            except Exception as e:
                log.error(f"Failed to send message: {e}")
