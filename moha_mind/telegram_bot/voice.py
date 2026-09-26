from __future__ import annotations

import secrets
import time
from datetime import timedelta

from pydantic import BaseModel
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from moha_mind.agent.core import MohaMindAgent
from moha_mind.agent.voice import LocalTranscriber, VoiceError
from moha_mind.config import settings
from moha_mind.telegram_bot.formatters import reply_markdown, truncate_message
from moha_mind.utils.i18n import t
from moha_mind.utils.logging_config import log


class PendingVoice(BaseModel):
    token: str
    text: str
    expires_at: float


class VoiceHandlers:
    def __init__(self, agent: MohaMindAgent):
        self.agent = agent
        self.transcriber = LocalTranscriber(settings)
        self.pending: dict[str, PendingVoice] = {}

    def _purge(self) -> None:
        now = time.monotonic()
        self.pending = {chat: item for chat, item in self.pending.items() if item.expires_at > now}

    async def receive(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.message
        if not message or not update.effective_chat:
            return
        media = message.voice or message.audio
        if not media:
            return
        if not settings.voice_enabled:
            await message.reply_text(t("voice.disabled"))
            return
        chat_id = str(update.effective_chat.id)
        self._purge()
        self.pending.pop(chat_id, None)
        try:
            limit = settings.voice_max_file_mb * 1024 * 1024
            if media.file_size is None or media.file_size > limit:
                raise VoiceError("too_large")
            duration = media.duration
            if isinstance(duration, timedelta):
                duration = duration.total_seconds()
            if duration > settings.voice_max_duration_seconds:
                raise VoiceError("too_long")
            await message.reply_text(t("voice.processing"))
            remote_file = await media.get_file()
            if remote_file.file_size is None or remote_file.file_size > limit:
                raise VoiceError("too_large")
            audio = await remote_file.download_as_bytearray()
            transcript = await self.transcriber.transcribe(audio)
            del audio
            token = secrets.token_urlsafe(12)
            for part in truncate_message(t("voice.preview") + "\n\n" + transcript.text, max_length=3000):
                await message.reply_text(part)
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(t("voice.confirm"), callback_data=f"voice:confirm:{token}"),
                        InlineKeyboardButton(t("voice.cancel"), callback_data=f"voice:cancel:{token}"),
                    ]
                ]
            )
            if len(self.pending) >= 100:
                self.pending.pop(next(iter(self.pending)))
            self.pending[chat_id] = PendingVoice(
                token=token,
                text=transcript.text,
                expires_at=time.monotonic() + 300,
            )
            await message.reply_text(t("voice.review"), reply_markup=keyboard)
        except VoiceError as exc:
            await message.reply_text(t(f"voice.{exc.code}"))
        except Exception as exc:
            self.pending.pop(chat_id, None)
            log.warning("Voice message failed (%s)", type(exc).__name__)
            await message.reply_text(t("voice.failed"))

    async def confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not query.data or not query.message or not update.effective_chat:
            return
        self._purge()
        _, action, token = query.data.split(":", 2)
        chat_id = str(update.effective_chat.id)
        pending = self.pending.get(chat_id)
        if not pending or not secrets.compare_digest(pending.token, token):
            await query.answer(t("voice.expired"), show_alert=True)
            return
        await query.answer()
        if action not in {"confirm", "cancel"}:
            return
        self.pending.pop(chat_id)
        if action == "cancel":
            await query.edit_message_text(t("voice.cancelled"))
            return
        if not settings.voice_enabled:
            await query.edit_message_text(t("voice.disabled"))
            return
        await query.edit_message_text(t("voice.sent"))
        try:
            response = await self.agent.chat(pending.text, chat_id=chat_id)
            for part in truncate_message(response, max_length=3000):
                await reply_markdown(query.message, part)
        except Exception as exc:
            log.warning("Voice request failed (%s)", type(exc).__name__)
            await query.message.reply_text(t("voice.failed"))
