"""Telegram bot command and message handlers."""

from telegram import Update
from telegram.ext import ContextTypes

from moha_mind.agent.core import MohaMindAgent
from moha_mind.agent.memory import MemoryManager
from moha_mind.telegram_bot.formatters import truncate_message
from moha_mind.utils.logging_config import log
from moha_mind.utils.timezone import ksa_time_str


class Handlers:
    def __init__(self, agent: MohaMindAgent, memory: MemoryManager):
        self.agent = agent
        self.memory = memory

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        user = update.effective_user
        welcome = (
            f"Assalamu Alaikum {user.first_name}! 👋\n\n"
            f"I'm MohaMind, your personal AI agent.\n"
            f"I remember everything about you and help manage your daily life.\n\n"
            f"Here's what I can do:\n"
            f"📋 /tasks - View your tasks\n"
            f"➕ /add <task> - Add a task\n"
            f"📅 /calendar - Today's schedule\n"
            f"🚗 /car - Vehicle status\n"
            f"💰 /pay - Upcoming bills\n"
            f"👨‍👩‍👧‍👦 /family - Family updates\n"
            f"🔔 /expiry - Expiring items\n"
            f"🧠 /remember <text> - Remember something\n"
            f"🔍 /recall <text> - Search memories and past conversations\n"
            f"🌅 /briefing - Morning briefing\n"
            f"📊 /review - Weekly review\n"
            f"📝 /note <text> - Quick note\n\n"
            f"Or just talk to me - I'll remember everything! 🧠"
        )
        await update.message.reply_text(welcome)

    async def today(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /today command."""
        response = await self.agent.chat(
            "What's on my schedule for today? Show me everything: tasks, calendar, appointments.",
            chat_id=str(update.effective_chat.id),
        )
        for part in truncate_message(response):
            await update.message.reply_text(part)

    async def tomorrow(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /tomorrow command."""
        response = await self.agent.chat(
            "What's on my schedule for tomorrow? Show me tasks, calendar, appointments, and anything important.",
            chat_id=str(update.effective_chat.id),
        )
        for part in truncate_message(response):
            await update.message.reply_text(part)

    async def tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /tasks command."""
        tasks = self.memory.get_task_section()
        active = [t for t in tasks if not t["done"]]
        if not active:
            await update.message.reply_text("No active tasks! You're all caught up 🎉")
            return
        lines = ["📋 Active Tasks:"]
        for i, t in enumerate(active, 1):
            due_info = f" (due {t['due']})" if t["due"] else ""
            priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t["priority"], "⚪")
            lines.append(f"{priority_emoji} {i}. {t['text']}{due_info}")
        await update.message.reply_text("\n".join(lines))

    async def reminders(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /reminders command."""
        from moha_mind.mcp_servers.reminders.server import ReminderServer

        days = 14
        if context.args:
            try:
                days = int(context.args[0])
            except ValueError:
                pass

        server = ReminderServer(self.memory)
        response = await server._list_reminders(days_ahead=days)
        for part in truncate_message(response):
            await update.message.reply_text(part)

    async def remind(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /remind command."""
        if not context.args:
            await update.message.reply_text("Usage: /remind <message with date/time>")
            return
        reminder_text = " ".join(context.args)
        response = await self.agent.chat(
            (
                "Set a timed reminder for this request. "
                "Support colloquial Arabic and Saudi/Gulf dialect naturally. "
                "Convert any relative date/time into an exact Asia/Riyadh datetime and use the reminder tools: "
                f"{reminder_text}"
            ),
            chat_id=str(update.effective_chat.id),
        )
        for part in truncate_message(response):
            await update.message.reply_text(part)

    async def add_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /add command."""
        if not context.args:
            await update.message.reply_text(
                "Usage: /add <task description>\nExample: /add Submit quarterly report [HIGH] due:2026-04-15"
            )
            return
        task_text = " ".join(context.args)
        response = await self.agent.chat(
            f"Add this task: {task_text}",
            chat_id=str(update.effective_chat.id),
        )
        await update.message.reply_text(f"✅ {response}")

    async def done(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /done command."""
        if not context.args:
            tasks = self.memory.get_task_section()
            active = [t for t in tasks if not t["done"]]
            if not active:
                await update.message.reply_text("No active tasks!")
                return
            lines = ["Which task to complete? Reply with the number:"]
            for i, t in enumerate(active, 1):
                lines.append(f"{i}. {t['text']}")
            await update.message.reply_text("\n".join(lines))
            return

        try:
            task_num = int(context.args[0])
            tasks = self.memory.get_task_section()
            active = [t for t in tasks if not t["done"]]
            if 1 <= task_num <= len(active):
                task = active[task_num - 1]
                self.memory.complete_task(task["text"])
                await update.message.reply_text(f"✅ Done: {task['text']}")
            else:
                await update.message.reply_text("Invalid task number")
        except ValueError:
            task_text = " ".join(context.args)
            success = self.memory.complete_task(task_text)
            if success:
                await update.message.reply_text(f"✅ Done: {task_text}")
            else:
                await update.message.reply_text("Task not found. Use /tasks to see task numbers.")

    async def car(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /car command."""
        response = await self.agent.chat(
            "Show me my vehicle status: next service, registration, insurance status.",
            chat_id=str(update.effective_chat.id),
        )
        for part in truncate_message(response):
            await update.message.reply_text(part)

    async def pay(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /pay command."""
        response = await self.agent.chat(
            "What bills and payments are coming up? Show upcoming bills and subscription renewals.",
            chat_id=str(update.effective_chat.id),
        )
        for part in truncate_message(response):
            await update.message.reply_text(part)

    async def health(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /health command."""
        response = await self.agent.chat(
            "Show me my health reminders: medications, upcoming doctor appointments, gym status.",
            chat_id=str(update.effective_chat.id),
        )
        for part in truncate_message(response):
            await update.message.reply_text(part)

    async def family(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /family command."""
        response = await self.agent.chat(
            "Show me family updates: pregnancy status, kids events, upcoming appointments.",
            chat_id=str(update.effective_chat.id),
        )
        for part in truncate_message(response):
            await update.message.reply_text(part)

    async def social(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /social command."""
        response = await self.agent.chat(
            "Who should I reach out to? Check my social pulse.",
            chat_id=str(update.effective_chat.id),
        )
        for part in truncate_message(response):
            await update.message.reply_text(part)

    async def expiry(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /expiry command."""
        days = 90
        if context.args:
            try:
                days = int(context.args[0])
            except ValueError:
                pass
        items = self.memory.get_expiring_items(days)
        if not items:
            await update.message.reply_text(f"Nothing expiring in the next {days} days! 🟢")
            return
        lines = ["🔔 Expiring Items:"]
        for item in items:
            if item["days_left"] <= 7:
                emoji = "🔴"
            elif item["days_left"] <= 30:
                emoji = "🟡"
            else:
                emoji = "🟢"
            lines.append(f"{emoji} [{item['days_left']}d] {item['detail']}")
        for part in truncate_message("\n".join(lines)):
            await update.message.reply_text(part)

    async def remember(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /remember command."""
        if not context.args:
            await update.message.reply_text("Usage: /remember <something to remember>")
            return
        text = " ".join(context.args)
        response = await self.agent.chat(
            f"Remember this and save it to the appropriate memory category: {text}",
            chat_id=str(update.effective_chat.id),
        )
        await update.message.reply_text(f"🧠 {response}")

    async def recall(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /recall command."""
        if not context.args:
            await update.message.reply_text("Usage: /recall <search query>")
            return
        query = " ".join(context.args)
        response = self.agent.recall(query, chat_id=str(update.effective_chat.id))
        for part in truncate_message(response):
            await update.message.reply_text(part)

    async def forget(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /forget command."""
        if not context.args:
            await update.message.reply_text("Usage: /forget <what to forget>")
            return
        text = " ".join(context.args)
        results = self.memory.search(text)
        if not results:
            await update.message.reply_text(f"I don't have anything about '{text}'")
            return
        await update.message.reply_text(f"Found {len(results)} matches. I'll remove the relevant entries.")
        log.info(f"Forget requested: {text} ({len(results)} matches)")

    async def calendar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /calendar command."""
        response = await self.agent.chat(
            "Show me my calendar events for today from Google and Microsoft calendars.",
            chat_id=str(update.effective_chat.id),
        )
        for part in truncate_message(response):
            await update.message.reply_text(part)

    async def shopping(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /shopping command."""
        shopping_data = self.memory.read("shopping")
        if not shopping_data.strip():
            await update.message.reply_text("No shopping list yet! Tell me what you need.")
            return
        for part in truncate_message(shopping_data):
            await update.message.reply_text(part)

    async def briefing(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /briefing command - manual morning briefing."""
        await update.message.reply_text("🌅 Generating your briefing...")
        response = await self.agent.generate_briefing()
        for part in truncate_message(response):
            await update.message.reply_text(part)

    async def review(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /review command - manual weekly review."""
        await update.message.reply_text("📊 Generating your weekly review...")
        response = await self.agent.generate_weekly_review()
        for part in truncate_message(response):
            await update.message.reply_text(part)

    async def note(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /note command."""
        if not context.args:
            await update.message.reply_text("Usage: /note <title>: <content>")
            return
        text = " ".join(context.args)
        if ":" in text:
            title, content = text.split(":", 1)
        else:
            title = f"Note {ksa_time_str()}"
            content = text
        self.memory.save_note(title.strip(), content.strip())
        await update.message.reply_text(f"📝 Note saved: {title.strip()}")

    async def week(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /week command."""
        response = await self.agent.chat(
            "Show me my week overview: all events, tasks with deadlines this week, important dates.",
            chat_id=str(update.effective_chat.id),
        )
        for part in truncate_message(response):
            await update.message.reply_text(part)

    async def radar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /radar command."""
        from moha_mind.mcp_servers.attention.server import AttentionServer

        server = AttentionServer(self.memory)
        response = await server._get_attention_radar(days_ahead=30, limit=8)
        for part in truncate_message(response):
            await update.message.reply_text(part)

    async def message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle regular text messages - the main conversation handler."""
        if not update.message or not update.message.text:
            return
        if update.message.text.startswith("/"):
            return

        user_text = update.message.text
        chat_id = str(update.effective_chat.id)

        try:
            await update.message.chat.send_action("typing")
            response = await self.agent.chat(user_text, chat_id=chat_id)
            for part in truncate_message(response):
                await update.message.reply_text(part)
        except Exception as e:
            log.error(f"Message handler error: {e}")
            await update.message.reply_text("Sorry, I had an error processing that. Please try again.")

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors."""
        log.error(f"Telegram error: {context.error}")
