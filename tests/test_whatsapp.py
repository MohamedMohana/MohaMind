import asyncio
import json
from io import StringIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError
from rich.console import Console

from moha_mind.whatsapp_bot.bot import IncomingMessage, WhatsAppBot, WhatsAppBridge, _claim_message, run_whatsapp


def incoming(**kwargs):
    return IncomingMessage(type="message", id="fictional-message-1", text="Remember a fictional task", **kwargs)


@pytest.mark.parametrize("fields", [{}, {"from_me": False, "is_self": True}, {"from_me": True, "is_self": False}])
def test_rejects_messages_without_self_chat_authorization(fields):
    with pytest.raises(ValidationError):
        incoming(**fields)


def test_receipts_survive_restart_and_do_not_store_message_content(tmp_path):
    path = tmp_path / "receipts.sqlite3"
    assert _claim_message(path, "account-1", "message-1")
    assert not _claim_message(path, "account-1", "message-1")
    assert _claim_message(path, "account-2", "message-1")
    assert b"account-1" not in path.read_bytes()


@pytest.fixture
def bot(tmp_path):
    agent = SimpleNamespace(chat=AsyncMock(return_value="Saved"))
    bridge = SimpleNamespace(
        session_dir=tmp_path,
        account="15550000001@s.whatsapp.net",
        send_message=AsyncMock(),
    )
    return WhatsAppBot(agent, bridge)


async def test_self_chat_uses_existing_agent_and_separate_conversation(bot):
    await bot.handle_message(incoming(from_me=True, is_self=True))
    bot.agent.chat.assert_awaited_once()
    assert bot.agent.chat.call_args.args == ("Remember a fictional task",)
    assert bot.agent.chat.call_args.kwargs["chat_id"].startswith("whatsapp:")
    assert "15550000001" not in bot.agent.chat.call_args.kwargs["chat_id"]
    bot.bridge.send_message.assert_awaited_once_with("Saved")


async def test_duplicate_messages_do_not_repeat_actions(bot):
    message = incoming(from_me=True, is_self=True)
    await bot.handle_message(message)
    await WhatsAppBot(bot.agent, bot.bridge).handle_message(message)
    bot.agent.chat.assert_awaited_once()
    bot.bridge.send_message.assert_awaited_once()


async def test_failed_send_does_not_replay_completed_agent_actions(bot):
    message = incoming(from_me=True, is_self=True)
    bot.bridge.send_message.side_effect = RuntimeError("disconnected")
    with pytest.raises(RuntimeError):
        await bot.handle_message(message)
    await WhatsAppBot(bot.agent, bot.bridge).handle_message(message)
    bot.agent.chat.assert_awaited_once()


async def test_help_does_not_call_provider(bot):
    message = incoming(from_me=True, is_self=True)
    message.text = "/help"
    await bot.handle_message(message)
    bot.agent.chat.assert_not_awaited()
    assert "existing memory" in bot.bridge.send_message.call_args.args[0]


async def test_bridge_chunks_replies_and_waits_for_acknowledgment(tmp_path):
    bridge = WhatsAppBridge(tmp_path)
    bridge.ready.set()
    payloads = []

    def write(data):
        payload = json.loads(data)
        payloads.append(payload)
        bridge.pending[payload["request_id"]].set_result(None)

    bridge.process = SimpleNamespace(stdin=SimpleNamespace(write=write, drain=AsyncMock()))
    await bridge.send_message("أ" * 7100)
    assert [len(payload["text"]) for payload in payloads] == [3500, 3500, 100]
    assert all("chat_id" not in payload for payload in payloads)
    assert bridge.pending == {}


async def test_bridge_refuses_arbitrary_recipients_and_offline_sends(tmp_path):
    bridge = WhatsAppBridge(tmp_path)
    with pytest.raises(ValueError, match="self-chat"):
        await bridge.send_message("hello", chat_id="15550000002")
    with pytest.raises(RuntimeError, match="not connected"):
        await bridge.send_message("hello")


def event_stream(*events):
    stream = asyncio.StreamReader()
    for event in events:
        stream.feed_data((json.dumps(event) + "\n").encode())
    stream.feed_eof()
    return stream


async def test_bridge_rejects_untrusted_event_without_logging_content(tmp_path, caplog):
    bridge = WhatsAppBridge(tmp_path, Console(file=StringIO()))
    bridge.process = SimpleNamespace(
        stdout=event_stream({"type": "message", "id": "id", "text": "private rejected text", "from_me": False}),
        wait=AsyncMock(return_value=0),
    )
    await bridge._read_events()
    assert bridge.messages.empty()
    assert "private rejected text" not in caplog.text


