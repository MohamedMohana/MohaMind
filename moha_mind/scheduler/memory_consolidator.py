"""Nightly memory consolidator.

Runs once a day (default 02:30 KSA). Reads:
- The last 24h of daily_log files
- The last 24h of session messages (from SessionStore)

Sends this to the primary LLM and asks it to extract:
- new_facts     -> durable info worth saving in a category
- observations  -> patterns across days (saved to memory/patterns.md)
- conflicts     -> proposed writes that contradict existing memory
- summary       -> a short digest string

Depending on `consolidator_mode`:
- auto    -> applies every proposal immediately
- confirm -> writes nothing, sends everything to Telegram for approval
- hybrid  -> auto-applies safe new_facts/observations, sends conflicts
             and writes to sensitive categories to Telegram

Pending proposals live in `memory/.pending_consolidations.jsonl` so they
survive restarts and can be resolved asynchronously via Telegram callbacks.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Optional

from moha_mind.agent.core import MohaMindAgent
from moha_mind.agent.memory import MEMORY_FILES, MemoryManager
from moha_mind.agent.privacy import PrivacyPolicy
from moha_mind.agent.session_store import SessionStore
from moha_mind.config import settings
from moha_mind.telegram_bot.bot import MohaMindBot
from moha_mind.utils.i18n import agent_language, t
from moha_mind.utils.logging_config import log
from moha_mind.utils.timezone import format_datetime_ar, format_datetime_en, now_ksa

PENDING_FILE = ".pending_consolidations.jsonl"


@dataclass
class Proposal:
    proposal_id: str
    kind: str  # "fact" | "observation" | "conflict"
    category: str
    content: str
    reason: str = ""
    risk: str = "low"  # "low" | "medium" | "high"
    existing_line: str = ""  # only for conflicts
    created_at: str = ""
    status: str = "pending"  # "pending" | "applied" | "rejected"
    metadata: dict = field(default_factory=dict)


EXTRACTION_PROMPT = """You are a careful assistant that distills recent personal data \
into durable, structured memory updates for a personal AI. You MUST only extract facts \
that are clearly stated and worth remembering long-term. Avoid gossip, transient mood \
states, and duplicates of things already in memory.

Return STRICT JSON with this exact shape (no prose, no markdown fences):
{
  "new_facts": [
    {"category": "<one of the allowed categories>",
     "content": "<one line to append, matching the user's language>",
     "reason": "<short why>",
     "risk": "low|medium|high"}
  ],
  "observations": [
    {"content": "<one-line durable pattern>", "reason": "<short why>", "risk": "low|medium|high"}
  ],
  "conflicts": [
    {"category": "<category>", "content": "<proposed update>",
     "existing_line": "<the current memory line it replaces or disagrees with>",
     "reason": "<why>", "risk": "medium|high"}
  ],
  "summary": "<2-3 sentence plain-language digest of what happened>"
}

Allowed categories: profile, family, tasks, occasions, vehicle, finances, health, home,
documents, travel, learning, shopping, relationships, energy_log.

Rules:
- `risk` is "low" for additive facts, "medium" for replacements,
  "high" for sensitive categories (finances/health/documents).
- Never invent facts not present in the input. If nothing is worth saving,
  return empty arrays.
