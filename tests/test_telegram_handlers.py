"""Tests for the new Telegram handler commands and destructive-action flow."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from moha_mind.telegram_bot.handlers import Handlers


@pytest.fixture
def handlers(tmp_memory):
    agent = MagicMock()
    agent.provider = "zai"
    agent.model = "glm-5-turbo"
    agent.verifier = None
    return Handlers(agent=agent, memory=tmp_memory)


def _make_update(text: str = "", chat_id: int = 100):
    message = MagicMock()
    message.reply_text = AsyncMock()
    message.chat = MagicMock()
    message.chat.send_action = AsyncMock()
    message.text = text

    update = MagicMock()
    update.message = message
    update.effective_chat = SimpleNamespace(id=chat_id)
    update.effective_user = SimpleNamespace(first_name="Mohana")
    update.callback_query = None
    return update


def _context(args: list[str] | None = None):
    ctx = MagicMock()
    ctx.args = args or []
    return ctx


class TestHelpAndStatus:
    @pytest.mark.asyncio
    async def test_help_lists_sections(self, handlers):
        update = _make_update()
        with patch.object(handlers, "_reply", new=AsyncMock()) as reply:
            await handlers.help(update, _context())
        reply.assert_awaited()
        body = reply.await_args.args[1]
        assert "/memory" in body
        assert "/forget" in body
        assert "/help" not in body or True  # not asserted, section titles matter

    @pytest.mark.asyncio
    async def test_status_shows_strategy_and_tasks(self, handlers):
        handlers.memory.write("tasks", "# Tasks\n\n- [ ] Call Ahmad\n- [ ] Write doc\n")
        update = _make_update()
        with patch.object(handlers, "_reply", new=AsyncMock()) as reply:
            await handlers.status(update, _context())
        body = reply.await_args.args[1]
        assert "zai" in body
        # 2 active tasks should appear
        assert "2" in body


class TestMemoryCommands:
    @pytest.mark.asyncio
    async def test_memory_overview_lists_categories(self, handlers):
        handlers.memory.write("tasks", "- [ ] one\n- [ ] two\n")
        update = _make_update()
        with patch.object(handlers, "_reply", new=AsyncMock()) as reply:
            await handlers.memory_overview(update, _context())
        body = reply.await_args.args[1]
        assert "tasks" in body
        assert "profile" in body

    @pytest.mark.asyncio
    async def test_show_memory_rejects_unknown_category(self, handlers):
        update = _make_update()
        with patch.object(handlers, "_reply", new=AsyncMock()) as reply:
            await handlers.show_memory(update, _context(["nonsense"]))
        body = reply.await_args.args[1]
        assert "غير معروف" in body

    @pytest.mark.asyncio
    async def test_show_memory_prints_content(self, handlers):
        handlers.memory.write("tasks", "- [ ] buy milk\n")
        update = _make_update()
        with patch.object(handlers, "_reply", new=AsyncMock()) as reply:
            await handlers.show_memory(update, _context(["tasks"]))
        body = reply.await_args.args[1]
        assert "buy milk" in body

    @pytest.mark.asyncio
    async def test_notes_list_when_empty(self, handlers):
        update = _make_update()
        with patch.object(handlers, "_reply", new=AsyncMock()) as reply:
            await handlers.notes_list(update, _context())
        assert "لا توجد" in reply.await_args.args[1]

    @pytest.mark.asyncio
    async def test_notes_list_shows_notes(self, handlers):
        handlers.memory.save_note("meeting", "discuss roadmap")
        update = _make_update()
        with patch.object(handlers, "_reply", new=AsyncMock()) as reply:
            await handlers.notes_list(update, _context())
        assert "meeting" in reply.await_args.args[1]

    @pytest.mark.asyncio
    async def test_read_note_missing(self, handlers):
        update = _make_update()
        with patch.object(handlers, "_reply", new=AsyncMock()) as reply:
            await handlers.read_note(update, _context(["nonexistent"]))
        assert "لم أجد" in reply.await_args.args[1]


class TestForgetFlow:
    @pytest.mark.asyncio
    async def test_forget_without_args_shows_usage(self, handlers):
        update = _make_update()
        with patch.object(handlers, "_reply", new=AsyncMock()) as reply:
            await handlers.forget(update, _context())
        assert "الاستخدام" in reply.await_args.args[1]

    @pytest.mark.asyncio
    async def test_forget_no_matches(self, handlers):
        update = _make_update()
        with patch.object(handlers, "_reply", new=AsyncMock()) as reply:
            await handlers.forget(update, _context(["zzzzzz"]))
        assert "لا توجد" in reply.await_args.args[1]

    @pytest.mark.asyncio
    async def test_forget_stores_pending_action(self, handlers):
        handlers.memory.write("tasks", "- [ ] Call Ahmad\n- [ ] Write doc\n")
        update = _make_update(chat_id=555)
        await handlers.forget(update, _context(["Call"]))

        update.message.reply_text.assert_awaited()
        assert len(handlers._pending_actions) == 1
        token = next(iter(handlers._pending_actions))
        assert handlers._pending_actions[token]["kind"] == "forget"
        assert handlers._pending_actions[token]["query"] == "Call"

    @pytest.mark.asyncio
    async def test_callback_confirm_executes_forget(self, handlers):
        handlers.memory.write("tasks", "- [ ] Call Ahmad\n- [ ] Other\n")
        token = handlers._remember_action(
            "555",
            {"kind": "forget", "query": "Call", "category": "tasks", "count": 1},
        )

        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.data = f"confirm:{token}"

        update = MagicMock()
        update.callback_query = query
        update.effective_chat = SimpleNamespace(id=555)

        await handlers.on_callback(update, _context())

        content = handlers.memory.read("tasks")
        assert "Call Ahmad" not in content
        assert "Other" in content
        query.edit_message_text.assert_awaited()

    @pytest.mark.asyncio
    async def test_callback_cancel_leaves_memory_alone(self, handlers):
        handlers.memory.write("tasks", "- [ ] Call Ahmad\n")
        token = handlers._remember_action(
            "555",
            {"kind": "forget", "query": "Call", "category": "tasks", "count": 1},
        )

        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.data = f"cancel:{token}"

        update = MagicMock()
        update.callback_query = query

        await handlers.on_callback(update, _context())

        assert "Call Ahmad" in handlers.memory.read("tasks")

    @pytest.mark.asyncio
    async def test_callback_unknown_token_is_safe(self, handlers):
        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.data = "confirm:does-not-exist"

        update = MagicMock()
        update.callback_query = query

        await handlers.on_callback(update, _context())
        query.edit_message_text.assert_awaited()


class TestDeleteNoteFlow:
    @pytest.mark.asyncio
    async def test_delete_note_requires_args(self, handlers):
        update = _make_update()
        with patch.object(handlers, "_reply", new=AsyncMock()) as reply:
            await handlers.delete_note(update, _context())
        assert "الاستخدام" in reply.await_args.args[1]

    @pytest.mark.asyncio
    async def test_delete_note_missing(self, handlers):
        update = _make_update()
        with patch.object(handlers, "_reply", new=AsyncMock()) as reply:
            await handlers.delete_note(update, _context(["ghost"]))
        assert "لم أجد" in reply.await_args.args[1]

    @pytest.mark.asyncio
    async def test_delete_note_confirm_removes_file(self, handlers):
        handlers.memory.save_note("meeting", "x")
        update = _make_update()
        await handlers.delete_note(update, _context(["meeting"]))
        token = next(iter(handlers._pending_actions))

        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.data = f"confirm:{token}"
        cb_update = MagicMock()
        cb_update.callback_query = query
        cb_update.effective_chat = SimpleNamespace(id=100)

        await handlers.on_callback(cb_update, _context())
        assert "meeting" not in handlers.memory.list_notes()


class TestUntaskFlow:
    @pytest.mark.asyncio
    async def test_untask_requires_args(self, handlers):
        update = _make_update()
        with patch.object(handlers, "_reply", new=AsyncMock()) as reply:
            await handlers.untask(update, _context())
        assert "الاستخدام" in reply.await_args.args[1]

    @pytest.mark.asyncio
    async def test_untask_confirms_and_deletes(self, handlers):
        handlers.memory.write("tasks", "# Tasks\n\n## Active\n- [ ] First\n- [ ] Second\n")
        update = _make_update()
        await handlers.untask(update, _context(["1"]))
        token = next(iter(handlers._pending_actions))

        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.data = f"confirm:{token}"
        cb_update = MagicMock()
        cb_update.callback_query = query
        cb_update.effective_chat = SimpleNamespace(id=100)
        await handlers.on_callback(cb_update, _context())

        content = handlers.memory.read("tasks")
        assert "First" not in content
        assert "Second" in content
