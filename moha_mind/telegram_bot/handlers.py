"""Telegram bot command and message handlers."""

from __future__ import annotations

import time
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

from moha_mind.agent.core import MohaMindAgent
from moha_mind.agent.memory import MEMORY_FILES, MemoryManager
from moha_mind.config import settings
from moha_mind.telegram_bot.formatters import reply_markdown, truncate_message
from moha_mind.utils.i18n import agent_language, t
from moha_mind.utils.logging_config import log
from moha_mind.utils.timezone import ksa_time_str

LTR = "\u200e"

PENDING_ACTION_TTL_SECONDS = 5 * 60


def command(name: str) -> str:
    return f"{LTR}/{name}"


def agent_request(request: str) -> str:
    """Prepend the AGENT_LANGUAGE reply instruction to a command request."""
    return f"{t('agent.instruction')}\n\n{request}"


def arabic_days_phrase(days: int) -> str:
    if days == 0:
        return "اليوم"
    if days == 1:
        return "غدًا"
    if days == 2:
        return "بعد يومين"
    if 3 <= days <= 10:
        return f"بعد {days} أيام"
    return f"بعد {days} يومًا"


class Handlers:
    def __init__(self, agent: MohaMindAgent, memory: MemoryManager):
        self.agent = agent
        self.memory = memory
        # Short-lived store for pending destructive confirmations (keyed by token).
        self._pending_actions: dict[str, dict[str, Any]] = {}
        # Chats already told they are not allowed, so strangers can't spam replies.
        self._denied_chats: set[str] = set()
        # Injected later by the app bootstrap so /consolidate, /pending work.
        self.consolidator = None

    def attach_consolidator(self, consolidator) -> None:
        self.consolidator = consolidator

    async def _reply(self, update: Update, text: str) -> None:
        if update.message:
            await reply_markdown(update.message, text)

    def _remember_action(self, chat_id: str, action: dict[str, Any]) -> str:
        """Store a destructive action for later confirmation. Returns a token."""
        self._purge_expired_actions()
        token = f"{chat_id}-{int(time.time() * 1000)}"
        self._pending_actions[token] = {
            "chat_id": chat_id,
            "created_at": time.time(),
            **action,
        }
        return token

    def _pop_action(self, token: str) -> dict[str, Any] | None:
        action = self._pending_actions.pop(token, None)
        if not action:
            return None
        if time.time() - action["created_at"] > PENDING_ACTION_TTL_SECONDS:
            return None
        return action

    def _purge_expired_actions(self) -> None:
        cutoff = time.time() - PENDING_ACTION_TTL_SECONDS
        stale = [k for k, v in self._pending_actions.items() if v["created_at"] < cutoff]
        for key in stale:
            self._pending_actions.pop(key, None)

    async def guard(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Owner lock — refuse updates from anyone not explicitly allowed.

        Registered in group -1 so it runs before every other handler (commands,
        messages, and inline-keyboard callbacks alike). Memory holds personal
        data, so an unknown Telegram user must never reach the agent.
        """
        allowed = settings.telegram_allowed_ids
        candidates = {
            str(update.effective_user.id) if update.effective_user else "",
            str(update.effective_chat.id) if update.effective_chat else "",
        }
        candidates.discard("")

        if allowed and candidates & allowed:
            return

        query = update.callback_query
        if query:
            try:
                await query.answer()
            except Exception:
                pass

        chat_id = str(update.effective_chat.id) if update.effective_chat else ""
        user_id = str(update.effective_user.id) if update.effective_user else "?"
        log.warning(f"Refused unauthorized Telegram update (user={user_id}, chat={chat_id or '?'})")

        if update.message and chat_id:
            if not allowed:
                # Bot not configured yet — help the owner finish setup.
                await update.message.reply_text(
                    "🔒 MohaMind is locked until its owner finishes setup.\n"
                    f"If this bot is yours, set TELEGRAM_CHAT_ID={chat_id} in .env and restart.\n\n"
                    "🔒 هذا مساعد شخصي خاص ولم يكتمل إعداده بعد.\n"
                    f"إذا كان هذا البوت لك، ضع TELEGRAM_CHAT_ID={chat_id} في ملف ‎.env‎ ثم أعد التشغيل."
                )
            elif chat_id not in self._denied_chats:
                if len(self._denied_chats) > 500:
                    self._denied_chats.clear()
                self._denied_chats.add(chat_id)
                await update.message.reply_text(
                    "🔒 This is a private personal assistant. Access is restricted to its owner.\n"
                    "🔒 هذا مساعد شخصي خاص، والوصول مقصور على صاحبه."
                )

        raise ApplicationHandlerStop

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        user = update.effective_user
        greeting = f"السلام عليكم يا {user.first_name} 👋" if user and user.first_name else "السلام عليكم 👋"
        welcome = (
            f"{greeting}\n\n"
            f"أنا MohaMind، مساعدك الشخصي.\n"
            f"أساعدك في تنظيم يومك ومتابعة مهامك، مواعيدك، العائلة، التذكيرات، وما يحتاج انتباهك.\n\n"
            f"اكتب {command('help')} لعرض جميع الأوامر، أو كلّمني بشكل طبيعي وسأرتّب المعلومات بنفسي."
        )
        await self._reply(update, welcome)

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command — list all available commands."""
        sections = [
            ("📅 المهام والتذكير", [
                f"{command('today')} — جدول اليوم",
                f"{command('tomorrow')} — جدول الغد",
                f"{command('week')} — نظرة على الأسبوع",
                f"{command('tasks')} — المهام النشطة",
                f"{command('add')} <نص> — أضف مهمة",
                f"{command('done')} [رقم] — أنهِ مهمة",
                f"{command('untask')} <رقم> — احذف مهمة",
                f"{command('remind')} <نص> — أنشئ تذكيرًا",
                f"{command('reminders')} [أيام] — التذكيرات القادمة",
            ]),
            ("🧠 الذاكرة", [
                f"{command('remember')} <نص> — احفظ معلومة",
                f"{command('recall')} <نص> — ابحث في الذاكرة والمحادثات",
                f"{command('memory')} — اعرض تصنيفات الذاكرة",
                f"{command('show')} <تصنيف> — اعرض محتوى تصنيف",
                f"{command('forget')} <نص> — احذف معلومة (مع تأكيد)",
                f"{command('notes')} — قائمة الملاحظات",
                f"{command('note')} <عنوان>: <محتوى> — أضف ملاحظة",
                f"{command('read_note')} <عنوان> — اقرأ ملاحظة",
                f"{command('delete_note')} <عنوان> — احذف ملاحظة",
            ]),
            ("🏠 الحياة اليومية", [
                f"{command('calendar')} — التقويم",
                f"{command('car')} — السيارة",
                f"{command('pay')} — المدفوعات",
                f"{command('health')} — الصحة",
                f"{command('family')} — العائلة",
                f"{command('social')} — التواصل",
                f"{command('expiry')} [أيام] — العناصر القريبة من الانتهاء",
                f"{command('shopping')} — قائمة المشتريات",
                f"{command('radar')} — رادار الانتباه",
            ]),
            ("📊 الملخصات", [
                f"{command('briefing')} — ملخص الصباح",
                f"{command('review')} — المراجعة الأسبوعية",
                f"{command('status')} — حالة النظام",
            ]),
        ]
        lines = []
        for title, items in sections:
            lines.append(f"*{title}*")
            lines.extend(items)
            lines.append("")
        lines.append("اكتب لي بشكل طبيعي وسأرتّب المعلومة في مكانها الصحيح.")
        await self._reply(update, "\n".join(lines).strip())

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status — quick system state."""
        strategy = settings.effective_strategy
        strategy_ar = {"solo": "بدون مساعد", "fallback": "احتياطي", "verify": "مراجع"}.get(strategy, strategy)

        active_tasks = [t for t in self.memory.get_task_section() if not t["done"]]
        expiring = self.memory.get_expiring_items(30)

        verifier = self.agent.verifier
        lines = [
            f"🧠 *المزوّد الأساسي:* {self.agent.provider} ({self.agent.model})",
            f"⚙️ *الوضع:* {strategy_ar}",
        ]
        if verifier:
            lines.append(f"🧐 *المراجع:* {verifier.provider} ({verifier.model})")
        lines.extend(
            [
                f"📋 *مهام نشطة:* {len(active_tasks)}",
                f"⏰ *ينتهي خلال 30 يومًا:* {len(expiring)}",
                f"🕐 {ksa_time_str()}",
            ]
        )
        await self._reply(update, "\n".join(lines))

    async def today(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /today command."""
        response = await self.agent.chat(
            agent_request(t("req.today")),
            chat_id=str(update.effective_chat.id),
        )
        for part in truncate_message(response):
            await self._reply(update, part)

    async def tomorrow(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /tomorrow command."""
        response = await self.agent.chat(
            agent_request(t("req.tomorrow")),
            chat_id=str(update.effective_chat.id),
        )
        for part in truncate_message(response):
            await self._reply(update, part)

    async def tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /tasks command."""
        tasks = self.memory.get_task_section()
        active = [t for t in tasks if not t["done"]]
        if not active:
            await self._reply(update, "لا توجد مهام نشطة الآن. أمورك مرتبة 🎉")
            return
        lines = ["📋 المهام النشطة:"]
        for i, task in enumerate(active, 1):
            due_info = f" (الموعد: {LTR}{task['due']})" if task["due"] else ""
            priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(task["priority"], "⚪")
            lines.append(f"{priority_emoji} {i}. {task['text']}{due_info}")
        await self._reply(update, "\n".join(lines))

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
        response = await server._list_reminders(days_ahead=days, language=agent_language())
        for part in truncate_message(response):
            await self._reply(update, part)

    async def remind(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /remind command."""
        if not context.args:
            await self._reply(update, f"الاستخدام: {command('remind')} <النص مع التاريخ أو الوقت>")
            return
        reminder_text = " ".join(context.args)
        response = await self.agent.chat(
            agent_request(t("req.remind", tz=settings.timezone, text=reminder_text)),
            chat_id=str(update.effective_chat.id),
        )
        for part in truncate_message(response):
            await self._reply(update, part)

    async def add_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /add command."""
        if not context.args:
            await self._reply(
                update,
                f"الاستخدام: {command('add')} <وصف المهمة>\n"
                f"مثال: {command('add')} إرسال التقرير الربع سنوي [HIGH] due:2026-04-15",
            )
            return
        task_text = " ".join(context.args)
        response = await self.agent.chat(
            agent_request(t("req.add_task", text=task_text)),
            chat_id=str(update.effective_chat.id),
        )
        await self._reply(update, f"✅ {response}")

    async def done(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /done command."""
        if not context.args:
            tasks = self.memory.get_task_section()
            active = [t for t in tasks if not t["done"]]
            if not active:
                await self._reply(update, "لا توجد مهام نشطة الآن.")
                return
            lines = ["أي مهمة تريد إكمالها؟ أرسل رقم المهمة:"]
            for i, t in enumerate(active, 1):
                lines.append(f"{i}. {t['text']}")
            await self._reply(update, "\n".join(lines))
            return

        try:
            task_num = int(context.args[0])
            tasks = self.memory.get_task_section()
            active = [t for t in tasks if not t["done"]]
            if 1 <= task_num <= len(active):
                task = active[task_num - 1]
                self.memory.complete_task(task["text"])
                await self._reply(update, f"✅ تم: {task['text']}")
            else:
                await self._reply(update, "رقم المهمة غير صحيح.")
        except ValueError:
            task_text = " ".join(context.args)
            success = self.memory.complete_task(task_text)
            if success:
                await self._reply(update, f"✅ تم: {task_text}")
            else:
                await self._reply(update, f"لم أجد المهمة. استخدم {command('tasks')} لرؤية أرقام المهام.")

    async def car(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /car command."""
        response = await self.agent.chat(
            agent_request(t("req.car")),
            chat_id=str(update.effective_chat.id),
        )
        for part in truncate_message(response):
            await self._reply(update, part)

    async def pay(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /pay command."""
        response = await self.agent.chat(
            agent_request(t("req.pay")),
            chat_id=str(update.effective_chat.id),
        )
        for part in truncate_message(response):
            await self._reply(update, part)

    async def health(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /health command."""
        response = await self.agent.chat(
            agent_request(t("req.health")),
            chat_id=str(update.effective_chat.id),
        )
        for part in truncate_message(response):
            await self._reply(update, part)

    async def family(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /family command."""
        response = await self.agent.chat(
            agent_request(t("req.family")),
            chat_id=str(update.effective_chat.id),
        )
        for part in truncate_message(response):
            await self._reply(update, part)

    async def social(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /social command."""
        response = await self.agent.chat(
            agent_request(t("req.social")),
            chat_id=str(update.effective_chat.id),
        )
        for part in truncate_message(response):
            await self._reply(update, part)

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
            await self._reply(update, f"لا يوجد شيء ينتهي خلال {days} يومًا القادمة 🟢")
            return
        lines = ["🔔 عناصر قريبة من الانتهاء:"]
        for item in items:
            if item["days_left"] <= 7:
                emoji = "🔴"
            elif item["days_left"] <= 30:
                emoji = "🟡"
            else:
                emoji = "🟢"
            lines.append(f"{emoji} [{arabic_days_phrase(item['days_left'])}] {item['detail']}")
        for part in truncate_message("\n".join(lines)):
            await self._reply(update, part)

    async def remember(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /remember command."""
        if not context.args:
            await self._reply(update, f"الاستخدام: {command('remember')} <المعلومة التي تريد حفظها>")
            return
        text = " ".join(context.args)
        response = await self.agent.chat(
            agent_request(t("req.remember", text=text)),
            chat_id=str(update.effective_chat.id),
        )
        await self._reply(update, f"🧠 {response}")

    async def recall(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /recall command."""
        if not context.args:
            await self._reply(update, f"الاستخدام: {command('recall')} <كلمات البحث>")
            return
        query = " ".join(context.args)
        response = self.agent.recall(query, chat_id=str(update.effective_chat.id), language="ar")
        for part in truncate_message(response):
            await self._reply(update, part)

    async def forget(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /forget command — delete matching memory with confirmation."""
        if not settings.telegram_allow_destructive:
            await self._reply(update, "حذف المعلومات معطّل في هذا الإعداد.")
            return

        if not context.args:
            await self._reply(
                update,
                f"الاستخدام: {command('forget')} <نص للبحث>\n"
                f"أو: {command('forget')} <تصنيف> <نص>  (لتقييد الحذف بتصنيف مثل tasks أو finances)",
            )
            return

        args = list(context.args)
        category_filter: str | None = None
        if len(args) >= 2 and args[0] in MEMORY_FILES:
            category_filter = args[0]
            query = " ".join(args[1:])
        else:
            query = " ".join(args)

        results = self.memory.search(query, categories=[category_filter] if category_filter else None)
        actionable = [
            r for r in results
            if r["matched_line"].strip()
            and not r["matched_line"].strip().startswith("#")
            and not r["matched_line"].strip().startswith("<!--")
        ]

        if not actionable:
            await self._reply(update, f"لا توجد لدي معلومات عن: «{query}»")
            return

        preview_lines = [f"سأحذف {len(actionable)} سطرًا من الذاكرة:"]
        for result in actionable[:8]:
            snippet = result["matched_line"].strip()
            if len(snippet) > 100:
                snippet = snippet[:97] + "..."
            preview_lines.append(f"- [{result['category']}] {snippet}")
        if len(actionable) > 8:
            preview_lines.append(f"... و{len(actionable) - 8} أخرى")
        preview_lines.append("\nهل أنت متأكد؟")

        chat_id = str(update.effective_chat.id)
        token = self._remember_action(
            chat_id,
            {
                "kind": "forget",
                "query": query,
                "category": category_filter,
                "count": len(actionable),
            },
        )

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ احذف", callback_data=f"confirm:{token}"),
                    InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel:{token}"),
                ]
            ]
        )
        if update.message:
            await update.message.reply_text("\n".join(preview_lines), reply_markup=keyboard)

    async def memory_overview(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /memory — list memory categories with size and preview."""
        lines = ["🧠 *تصنيفات الذاكرة*"]
        for category in MEMORY_FILES.keys():
            content = self.memory.read(category)
            size = len(content)
            if size == 0:
                lines.append(f"• `{category}` — فارغ")
            else:
                lines_count = sum(
                    1
                    for ln in content.split("\n")
                    if ln.strip() and not ln.strip().startswith("#") and not ln.strip().startswith("<!--")
                )
                lines.append(f"• `{category}` — {lines_count} سطر، {size} حرف")
        lines.append(f"\nاستخدم {command('show')} <تصنيف> لعرض المحتوى.")
        await self._reply(update, "\n".join(lines))

    async def show_memory(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /show <category> — show the content of a memory category."""
        if not context.args:
            available = ", ".join(MEMORY_FILES.keys())
            await self._reply(update, f"الاستخدام: {command('show')} <تصنيف>\nالتصنيفات: {available}")
            return
        category = context.args[0].lower().strip()
        if category not in MEMORY_FILES:
            await self._reply(update, f"تصنيف غير معروف: «{category}»")
            return
        content = self.memory.read(category)
        if not content.strip():
            await self._reply(update, f"التصنيف «{category}» فارغ.")
            return
        for part in truncate_message(content):
            await self._reply(update, part)

    async def notes_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /notes — list all saved notes."""
        notes = self.memory.list_notes()
        if not notes:
            await self._reply(update, "لا توجد ملاحظات محفوظة بعد.")
            return
        lines = ["📝 *الملاحظات المحفوظة:*"]
        for note in notes:
            lines.append(f"• {note}")
        lines.append(f"\nاستخدم {command('read_note')} <عنوان> لفتح ملاحظة.")
        await self._reply(update, "\n".join(lines))

    async def read_note(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /read_note <title>."""
        if not context.args:
            await self._reply(update, f"الاستخدام: {command('read_note')} <عنوان الملاحظة>")
            return
        title = " ".join(context.args)
        content = self.memory.read_note(title)
        if not content:
            await self._reply(update, f"لم أجد ملاحظة باسم: «{title}»")
            return
        for part in truncate_message(content):
            await self._reply(update, part)

    async def delete_note(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /delete_note <title> — delete with confirmation."""
        if not settings.telegram_allow_destructive:
            await self._reply(update, "حذف المعلومات معطّل في هذا الإعداد.")
            return
        if not context.args:
            await self._reply(update, f"الاستخدام: {command('delete_note')} <عنوان الملاحظة>")
            return
        title = " ".join(context.args)
        if not self.memory.read_note(title):
            await self._reply(update, f"لم أجد ملاحظة باسم: «{title}»")
            return

        chat_id = str(update.effective_chat.id)
        token = self._remember_action(chat_id, {"kind": "delete_note", "title": title})
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ احذف", callback_data=f"confirm:{token}"),
                    InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel:{token}"),
                ]
            ]
        )
        if update.message:
            await update.message.reply_text(
                f"هل تريد حذف الملاحظة «{title}»؟", reply_markup=keyboard
            )

    async def untask(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /untask <num> — delete a specific active task."""
        if not settings.telegram_allow_destructive:
            await self._reply(update, "حذف المعلومات معطّل في هذا الإعداد.")
            return
        if not context.args:
            await self._reply(update, f"الاستخدام: {command('untask')} <رقم المهمة>")
            return
        tasks = self.memory.get_task_section()
        active = [t for t in tasks if not t["done"]]
        if not active:
            await self._reply(update, "لا توجد مهام نشطة لحذفها.")
            return
        try:
            idx = int(context.args[0]) - 1
        except ValueError:
            await self._reply(update, "يرجى إدخال رقم المهمة.")
            return
        if idx < 0 or idx >= len(active):
            await self._reply(update, "رقم المهمة خارج النطاق.")
            return

        task_text = active[idx]["text"]
        chat_id = str(update.effective_chat.id)
        token = self._remember_action(chat_id, {"kind": "delete_task", "task_text": task_text})
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ احذف", callback_data=f"confirm:{token}"),
                    InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel:{token}"),
                ]
            ]
        )
        if update.message:
            await update.message.reply_text(f"حذف المهمة: «{task_text}»؟", reply_markup=keyboard)

    async def on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle inline-keyboard button callbacks for destructive confirmations."""
        query = update.callback_query
        if not query or not query.data:
            return
        await query.answer()

        action_type, _, token = query.data.partition(":")

        # Consolidator approvals live outside the short-lived token store so they
        # can survive restarts; handle them first.
        if action_type in ("mem_accept", "mem_reject") and self.consolidator:
            resolved = self.consolidator.resolve(token, accept=(action_type == "mem_accept"))
            if not resolved:
                try:
                    await query.edit_message_text("هذا الاقتراح لم يعد متاحًا.")
                except Exception:
                    pass
                return
            verb = "حُفظ" if action_type == "mem_accept" else "رُفض"
            try:
                await query.edit_message_text(f"✅ {verb}: {resolved.content[:200]}")
            except Exception:
                pass
            return

        pending = self._pop_action(token)
        if not pending:
            try:
                await query.edit_message_text("انتهت صلاحية هذا الطلب.")
            except Exception:
                pass
            return

        if action_type == "cancel":
            try:
                await query.edit_message_text("تم الإلغاء.")
            except Exception:
                pass
            return

        if action_type != "confirm":
            return

        kind = pending.get("kind")
        if kind == "forget":
            removed = 0
            categories = [pending["category"]] if pending.get("category") else list(MEMORY_FILES.keys())
            for category in categories:
                removed += self.memory.delete_matches(category, pending["query"])
            try:
                await query.edit_message_text(f"✅ حذفت {removed} سطرًا من الذاكرة.")
            except Exception:
                pass
        elif kind == "delete_note":
            ok = self.memory.delete_note(pending["title"])
            text = f"✅ حذفت الملاحظة «{pending['title']}»." if ok else "تعذّر حذف الملاحظة."
            try:
                await query.edit_message_text(text)
            except Exception:
                pass
        elif kind == "delete_task":
            removed = self.memory.delete_matches("tasks", pending["task_text"], max_deletions=1)
            text = "✅ حذفت المهمة." if removed else "لم أستطع حذف المهمة."
            try:
                await query.edit_message_text(text)
            except Exception:
                pass
        else:
            try:
                await query.edit_message_text("طلب غير معروف.")
            except Exception:
                pass

    async def calendar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /calendar command."""
        response = await self.agent.chat(
            agent_request(t("req.calendar")),
            chat_id=str(update.effective_chat.id),
        )
        for part in truncate_message(response):
            await self._reply(update, part)

    async def shopping(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /shopping command."""
        shopping_data = self.memory.read("shopping")
        if not shopping_data.strip():
            await self._reply(update, "لا توجد قائمة مشتريات حتى الآن. أخبرني بما تحتاجه.")
            return
        for part in truncate_message(shopping_data):
            await self._reply(update, part)

    async def briefing(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /briefing command - manual morning briefing."""
        await self._reply(update, "🌅 جارٍ إعداد ملخصك...")
        response = await self.agent.generate_briefing()
        for part in truncate_message(response):
            await self._reply(update, part)

    async def review(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /review command - manual weekly review."""
        await self._reply(update, "📊 جارٍ إعداد المراجعة الأسبوعية...")
        response = await self.agent.generate_weekly_review()
        for part in truncate_message(response):
            await self._reply(update, part)

    async def note(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /note command."""
        if not context.args:
            await self._reply(update, f"الاستخدام: {command('note')} <العنوان>: <المحتوى>")
            return
        text = " ".join(context.args)
        if ":" in text:
            title, content = text.split(":", 1)
        else:
            title = f"Note {ksa_time_str()}"
            content = text
        self.memory.save_note(title.strip(), content.strip())
        await self._reply(update, f"📝 تم حفظ الملاحظة: {title.strip()}")

    async def week(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /week command."""
        response = await self.agent.chat(
            agent_request(t("req.week")),
            chat_id=str(update.effective_chat.id),
        )
        for part in truncate_message(response):
            await self._reply(update, part)

    async def radar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /radar command."""
        response = await self.agent.chat(
            agent_request(t("req.radar")),
            chat_id=str(update.effective_chat.id),
        )
        for part in truncate_message(response):
            await self._reply(update, part)

    async def undo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /undo — revert the last memory mutation."""
        result = self.memory.undo_last()
        if not result:
            await self._reply(update, "لا يوجد ما يمكن التراجع عنه في الذاكرة.")
            return
        cat = result["category"]
        action = result["action"]
        await self._reply(update, f"↩️ تم التراجع عن آخر تعديل ({action}) في {cat}.")

    async def why(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /why <category> <fragment> — show provenance of a memory line."""
        args = context.args or []
        if len(args) < 2:
            await self._reply(update, "استخدم: /why <category> <جزء من النص>")
            return
        category = args[0].lower()
        fragment = " ".join(args[1:])
        events = self.memory.explain(category, fragment)
        if not events:
            await self._reply(update, f"لم أجد سجلًا لهذا السطر في {category}.")
            return
        lines = [f"سجل {category}:"]
        for ev in events[:5]:
            lines.append(f"- {ev['timestamp']} · {ev['action']} · {ev['source']}")
        await self._reply(update, "\n".join(lines))

    async def consolidate(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /consolidate — manually run the nightly consolidator."""
        if not self.consolidator:
            await self._reply(update, "خدمة التجميع الذاكرة غير مفعّلة. فعّل CONSOLIDATOR_ENABLED في .env.")
            return
        await self._reply(update, "🧠 جارٍ مراجعة ذاكرة اليوم...")
        try:
            result = await self.consolidator.run()
        except Exception as exc:
            log.error(f"Manual consolidation failed: {exc}")
            await self._reply(update, f"تعذّر التجميع: {exc}")
            return
        applied = result.get("applied", 0)
        queued = result.get("queued", 0)
        summary = result.get("summary") or "—"
        await self._reply(update, f"✅ طُبّق {applied}، ينتظر قرارك {queued}\n\n{summary}")

    async def pending(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /pending — list consolidator proposals awaiting approval."""
        if not self.consolidator:
            await self._reply(update, "خدمة التجميع غير مفعّلة.")
            return
        proposals = self.consolidator.load_pending()
        if not proposals:
            await self._reply(update, "لا توجد اقتراحات تنتظر المراجعة.")
            return
        for prop in proposals[:5]:
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("✅ احفظ", callback_data=f"mem_accept:{prop.proposal_id}"),
                        InlineKeyboardButton("❌ تجاهل", callback_data=f"mem_reject:{prop.proposal_id}"),
                    ]
                ]
            )
            text = f"[{prop.kind} · {prop.category}] {prop.content}"
            if prop.existing_line:
                text += f"\n(يستبدل: {prop.existing_line})"
            if update.message:
                await update.message.reply_text(text, reply_markup=keyboard)

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
                await self._reply(update, part)
        except Exception as e:
            log.error(f"Message handler error: {e}")
            await self._reply(update, "حدث خطأ أثناء معالجة رسالتك. حاول مرة أخرى.")

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors."""
        log.error(f"Telegram error: {context.error}")
