import asyncio
import sys
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from moha_mind.agent.voice import LocalTranscriber, VoiceError
from moha_mind.config import Settings


@pytest.fixture
def transcriber(monkeypatch):
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    config = Settings(_env_file=None, voice_enabled=True)
    service = LocalTranscriber(config)
    monkeypatch.setattr(service, "_decode", lambda audio: "decoded waveform")
    return service


@pytest.fixture
def whisper(monkeypatch):
    model = MagicMock()
    model.transcribe.return_value = (
        iter([SimpleNamespace(text=" مرحبًا "), SimpleNamespace(text="hello ")]),
        SimpleNamespace(language="ar"),
    )
    constructor = MagicMock(return_value=model)
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=constructor))
    return constructor, model


async def test_multilingual_transcription_is_local_and_keeps_original_language(transcriber, whisper):
    constructor, model = whisper
    transcript = await transcriber.transcribe(b"audio")
    assert transcript.text == "مرحبًا hello"
    assert transcript.language == "ar"
    constructor.assert_called_once_with(
        "small", device="cpu", compute_type="int8", cpu_threads=4, local_files_only=False
    )
    assert model.transcribe.call_args.kwargs == {
        "language": None,
        "task": "transcribe",
        "beam_size": 5,
        "vad_filter": True,
        "condition_on_previous_text": False,
    }


async def test_model_is_reused_and_language_can_be_forced(transcriber, whisper):
    constructor, model = whisper
    transcriber.config.voice_language = "en"
    model.transcribe.side_effect = lambda *a, **kw: ([SimpleNamespace(text="hello")], SimpleNamespace(language="en"))
    await transcriber.transcribe(b"one")
    await transcriber.transcribe(b"two")
    constructor.assert_called_once()
    assert model.transcribe.call_args.kwargs["language"] == "en"


@pytest.mark.parametrize("enabled,audio,code", [(False, b"a", "disabled"), (True, b"", "no_speech")])
async def test_invalid_requests_do_not_load_model(transcriber, whisper, enabled, audio, code):
    transcriber.config.voice_enabled = enabled
    with pytest.raises(VoiceError, match=code):
        await transcriber.transcribe(audio)
    whisper[0].assert_not_called()


async def test_size_checked_again_after_download(transcriber, whisper):
    transcriber.config.voice_max_file_mb = 1
    with pytest.raises(VoiceError, match="too_large"):
        await transcriber.transcribe(b"a" * (1024 * 1024 + 1))
    whisper[0].assert_not_called()


async def test_missing_optional_dependency(transcriber, monkeypatch):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    with pytest.raises(VoiceError, match="unavailable"):
        await transcriber.transcribe(b"audio")


async def test_silence_is_not_forwarded(transcriber, whisper):
    whisper[1].transcribe.return_value = ([], SimpleNamespace(language="ar"))
    with pytest.raises(VoiceError, match="no_speech"):
        await transcriber.transcribe(b"audio")


async def test_decoder_errors_do_not_expose_recording_or_paths(transcriber, whisper, monkeypatch):
    monkeypatch.setattr(transcriber, "_decode", MagicMock(side_effect=ValueError("private recording")))
    with pytest.raises(VoiceError, match="^failed$"):
        await transcriber.transcribe(b"audio")
    whisper[0].assert_not_called()


async def test_inference_runs_off_event_loop(transcriber, whisper):
    loop_thread = threading.get_ident()
    thread_ids = []

    def segments():
        thread_ids.append(threading.get_ident())
        yield SimpleNamespace(text="hello")

    whisper[1].transcribe.return_value = (segments(), SimpleNamespace(language="en"))
    await transcriber.transcribe(b"audio")
    assert thread_ids[0] != loop_thread


async def test_cancellation_does_not_release_model_while_worker_is_running(transcriber, whisper):
    started = threading.Event()
    finish = threading.Event()

    def slow(*args, **kwargs):
        started.set()
        finish.wait(timeout=5)
        return [SimpleNamespace(text="hello")], SimpleNamespace(language="en")

    whisper[1].transcribe.side_effect = slow
    task = asyncio.create_task(transcriber.transcribe(b"audio"))
    try:
        assert await asyncio.to_thread(started.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        assert transcriber._lock.locked()
    finally:
        finish.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not transcriber._lock.locked()


@pytest.mark.parametrize(
    "field,value",
    [
        ("voice_model", "small.en"),
        ("voice_model", "distil-large-v3"),
        ("voice_model", " "),
        ("voice_max_file_mb", 21),
        ("voice_max_duration_seconds", 0),
        ("voice_cpu_threads", 0),
    ],
)
def test_voice_settings_are_validated(field, value, monkeypatch):
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


def silent_wav(seconds):
    import wave
    from io import BytesIO

    buffer = BytesIO()
    with wave.open(buffer, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(b"\0\0" * (16000 * seconds))
    return buffer.getvalue()


def test_real_decoder_returns_mono_float_audio(transcriber):
    pytest.importorskip("av")
    pytest.importorskip("numpy")
    waveform = LocalTranscriber._decode(transcriber, silent_wav(1))
    assert waveform.shape == (16000,)
    assert str(waveform.dtype) == "float32"
    assert not waveform.any()


def test_real_decoder_enforces_duration_even_if_metadata_lies(transcriber):
    pytest.importorskip("av")
    pytest.importorskip("numpy")
    transcriber.config.voice_max_duration_seconds = 1
    with pytest.raises(VoiceError, match="too_long"):
        LocalTranscriber._decode(transcriber, silent_wav(2))
