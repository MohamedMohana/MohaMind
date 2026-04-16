"""Pluggable embedding backends for MohaMind semantic memory.

Three backends are supported:
- none   -> embeddings disabled. Factory returns None and callers gracefully
            skip semantic features (FTS5 + substring search still work).
- openai -> uses the existing OpenAI client to call text-embedding-3-small
            (or another configured model).
- local  -> uses sentence-transformers locally. Only imported on demand so
            the optional dependency never breaks the default install.

The `Embedder` protocol keeps the semantic index decoupled from the backend.
"""

from __future__ import annotations

import asyncio
from typing import Optional, Protocol

from moha_mind.config import settings
from moha_mind.utils.logging_config import log

DEFAULT_OPENAI_MODEL = "text-embedding-3-small"
DEFAULT_LOCAL_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class Embedder(Protocol):
    provider: str
    model: str
    dim: int

    def encode(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbedder:
    def __init__(self, api_key: str, model: str = DEFAULT_OPENAI_MODEL, base_url: Optional[str] = None):
        from openai import OpenAI  # imported lazily — avoids network at import time

        self.provider = "openai"
        self.model = model or DEFAULT_OPENAI_MODEL
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        # 1536 for text-embedding-3-small, 3072 for -3-large, we just probe on first use.
        self._dim: Optional[int] = None

    @property
    def dim(self) -> int:
        if self._dim is None:
            self.encode(["probe"])
        return self._dim or 0

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        clean = [t.strip() for t in texts if t and t.strip()]
        if not clean:
            return [[] for _ in texts]
        try:
            resp = self._client.embeddings.create(model=self.model, input=clean)
        except Exception as exc:
            log.warning(f"OpenAI embedding call failed: {exc}")
            return [[] for _ in texts]
        vectors = [item.embedding for item in resp.data]
        if vectors and self._dim is None:
            self._dim = len(vectors[0])
        return vectors


class LocalEmbedder:
    def __init__(self, model: str = DEFAULT_LOCAL_MODEL):
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on optional dep
            raise RuntimeError(
                "Local embeddings require 'sentence-transformers'. "
                "Install with: uv add 'sentence-transformers'"
            ) from exc

        self.provider = "local"
        self.model = model or DEFAULT_LOCAL_MODEL
        self._model = SentenceTransformer(self.model)
        self._dim = int(self._model.get_sentence_embedding_dimension() or 0)

    @property
    def dim(self) -> int:
        return self._dim

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        clean = [t.strip() or " " for t in texts]
        vectors = self._model.encode(clean, convert_to_numpy=False, show_progress_bar=False)
        return [list(map(float, v)) for v in vectors]


def build_embedder() -> Optional[Embedder]:
    """Factory that reads settings and returns an Embedder, or None if disabled."""
    backend = (getattr(settings, "embedding_backend", "none") or "none").lower()
    if backend == "none":
        return None

    if backend == "openai":
        api_key = getattr(settings, "openai_api_key", "") or ""
        if not api_key:
            log.warning("Embedding backend=openai but OPENAI_API_KEY is not set. Disabling semantic memory.")
            return None
        model = getattr(settings, "embedding_model", "") or DEFAULT_OPENAI_MODEL
        base_url = getattr(settings, "openai_base_url", "") or None
        try:
            return OpenAIEmbedder(api_key=api_key, model=model, base_url=base_url)
        except Exception as exc:
            log.warning(f"OpenAI embedder init failed: {exc}")
            return None

    if backend == "local":
        model = getattr(settings, "embedding_model", "") or DEFAULT_LOCAL_MODEL
        try:
            return LocalEmbedder(model=model)
        except Exception as exc:
            log.warning(f"Local embedder init failed: {exc}")
            return None

    log.warning(f"Unknown embedding_backend={backend!r}. Disabling semantic memory.")
    return None


async def encode_async(embedder: Embedder, texts: list[str]) -> list[list[float]]:
    """Run a potentially-blocking encode in a thread so it doesn't block the event loop."""
    return await asyncio.to_thread(embedder.encode, texts)
