from __future__ import annotations

import asyncio
from io import BytesIO

from pydantic import BaseModel

from moha_mind.config import Settings


class VoiceError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class Transcript(BaseModel):
    text: str
    language: str


class LocalTranscriber:
    def __init__(self, config: Settings):
        self.config = config
        self._model = None
        self._lock = asyncio.Lock()

    async def transcribe(self, audio: bytes | bytearray) -> Transcript:
        if not self.config.voice_enabled:
            raise VoiceError("disabled")
        if len(audio) > self.config.voice_max_file_mb * 1024 * 1024:
            raise VoiceError("too_large")
        if not audio:
            raise VoiceError("no_speech")
        async with self._lock:
            worker = asyncio.create_task(asyncio.to_thread(self._transcribe, audio))
            try:
                return await asyncio.shield(worker)
            except asyncio.CancelledError:
                try:
                    await worker
                except Exception:
                    pass
                raise

    def _decode(self, audio: bytes | bytearray):
        import av
        import numpy as np

        samples = 0
        chunks = []
        limit = self.config.voice_max_duration_seconds * 16000
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)

        def collect(frames):
            nonlocal samples
            for frame in frames:
                samples += frame.samples
                if samples > limit:
                    raise VoiceError("too_long")
                chunks.append(frame.to_ndarray().flatten())

        with av.open(BytesIO(audio)) as container:
            for frame in container.decode(audio=0):
                collect(resampler.resample(frame))
            collect(resampler.resample(None))
        if not chunks:
            raise VoiceError("no_speech")
        return np.concatenate(chunks).astype(np.float32) / 32768.0

    def _transcribe(self, audio: bytes | bytearray) -> Transcript:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise VoiceError("unavailable") from None
        try:
            waveform = self._decode(audio)
            if self._model is None:
                self._model = WhisperModel(
                    self.config.voice_model,
                    device=self.config.voice_device,
                    compute_type=self.config.voice_compute_type,
                    cpu_threads=self.config.voice_cpu_threads,
                    local_files_only=self.config.voice_local_files_only,
                )
            segments, info = self._model.transcribe(
                waveform,
                language=None if self.config.voice_language == "auto" else self.config.voice_language,
                task="transcribe",
                beam_size=5,
                vad_filter=True,
                condition_on_previous_text=False,
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
            if not text:
                raise VoiceError("no_speech")
            return Transcript(text=text, language=info.language)
        except VoiceError:
            raise
        except Exception:
            raise VoiceError("failed") from None
