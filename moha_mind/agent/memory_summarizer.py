"""Rolling per-category memory summaries.

For each memory category (tasks, family, reminders, ...), we keep a short
paragraph summary in `memory/.summaries/<cat>.md`. Summaries are regenerated
on demand when the source file mtime is newer than the summary mtime.

Why: the system prompt used to paste every category in full every turn,
which blows up the token budget as memory grows. With summaries + a
router (see memory_router.py) we only inject summaries by default and
expand the 2-4 most relevant categories in full.

The summarizer tries to use the primary LLM for quality. If the LLM is
unavailable (e.g. tests, no API key), it falls back to a deterministic
heuristic summary built from headings + first bullets.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from moha_mind.agent.memory import MEMORY_FILES, MemoryManager
from moha_mind.config import settings
from moha_mind.utils.logging_config import log

SUMMARIES_DIR = ".summaries"
MAX_SUMMARY_CHARS = 600


@dataclass
class CategorySummary:
    category: str
    text: str
    source_mtime: float
    generated_at: float


def _heuristic_summary(category: str, content: str, max_chars: int = MAX_SUMMARY_CHARS) -> str:
    """Deterministic fallback: pull sections + first bullet per section.

    The result is not brilliant, but it's always available and is small.
    """
    if not content or not content.strip():
        return f"(empty) {category} has no entries yet."

    lines = [line.rstrip() for line in content.splitlines()]
    sections: list[tuple[str, list[str]]] = []
    current_name = "intro"
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if re.match(r"^#{2,6}\s+", stripped):
            if current_lines:
                sections.append((current_name, current_lines))
            current_name = stripped.lstrip("# ").strip()
            current_lines = []
            continue
        if stripped.startswith("# "):
            continue
        if stripped.startswith("<!--") or not stripped:
            continue
        if stripped.startswith("- ") or stripped.startswith("* "):
            current_lines.append(stripped[2:].strip())
        elif stripped.startswith("• "):
            current_lines.append(stripped[2:].strip())
        elif stripped:
            current_lines.append(stripped)
    if current_lines:
        sections.append((current_name, current_lines))

    if not sections:
        trimmed = " ".join(content.split())
        return trimmed[:max_chars]

    parts: list[str] = []
    for name, items in sections:
        if not items:
            continue
        first = items[0]
        extra = f" (+{len(items) - 1} more)" if len(items) > 1 else ""
        parts.append(f"{name}: {first}{extra}".strip())

    summary = "; ".join(parts)
    if len(summary) > max_chars:
        summary = summary[: max_chars - 3].rstrip() + "..."
    return summary


class MemorySummarizer:
    """Generates and caches per-category summaries."""

    def __init__(self, memory: MemoryManager, llm_client=None, llm_model: Optional[str] = None):
        self.memory = memory
        self.dir = memory.memory_path / SUMMARIES_DIR
        self.dir.mkdir(parents=True, exist_ok=True)
        self.llm_client = llm_client
        self.llm_model = llm_model or getattr(settings, "memory_summary_model", "") or ""

    # ------------- public API -------------
    def summary_path(self, category: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9_-]", "_", category)
        return self.dir / f"{safe}.md"

    def meta_path(self, category: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9_-]", "_", category)
        return self.dir / f"{safe}.meta.json"

    def get_summary(self, category: str) -> str:
        """Return the cached summary, regenerating if the source changed."""
        source = self._source_path(category)
        if not source.exists():
            return ""
        cache = self.summary_path(category)
        source_text = source.read_text(encoding="utf-8")
        if cache.exists() and self._cache_matches_source(category, source_text):
            return cache.read_text(encoding="utf-8").strip()
        text = _heuristic_summary(category, source_text)
        self._write_cache(category, text, source_text=source_text)
        return text

    def get_summaries(self, categories: list[str]) -> dict[str, str]:
        return {cat: self.get_summary(cat) for cat in categories if self.get_summary(cat)}

    def invalidate(self, category: str) -> None:
        path = self.summary_path(category)
        if path.exists():
            path.unlink()
        meta = self.meta_path(category)
        if meta.exists():
            meta.unlink()

    async def refresh_async(self, category: str) -> str:
        """Regenerate a summary, preferring the LLM when available."""
        source = self._source_path(category)
        if not source.exists():
            return ""
        content = source.read_text(encoding="utf-8")
        text = await self._llm_summary(category, content) if self.llm_client else ""
        if not text:
            text = _heuristic_summary(category, content)
        self._write_cache(category, text, source_text=content)
        return text

    async def refresh_all_async(self) -> dict[str, str]:
        tasks = [self.refresh_async(cat) for cat in MEMORY_FILES.keys()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        out: dict[str, str] = {}
        for cat, result in zip(MEMORY_FILES.keys(), results):
            if isinstance(result, Exception):
                log.debug(f"Summary refresh failed for {cat}: {result}")
                continue
            if result:
                out[cat] = result
        return out

    # ------------- internals -------------
    def _source_path(self, category: str) -> Path:
        filename = MEMORY_FILES.get(category, f"{category}.md")
        return self.memory.memory_path / filename

    def _source_fingerprint(self, content: str) -> str:
        return hashlib.sha1(content.encode("utf-8")).hexdigest()

    def _cache_matches_source(self, category: str, source_text: str) -> bool:
        meta = self.meta_path(category)
        if not meta.exists():
            return False
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return data.get("source_hash") == self._source_fingerprint(source_text)

    def _write_cache(self, category: str, text: str, source_text: str | None = None) -> None:
        path = self.summary_path(category)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.strip() + "\n", encoding="utf-8")
        if source_text is not None:
            self.meta_path(category).write_text(
                json.dumps({"source_hash": self._source_fingerprint(source_text)}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    async def _llm_summary(self, category: str, content: str) -> str:
        if not self.llm_client:
            return ""
        prompt = (
            f"Summarize this '{category}' memory file into ONE short paragraph (max 80 words). "
            f"Focus on durable facts, dates, and patterns — skip template comments. "
            f"Match the user's language (Arabic stays Arabic). No lists, no markdown.\n\n"
            f"FILE CONTENT:\n{content[:4000]}"
        )
        try:
            resp = await self.llm_client.chat.completions.create(
                model=self.llm_model or "gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a terse, accurate memory summarizer."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=220,
            )
            content_out = (resp.choices[0].message.content or "").strip()
            return content_out[:MAX_SUMMARY_CHARS]
        except Exception as exc:
            log.debug(f"LLM summary failed for {category}: {exc}")
            return ""