async def test_bridge_fails_pending_delivery_when_connection_closes(tmp_path):
    bridge = WhatsAppBridge(tmp_path, Console(file=StringIO()))
    future = asyncio.get_running_loop().create_future()
    bridge.pending["send-1"] = future
    bridge.ready.set()
    bridge.process = SimpleNamespace(stdout=event_stream(), wait=AsyncMock(return_value=0))
    await bridge._read_events()
    assert not bridge.ready.is_set()
    with pytest.raises(RuntimeError, match="outcome is unknown"):
        await future


async def test_bridge_accepts_only_valid_events_and_does_not_log_qr(tmp_path, caplog):
    output = StringIO()
    bridge = WhatsAppBridge(tmp_path, Console(file=output))
    message = incoming(from_me=True, is_self=True)
    bridge.process = SimpleNamespace(
        stdout=event_stream(
            {"type": "qr", "terminal": "fictional-qr-token"},
            {"type": "connected", "account": "15550000001@s.whatsapp.net"},
            message.model_dump(),
        ),
        wait=AsyncMock(return_value=0),
    )
    await bridge._read_events()
    assert await bridge.messages.get() == message
    assert "fictional-qr-token" in output.getvalue()
    assert "fictional-qr-token" not in caplog.text


async def test_pairing_does_not_bootstrap_agent_or_read_memory(tmp_path, monkeypatch):
    from moha_mind import main

    bootstrap = AsyncMock()
    monkeypatch.setattr(main, "bootstrap", bootstrap)
    bridge = Mock()
    bridge.start = AsyncMock()
    bridge.wait_ready = AsyncMock()
    bridge.close = AsyncMock()
    bridge.reader = asyncio.create_task(asyncio.sleep(0))
    monkeypatch.setattr("moha_mind.whatsapp_bot.bot.WhatsAppBridge", lambda *args: bridge)
    await run_whatsapp(pair=True)
    bridge.start.assert_awaited_once_with(pair=True)
    bridge.close.assert_awaited_once()
    bootstrap.assert_not_awaited()


async def test_whatsapp_bootstraps_existing_memory_and_cleans_up(tmp_memory, monkeypatch):
    from moha_mind import main

    tmp_memory.write("profile", "Fictional existing profile")
    before = {p.name: p.read_bytes() for p in tmp_memory.memory_path.glob("*.md")}
    agent = SimpleNamespace(external_mcp=SimpleNamespace(aclose=AsyncMock()))
    bootstrap = AsyncMock(return_value=(tmp_memory, agent, None, None))
    monkeypatch.setattr(main, "bootstrap", bootstrap)
    bridge = Mock()
    bridge.start = AsyncMock()
    bridge.wait_ready = AsyncMock()
    bridge.close = AsyncMock()
    bridge.messages = asyncio.Queue()
    bridge.reader = asyncio.create_task(asyncio.sleep(0))
    monkeypatch.setattr("moha_mind.whatsapp_bot.bot.WhatsAppBridge", lambda *args: bridge)
    await run_whatsapp()
    bootstrap.assert_awaited_once_with(require_telegram=False)
    assert {p.name: p.read_bytes() for p in tmp_memory.memory_path.glob("*.md")} == before
    bridge.close.assert_awaited_once()
    agent.external_mcp.aclose.assert_awaited_once()


def test_whatsapp_setup_entrypoint_does_not_require_api_key(monkeypatch):
    from moha_mind import main

    run = AsyncMock()
    auth = Mock(side_effect=AssertionError("pairing must not read memory or require an API key"))
    monkeypatch.setattr("sys.argv", ["mohamind", "whatsapp", "setup"])
    monkeypatch.setattr(main, "_has_api_key", auth)
    monkeypatch.setattr(main, "configure_logging", Mock())
    monkeypatch.setattr("moha_mind.whatsapp_bot.bot.run_whatsapp", run)
    main.run()
    run.assert_awaited_once_with(pair=True)


def test_whatsapp_schedule_entrypoint(monkeypatch):
    from moha_mind import main

    run = AsyncMock()
    monkeypatch.setattr("sys.argv", ["mohamind", "whatsapp", "--schedule"])
    monkeypatch.setattr(main, "_has_api_key", lambda: True)
    monkeypatch.setattr(main, "configure_logging", Mock())
    monkeypatch.setattr("moha_mind.whatsapp_bot.bot.run_whatsapp", run)
    main.run()
    run.assert_awaited_once_with(schedule=True)
