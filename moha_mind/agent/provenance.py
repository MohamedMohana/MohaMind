"""Provenance & undo for MohaMind memory.

Every mutation to a memory file is appended to an append-only JSONL log
at `memory/.history.jsonl`. This enables:
- /undo to reverse the last change
- /why to show who/when/how a line got there
- Conflict detection (two writes of the same fact across time)

The log is intentionally independent of the markdown — the markdown
remains the source of truth, and history is append-only auditable metadata.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from moha_mind.utils.logging_config import log
from moha_mind.utils.timezone import now_ksa

HISTORY_FILENAME = ".history.jsonl"


@dataclass
class MemoryEvent:
    event_id: str
    timestamp: str
    action: str  # "write" | "append" | "append_section" | "delete_line" | "delete_matches" | "delete_note"
    category: str
    source: str  # "user" | "agent" | "consolidator" | "import" | "manual"
    before_hash: str
    after_hash: str
    before_snippet: str
    after_snippet: str
    details: dict

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def _hash(content: str) -> str:
    return hashlib.sha1((content or "").encode("utf-8")).hexdigest()[:12]


def _snippet(content: str, limit: int = 400) -> str:
    clean = content or ""
    if len(clean) <= limit:
        return clean
    return clean[:limit] + "..."


class ProvenanceLog:
    """Append-only log of memory mutations, used for /undo and /why."""

    def __init__(self, memory_path: Path):
        self.memory_path = Path(memory_path)
        self.log_path = self.memory_path / HISTORY_FILENAME

    def record(
        self,
        *,
        action: str,
        category: str,
        before: str,
        after: str,
        source: str = "agent",
        details: Optional[dict] = None,
    ) -> MemoryEvent:
        event = MemoryEvent(
            event_id=uuid.uuid4().hex[:12],
            timestamp=now_ksa().isoformat(timespec="seconds"),
            action=action,
            category=category,
            source=source,
            before_hash=_hash(before),
            after_hash=_hash(after),
            before_snippet=_snippet(before),
            after_snippet=_snippet(after),
            details=details or {},
        )
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(event.to_json() + "\n")
        except Exception as exc:
            log.warning(f"Failed to write provenance event: {exc}")
        return event

    def recent(self, limit: int = 20) -> list[MemoryEvent]:
        if not self.log_path.exists():
            return []
        try:
            lines = self.log_path.read_text(encoding="utf-8").splitlines()
        except Exception as exc:
            log.warning(f"Failed to read provenance log: {exc}")
            return []

        events: list[MemoryEvent] = []
        for raw in lines[-limit * 2 :]:
            if not raw.strip():
                continue
            try:
                data = json.loads(raw)
                events.append(MemoryEvent(**data))
            except (json.JSONDecodeError, TypeError) as exc:
                log.debug(f"Skipping malformed provenance line: {exc}")
        return events[-limit:]

    def last_event(self) -> Optional[MemoryEvent]:
        events = self.recent(limit=1)
        return events[0] if events else None

    def find_for_line(self, category: str, text_fragment: str, limit: int = 5) -> list[MemoryEvent]:
        """Find recent events for a category whose snippet contains the fragment."""
        fragment = text_fragment.lower().strip()
        if not fragment:
            return []
        results = []
        for event in self.recent(limit=200):
            if event.category != category:
                continue
            haystack = (event.after_snippet or "") + "\n" + (event.before_snippet or "")
            if fragment in haystack.lower():
                results.append(event)
                if len(results) >= limit:
                    break
        return results