- Match the dominant language of the input (Arabic stays Arabic).
"""


class MemoryConsolidator:
    def __init__(self, agent: MohaMindAgent, memory: MemoryManager, bot: Optional[MohaMindBot] = None):
        self.agent = agent
        self.memory = memory
        self.bot = bot
        self.session_store = SessionStore(memory.memory_path)
        self.pending_path: Path = memory.memory_path / PENDING_FILE

    # ---------------- public entry point ----------------
    async def run(self) -> dict:
        """Main entry point — collects input, calls LLM, applies/queues proposals."""
        if not getattr(settings, "consolidator_enabled", False):
            return {"skipped": True, "reason": "disabled"}

        mode = getattr(settings, "consolidator_mode", "hybrid")
        policy = PrivacyPolicy.from_settings()

        source_text = self._collect_recent()
        if not source_text.strip():
            return {"applied": 0, "queued": 0, "summary": "Nothing to consolidate."}

        extracted = await self._extract(source_text)

        applied: list[Proposal] = []
        queued: list[Proposal] = []

        for fact in extracted.get("new_facts", []):
            prop = Proposal(
                proposal_id=uuid.uuid4().hex[:10],
                kind="fact",
                category=str(fact.get("category", "")).lower().strip(),
                content=str(fact.get("content", "")).strip(),
                reason=str(fact.get("reason", "")),
                risk=str(fact.get("risk", "low")),
                created_at=now_ksa().isoformat(timespec="seconds"),
            )
            if not prop.content or prop.category not in MEMORY_FILES:
                continue
            self._route_proposal(prop, mode=mode, policy=policy, applied=applied, queued=queued)

        for obs in extracted.get("observations", []):
            prop = Proposal(
                proposal_id=uuid.uuid4().hex[:10],
                kind="observation",
                category="patterns",
                content=str(obs.get("content", "")).strip(),
                reason=str(obs.get("reason", "")),
                risk=str(obs.get("risk", "low")),
                created_at=now_ksa().isoformat(timespec="seconds"),
            )
            if not prop.content:
                continue
            self._route_proposal(prop, mode=mode, policy=policy, applied=applied, queued=queued)

        for conflict in extracted.get("conflicts", []):
            prop = Proposal(
                proposal_id=uuid.uuid4().hex[:10],
                kind="conflict",
                category=str(conflict.get("category", "")).lower().strip(),
                content=str(conflict.get("content", "")).strip(),
                reason=str(conflict.get("reason", "")),
                risk=str(conflict.get("risk", "high")),
                existing_line=str(conflict.get("existing_line", "")),
                created_at=now_ksa().isoformat(timespec="seconds"),
            )
            if not prop.content or prop.category not in MEMORY_FILES:
                continue
            # conflicts are never auto-applied
            self._queue(prop)
            queued.append(prop)

        summary = extracted.get("summary", "").strip()
        if getattr(settings, "consolidator_send_digest", True) and self.bot:
            try:
                await self._send_digest(summary, applied, queued)
            except Exception as exc:
                log.warning(f"Consolidator digest send failed: {exc}")

        return {
            "applied": len(applied),
            "queued": len(queued),
            "summary": summary,
            "at": now_ksa().isoformat(timespec="seconds"),
        }

    # ---------------- collection ----------------
    def _collect_recent(self, hours: int = 24) -> str:
        parts: list[str] = []
        today = now_ksa()
        for delta in range(2):
            stamp = (today - timedelta(days=delta)).strftime("%Y-%m-%d")
            path = self.memory.memory_path / "daily_log" / f"{stamp}.md"
            if path.exists():
                parts.append(f"### DAILY LOG {stamp}\n{path.read_text(encoding='utf-8')}")

        cutoff = now_ksa() - timedelta(hours=hours)
        recent = self.session_store.load_since(cutoff)

        if recent:
            dialog_lines = []
            for msg in recent[-100:]:
                role = msg.get("role", "?")
                text = (msg.get("content") or "").strip()
                if text:
                    dialog_lines.append(f"{role}: {text}")
            if dialog_lines:
                parts.append("### RECENT DIALOG\n" + "\n".join(dialog_lines))

        return "\n\n".join(parts)

    # ---------------- extraction ----------------
    async def _extract(self, source_text: str) -> dict:
        try:
            resp = await self.agent._chat_completion_with_fallback(
                messages=[
                    {"role": "system", "content": EXTRACTION_PROMPT},
                    {"role": "user", "content": source_text[:12000]},
                ],
                temperature=0.2,
                max_tokens=1200,
            )
        except Exception as exc:
            log.warning(f"Consolidator LLM call failed: {exc}")
            return {}

        raw = (resp.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:].strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            log.warning(f"Consolidator returned non-JSON: {exc} :: {raw[:200]}")
            return {}

    # ---------------- routing / apply ----------------
    def _route_proposal(
        self,
        proposal: Proposal,
        *,
        mode: str,
        policy: PrivacyPolicy,
        applied: list[Proposal],
        queued: list[Proposal],
    ) -> None:
        sensitive = policy.is_sensitive(proposal.category)
        if mode == "confirm":
            self._queue(proposal)
            queued.append(proposal)
            return
        if mode == "hybrid" and (sensitive or proposal.risk in ("medium", "high")):
            self._queue(proposal)
            queued.append(proposal)
            return
        # auto, or safe hybrid
        self._apply(proposal)
        applied.append(proposal)

    def _apply(self, proposal: Proposal) -> None:
        self.memory.set_write_source("consolidator")
        try:
            if proposal.kind == "observation":
                patterns_path = self.memory.memory_path / "patterns.md"
                existing = patterns_path.read_text(encoding="utf-8") if patterns_path.exists() else "# Patterns\n"
                stamp = now_ksa().strftime("%Y-%m-%d")
                new_content = existing.rstrip() + f"\n- [{stamp}] {proposal.content}\n"
                patterns_path.write_text(new_content, encoding="utf-8")
                self.memory.provenance.record(
                    action="append",
                    category="patterns",
                    before=existing,
                    after=new_content,
                    source="consolidator",
                    details={"proposal_id": proposal.proposal_id, "reason": proposal.reason},
                )
                return

            # fact / low-risk addition
            self.memory.append(proposal.category, f"- {proposal.content}")
        finally:
            self.memory.set_write_source("agent")

    def _queue(self, proposal: Proposal) -> None:
        self.pending_path.parent.mkdir(parents=True, exist_ok=True)
        with self.pending_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(proposal), ensure_ascii=False) + "\n")

    # ---------------- pending queue management ----------------
    def load_pending(self) -> list[Proposal]:
        if not self.pending_path.exists():
            return []
        out: list[Proposal] = []
        for line in self.pending_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                out.append(Proposal(**data))
            except Exception:
                continue
        return [p for p in out if p.status == "pending"]

    def resolve(self, proposal_id: str, *, accept: bool) -> Optional[Proposal]:
        if not self.pending_path.exists():
            return None
        lines = self.pending_path.read_text(encoding="utf-8").splitlines()
        resolved: Optional[Proposal] = None
        new_lines = []
        for raw in lines:
            if not raw.strip():
                continue
            try:
                data = json.loads(raw)
            except Exception:
                new_lines.append(raw)
                continue
            if data.get("proposal_id") == proposal_id and data.get("status") == "pending":
                data["status"] = "applied" if accept else "rejected"
                resolved = Proposal(**data)
                new_lines.append(json.dumps(data, ensure_ascii=False))
                continue
            new_lines.append(raw)

        self.pending_path.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")

        if resolved and accept:
            self._apply(resolved)
        return resolved

    # ---------------- digest ----------------
    async def _send_digest(
        self, summary: str, applied: list[Proposal], queued: list[Proposal]
    ) -> None:
        if not self.bot:
            return
        stamp = now_ksa().strftime("%Y-%m-%d %H:%M")
        when = format_datetime_ar(stamp) if agent_language() == "ar" else format_datetime_en(stamp)
        lines = [t("consolidator.header", when=when)]
        if summary:
            lines.extend(["", summary])
        if applied:
            lines.append("")
            lines.append(t("consolidator.applied"))
            for p in applied[:10]:
                lines.append(f"- [{p.category}] {p.content}")
        if queued:
            lines.append("")
            lines.append(t("consolidator.queued"))
            for p in queued[:10]:
                tag = p.kind.upper()
                lines.append(f"- [{tag} · {p.category}] {p.content}  (id: {p.proposal_id})")

        if len(lines) <= 1:
            return
        await self.bot.send_message("\n".join(lines))
