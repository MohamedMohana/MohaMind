import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import ApplicationHandlerStop

from moha_mind.agent.voice import Transcript, VoiceError
from moha_mind.config import settings
from moha_mind.telegram_bot.bot import MohaMindBot
from moha_mind.telegram_bot.voice import PendingVoice, VoiceHandlers


@pytest.fixture
def voice(monkeypatch):
    monkeypatch.setattr(settings, "voice_enabled", True)
    monkeypatch.setattr(settings, "voice_max_file_mb", 10)
    monkeypatch.setattr(settings, "voice_max_duration_seconds", 300)
    monkeypatch.setattr(settings, "agent_language", "en")
    handler = VoiceHandlers(SimpleNamespace(chat=AsyncMock(return_value="reply")))
    handler.transcriber.transcribe = AsyncMock(return_value=Transcript(text="مرحبا hello", language="ar"))
    return handler


def update_with_audio():
    remote = SimpleNamespace(file_size=100, download_as_bytearray=AsyncMock(return_value=bytearray(b"recording")))
    media = SimpleNamespace(file_size=100, duration=5, get_file=AsyncMock(return_value=remote))
    message = SimpleNamespace(voice=media, audio=None, reply_text=AsyncMock())
    return SimpleNamespace(message=message, effective_chat=SimpleNamespace(id=100)), remote


def callback(token, action="confirm", chat_id=100):
    query = SimpleNamespace(
        data=f"voice:{action}:{token}",
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
        message=SimpleNamespace(reply_text=AsyncMock()),
    )
    return SimpleNamespace(callback_query=query, effective_chat=SimpleNamespace(id=chat_id))


async def test_voice_requires_explicit_confirmation(voice):
    update, remote = update_with_audio()
    await voice.receive(update, None)
    remote.download_as_bytearray.assert_awaited_once()
    voice.agent.chat.assert_not_awaited()
    assert "مرحبا hello" in update.message.reply_text.await_args_list[1].args[0]
    token = voice.pending["100"].token
    confirm = callback(token)
    await voice.confirm(confirm, None)
    voice.agent.chat.assert_awaited_once_with("مرحبا hello", chat_id="100")
    confirm.callback_query.message.reply_text.assert_awaited_once()
    assert not voice.pending


@pytest.mark.parametrize("action", ["confirm", "cancel"])
async def test_callback_cannot_be_replayed(voice, action):
    voice.pending["100"] = PendingVoice(token="token", text="hello", expires_at=time.monotonic() + 60)
    update = callback("token", action)
    await voice.confirm(update, None)
    await voice.confirm(update, None)
    assert voice.agent.chat.await_count == (1 if action == "confirm" else 0)
    assert not voice.pending


async def test_another_chat_cannot_confirm_or_remove_pending_voice(voice):
    voice.pending["100"] = PendingVoice(token="token", text="private text", expires_at=time.monotonic() + 60)
    update = callback("token", chat_id=200)
    await voice.confirm(update, None)
    voice.agent.chat.assert_not_awaited()
    assert "100" in voice.pending
    assert "private text" not in str(update.callback_query.answer.await_args_list)


async def test_expired_voice_cannot_execute(voice):
    voice.pending["100"] = PendingVoice(token="token", text="hello", expires_at=time.monotonic() - 1)
    await voice.confirm(callback("token"), None)
    voice.agent.chat.assert_not_awaited()
    assert not voice.pending


@pytest.mark.parametrize("size,duration", [(11 * 1024 * 1024, 5), (None, 5), (100, 301)])
async def test_limits_checked_before_download(voice, size, duration):
    update, _ = update_with_audio()
    update.message.voice.file_size = size
    update.message.voice.duration = duration
    await voice.receive(update, None)
    update.message.voice.get_file.assert_not_awaited()
    voice.transcriber.transcribe.assert_not_awaited()


async def test_remote_file_size_checked_before_download(voice):
    update, remote = update_with_audio()
    remote.file_size = 11 * 1024 * 1024
    await voice.receive(update, None)
    remote.download_as_bytearray.assert_not_awaited()


async def test_audio_uploads_also_work(voice):
    update, _ = update_with_audio()
    update.message.audio, update.message.voice = update.message.voice, None
    await voice.receive(update, None)
    assert "100" in voice.pending


async def test_disabled_voice_never_downloads_audio(voice, monkeypatch):
    monkeypatch.setattr(settings, "voice_enabled", False)
    update, _ = update_with_audio()
    await voice.receive(update, None)
    update.message.voice.get_file.assert_not_awaited()


@pytest.mark.parametrize("code", ["unavailable", "no_speech", "failed", "too_long"])
async def test_transcription_failures_never_reach_agent(voice, code):
    update, _ = update_with_audio()
    voice.transcriber.transcribe.side_effect = VoiceError(code)
    await voice.receive(update, None)
    assert not voice.pending
    voice.agent.chat.assert_not_awaited()


async def test_new_recording_invalidates_old_preview(voice):
    update, _ = update_with_audio()
    await voice.receive(update, None)
    old_token = voice.pending["100"].token
    await voice.receive(update, None)
    await voice.confirm(callback(old_token), None)
    voice.agent.chat.assert_not_awaited()
    assert voice.pending["100"].token != old_token


async def test_failed_download_does_not_log_private_error(voice, caplog):
    update, remote = update_with_audio()
    remote.download_as_bytearray.side_effect = RuntimeError("private-file-url")
    await voice.receive(update, None)
    assert "private-file-url" not in caplog.text
    assert not voice.pending


async def test_unauthorized_voice_is_stopped_before_audio_handler(tmp_memory, monkeypatch):
    monkeypatch.setattr(settings, "telegram_chat_id", "100")
    monkeypatch.setattr(settings, "telegram_allowed_user_ids", "")
    bot = MohaMindBot(MagicMock(), tmp_memory)
    update, remote = update_with_audio()
    update.effective_chat = SimpleNamespace(id=200, type="private")
    update.effective_user = SimpleNamespace(id=200)
    update.callback_query = None
    with pytest.raises(ApplicationHandlerStop):
        await bot.handlers.guard(update, None)
    remote.download_as_bytearray.assert_not_awaited()


async def test_proactive_messages_never_go_to_groups(tmp_memory):
    bot = MohaMindBot(MagicMock(), tmp_memory)
    bot.app = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
    await bot.send_message("private reminder", chat_id="-100999")
    bot.app.bot.send_message.assert_not_awaited()
