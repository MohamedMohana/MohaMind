"""Tests for the Telegram owner lock (Handlers.guard)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ApplicationHandlerStop

from moha_mind.config import settings
from moha_mind.telegram_bot.handlers import Handlers


@pytest.fixture
def handlers(tmp_memory):
    agent = MagicMock()
    return Handlers(agent=agent, memory=tmp_memory)


def _make_update(chat_id: int | None = 100, user_id: int | None = 100, with_callback: bool = False):
    message = MagicMock()
    message.reply_text = AsyncMock()

    update = MagicMock()
    update.message = message
    update.effective_chat = SimpleNamespace(id=chat_id) if chat_id is not None else None
    update.effective_user = SimpleNamespace(id=user_id) if user_id is not None else None
    if with_callback:
        update.callback_query = MagicMock()
        update.callback_query.answer = AsyncMock()
        update.message = None
    else:
        update.callback_query = None
    return update


def _context():
    return MagicMock()


class TestGuardAllows:
    @pytest.mark.asyncio
    async def test_owner_chat_id_passes(self, handlers):
        update = _make_update(chat_id=100, user_id=100)
        with patch.object(settings, "telegram_chat_id", "100"):
            await handlers.guard(update, _context())  # must not raise
        update.message.reply_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_extra_allowed_user_id_passes(self, handlers):
        update = _make_update(chat_id=555, user_id=555)
        with (
            patch.object(settings, "telegram_chat_id", "100"),
            patch.object(settings, "telegram_allowed_user_ids", "444, 555"),
        ):
            await handlers.guard(update, _context())
        update.message.reply_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_owner_user_id_passes_in_other_chat(self, handlers):
        # Group chat has a different chat id, but the sender is the owner.
        update = _make_update(chat_id=-100999, user_id=100)
        with patch.object(settings, "telegram_chat_id", "100"):
            await handlers.guard(update, _context())


class TestGuardBlocks:
    @pytest.mark.asyncio
    async def test_stranger_is_blocked_and_told_once(self, handlers):
        with patch.object(settings, "telegram_chat_id", "100"):
            update = _make_update(chat_id=666, user_id=666)
            with pytest.raises(ApplicationHandlerStop):
                await handlers.guard(update, _context())
            update.message.reply_text.assert_awaited_once()
            body = update.message.reply_text.await_args.args[0]
            assert "private" in body

            # Second attempt from the same chat: blocked silently.
            second = _make_update(chat_id=666, user_id=666)
            with pytest.raises(ApplicationHandlerStop):
                await handlers.guard(second, _context())
            second.message.reply_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stranger_callback_is_blocked_and_answered(self, handlers):
        update = _make_update(chat_id=666, user_id=666, with_callback=True)
        with patch.object(settings, "telegram_chat_id", "100"):
            with pytest.raises(ApplicationHandlerStop):
                await handlers.guard(update, _context())
        update.callback_query.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stranger_never_leaks_owner_ids(self, handlers):
        update = _make_update(chat_id=666, user_id=666)
        with patch.object(settings, "telegram_chat_id", "100"):
            with pytest.raises(ApplicationHandlerStop):
                await handlers.guard(update, _context())
        body = update.message.reply_text.await_args.args[0]
        assert "100" not in body


class TestGuardUnconfigured:
    @pytest.mark.asyncio
    async def test_locked_until_configured_and_shows_chat_id(self, handlers):
        update = _make_update(chat_id=777, user_id=777)
        with (
            patch.object(settings, "telegram_chat_id", ""),
            patch.object(settings, "telegram_allowed_user_ids", ""),
        ):
            with pytest.raises(ApplicationHandlerStop):
                await handlers.guard(update, _context())
        body = update.message.reply_text.await_args.args[0]
        assert "TELEGRAM_CHAT_ID=777" in body

    @pytest.mark.asyncio
    async def test_unconfigured_hint_repeats_for_owner_convenience(self, handlers):
        with (
            patch.object(settings, "telegram_chat_id", ""),
            patch.object(settings, "telegram_allowed_user_ids", ""),
        ):
            for _ in range(2):
                update = _make_update(chat_id=777, user_id=777)
                with pytest.raises(ApplicationHandlerStop):
                    await handlers.guard(update, _context())
                update.message.reply_text.assert_awaited_once()


class TestAllowedIdsProperty:
    def test_combines_chat_id_and_extra_ids(self):
        with (
            patch.object(settings, "telegram_chat_id", " 100 "),
            patch.object(settings, "telegram_allowed_user_ids", "200, 300 ,"),
        ):
            assert settings.telegram_allowed_ids == frozenset({"100", "200", "300"})

    def test_empty_when_nothing_configured(self):
        with (
            patch.object(settings, "telegram_chat_id", ""),
            patch.object(settings, "telegram_allowed_user_ids", ""),
        ):
            assert settings.telegram_allowed_ids == frozenset()
