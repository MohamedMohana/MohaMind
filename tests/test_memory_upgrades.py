"""Tests for the memory upgrade stack: privacy, provenance, router,
summarizer, semantic index, consolidator.

Network-dependent pieces (OpenAI embeddings, LLM calls) are covered with
stub doubles so the tests remain fast and offline-safe.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from moha_mind.agent.memory import MemoryManager
from moha_mind.agent.memory_router import MemoryRouter
from moha_mind.agent.memory_summarizer import MemorySummarizer, _heuristic_summary
from moha_mind.agent.privacy import PrivacyPolicy, redact
from moha_mind.agent.provenance import ProvenanceLog
from moha_mind.agent.semantic_index import SemanticIndex
from moha_mind.utils.timezone import now_ksa


@pytest.fixture
def memory(tmp_path):
    return MemoryManager(memory_dir=str(tmp_path))


# ---------- privacy ----------
class TestPrivacy:
    def test_default_sensitive_categories(self, monkeypatch):
        monkeypatch.setattr("moha_mind.agent.privacy.settings.sensitive_categories", "")
        policy = PrivacyPolicy.from_settings()
        assert policy.is_sensitive("finances")
        assert policy.is_sensitive("health")
        assert not policy.is_sensitive("tasks")

    def test_custom_sensitive_categories(self, monkeypatch):
        monkeypatch.setattr("moha_mind.agent.privacy.settings.sensitive_categories", "tasks,profile")
        policy = PrivacyPolicy.from_settings()
        assert policy.is_sensitive("tasks")
        assert policy.is_sensitive("profile")
        assert not policy.is_sensitive("finances")

    def test_redact_amounts(self):
        assert "[amount]" in redact("Salary is 12000 SAR")

    def test_redact_email(self):
        assert "[email]" in redact("reach me at foo@bar.com")

    def test_redact_long_numbers(self):
        out = redact("passport 1234567890")
        # Either [id] or [phone] tag is acceptable; what matters is the digits are gone.
        assert "1234567890" not in out
        assert "[id]" in out or "[phone]" in out

    def test_redact_preserves_short_numbers(self):
        out = redact("three kids aged 3, 5, 7")
        assert "3" in out and "5" in out and "7" in out


# ---------- provenance ----------
class TestProvenance:
    def test_events_are_logged(self, memory):
        memory.write("tasks", "# Tasks\n- [ ] one")
        events = memory.provenance.recent(limit=5)
        assert events
        assert events[-1].category == "tasks"
        assert events[-1].action == "write"

    def test_undo_reverts_last_write(self, memory):
        memory.write("tasks", "# Tasks\n- [ ] first")
        memory.write("tasks", "# Tasks\n- [ ] first\n- [ ] second")
        result = memory.undo_last()
        assert result is not None
        assert result["category"] == "tasks"
        assert "second" not in memory.read("tasks")

    def test_undo_restores_full_snapshot_for_large_memory(self, memory):
        original = "# Family\n" + "\n".join(f"- durable fact {idx}" for idx in range(80))
        memory.write("family", original)
        memory.write("family", "bad overwrite")

        result = memory.undo_last()

        assert result is not None
        restored = memory.read("family")
        assert "bad overwrite" not in restored
        assert "durable fact 79" in restored

    def test_write_records_version_snapshots(self, memory):
        memory.write("family", "first")
        memory.write("family", "second")

        events = memory.provenance.recent(limit=5)

        assert events[-1].details.get("before_snapshot")
        assert events[-1].details.get("after_snapshot")

    def test_undo_with_no_history_returns_none(self, memory):
        assert memory.undo_last() is None

    def test_explain_finds_matching_events(self, memory):
        memory.write("tasks", "# Tasks\n- [ ] buy milk")
        events = memory.explain("tasks", "milk")
        assert events
        assert events[0]["source"] in ("agent", "user")

    def test_source_tagging(self, memory):
        memory.set_write_source("user")
        memory.write("tasks", "- [ ] from user")
        memory.set_write_source("consolidator")
        memory.write("tasks", "- [ ] from consolidator")
        events = memory.provenance.recent(limit=10)
        sources = [ev.source for ev in events[-2:]]
        assert "user" in sources
        assert "consolidator" in sources


class TestProvenanceLog:
    def test_empty_log(self, tmp_path):
        plog = ProvenanceLog(tmp_path)
        assert plog.recent() == []
        assert plog.last_event() is None

    def test_record_and_read_back(self, tmp_path):
        plog = ProvenanceLog(tmp_path)
        plog.record(action="write", category="tasks", before="a", after="a\nb", source="agent")
        plog.record(action="append", category="tasks", before="a\nb", after="a\nb\nc", source="agent")
        events = plog.recent(limit=10)
        assert len(events) == 2
        assert events[-1].action == "append"


# ---------- summarizer ----------
class TestSummarizer:
    def test_heuristic_summary_for_empty(self):
        out = _heuristic_summary("tasks", "")
        assert "empty" in out.lower()

    def test_heuristic_summary_preserves_sections(self):
        content = "# Tasks\n\n## Active\n- buy milk\n- call mom\n\n## Done\n- ship feature"
        out = _heuristic_summary("tasks", content)
        assert "Active" in out or "buy milk" in out

    def test_cached_summary_regenerates_on_mtime_change(self, memory, monkeypatch):
        memory.write("tasks", "# Tasks\n## Active\n- one thing")
        summ = MemorySummarizer(memory)
        first = summ.get_summary("tasks")
        assert first
        memory.write("tasks", "# Tasks\n## Active\n- something totally different")
        second = summ.get_summary("tasks")
        assert second != first


# ---------- router ----------
class TestRouter:
    def test_router_picks_finances_for_money_query(self, memory):
        router = MemoryRouter(memory)
        decision = router.pick("how much did I spend on my salary bill?")
        assert "finances" in decision.categories

    def test_router_bilingual_arabic(self, memory):
        router = MemoryRouter(memory)
        decision = router.pick("ذكرني بكرة الساعة 5")
        assert "reminders" in decision.categories

    def test_router_defaults_when_nothing_matches(self, memory):
        router = MemoryRouter(memory)
        decision = router.pick("xxxxx yyyyy")
        assert decision.method == "default"
        assert "profile" in decision.categories

    def test_router_respects_max_categories(self, memory):
        router = MemoryRouter(memory)
        decision = router.pick("remind me to pay my car insurance for my kid", max_categories=3)
        assert len(decision.categories) <= 3

    def test_router_always_includes_profile(self, memory):
        router = MemoryRouter(memory)
        decision = router.pick("buy milk")
        assert "profile" in decision.categories


# ---------- semantic index ----------
class StubEmbedder:
    """Deterministic stub embedder: maps each character bucket to a dim."""

    provider = "stub"
    model = "stub-1"
    dim = 16

    def encode(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for t in texts:
            vec = [0.0] * self.dim
            for ch in t.lower():
                if ch.isalpha():
                    vec[ord(ch) % self.dim] += 1.0
            norm = sum(v * v for v in vec) ** 0.5 or 1.0
            vec = [v / norm for v in vec]
            vectors.append(vec)
        return vectors


class TestSemanticIndex:
    def test_disabled_when_embedder_is_none(self, memory):
        idx = SemanticIndex(memory, None)
        assert not idx.is_available()
        assert idx.sync() == 0
        assert idx.search("anything") == []

    def test_indexes_and_searches_memory_files(self, memory):
        memory.write("tasks", "# Tasks\n## Active\n- schedule dentist appointment\n- renew vehicle insurance")
        idx = SemanticIndex(memory, StubEmbedder())
        synced = idx.sync()
        assert synced >= 2
        results = idx.search("dentist")
        assert results
        assert any("dentist" in r.chunk for r in results)

    def test_excludes_sensitive_categories_by_default(self, memory):
        memory.write("finances", "# Finances\n## Bills\n- mortgage is 3000 SAR")
        idx = SemanticIndex(memory, StubEmbedder())
        idx.sync()
        results = idx.search("mortgage")
        assert all(r.category != "finances" for r in results)

    def test_sensitive_never_indexed(self, memory):
        """By design, sensitive categories are never added to the embedding store."""
        memory.write("finances", "# Finances\n## Bills\n- mortgage is 3000 SAR")
        idx = SemanticIndex(memory, StubEmbedder())
        idx.sync()
        # Even with include_sensitive=True, nothing was indexed from finances.
        results = idx.search("mortgage", include_sensitive=True)
        assert all(r.category != "finances" for r in results)


# ---------- consolidator (stubbed LLM) ----------
class FakeChoice:
    def __init__(self, content: str):
        self.message = type("M", (), {"content": content})()


class FakeResp:
    def __init__(self, content: str):
        self.choices = [FakeChoice(content)]


class FakeAgent:
    def __init__(self, memory: MemoryManager, payload: dict[str, Any]):
        self.memory = memory
        self._payload = payload

    async def _chat_completion_with_fallback(self, **kwargs):
        return FakeResp(json.dumps(self._payload))


class TestConsolidator:
    def test_applies_safe_facts_in_auto_mode(self, memory, monkeypatch):
        from moha_mind.scheduler.memory_consolidator import MemoryConsolidator

        monkeypatch.setattr("moha_mind.scheduler.memory_consolidator.settings.consolidator_enabled", True)
        monkeypatch.setattr("moha_mind.scheduler.memory_consolidator.settings.consolidator_mode", "auto")
        monkeypatch.setattr("moha_mind.scheduler.memory_consolidator.settings.consolidator_send_digest", False)

        payload = {
            "new_facts": [
                {
                    "category": "tasks",
                    "content": "renew passport next month",
                    "reason": "said last night",
                    "risk": "low",
                }
            ],
            "observations": [],
            "conflicts": [],
            "summary": "",
        }
        cons = MemoryConsolidator(FakeAgent(memory, payload), memory, bot=None)
        # seed a daily log so _collect_recent has input (uses today's date)
        daily = memory.memory_path / "daily_log"
        daily.mkdir(exist_ok=True)
        today = now_ksa().strftime("%Y-%m-%d")
        (daily / f"{today}.md").write_text("the user mentioned renewing their passport\n")

        result = asyncio.run(cons.run())
        assert result["applied"] == 1
        assert "renew passport" in memory.read("tasks")

    def test_queues_conflicts_regardless_of_mode(self, memory, monkeypatch):
        from moha_mind.scheduler.memory_consolidator import MemoryConsolidator

        monkeypatch.setattr("moha_mind.scheduler.memory_consolidator.settings.consolidator_enabled", True)
        monkeypatch.setattr("moha_mind.scheduler.memory_consolidator.settings.consolidator_mode", "auto")
        monkeypatch.setattr("moha_mind.scheduler.memory_consolidator.settings.consolidator_send_digest", False)

        payload = {
            "new_facts": [],
            "observations": [],
            "conflicts": [
                {
                    "category": "profile",
                    "content": "moved to Jeddah",
                    "existing_line": "lives in Riyadh",
                    "reason": "said today",
                    "risk": "high",
                }
            ],
            "summary": "",
        }
        cons = MemoryConsolidator(FakeAgent(memory, payload), memory, bot=None)
        daily = memory.memory_path / "daily_log"
        daily.mkdir(exist_ok=True)
        today = now_ksa().strftime("%Y-%m-%d")
        (daily / f"{today}.md").write_text("moving to Jeddah\n")

        result = asyncio.run(cons.run())
        assert result["applied"] == 0
        assert result["queued"] == 1

        pending = cons.load_pending()
        assert len(pending) == 1
        assert pending[0].kind == "conflict"

        resolved = cons.resolve(pending[0].proposal_id, accept=True)
        assert resolved is not None
        assert "Jeddah" in memory.read("profile")

    def test_hybrid_mode_queues_sensitive_facts(self, memory, monkeypatch):
        from moha_mind.scheduler.memory_consolidator import MemoryConsolidator

        monkeypatch.setattr("moha_mind.scheduler.memory_consolidator.settings.consolidator_enabled", True)
        monkeypatch.setattr("moha_mind.scheduler.memory_consolidator.settings.consolidator_mode", "hybrid")
        monkeypatch.setattr("moha_mind.scheduler.memory_consolidator.settings.consolidator_send_digest", False)

        payload = {
            "new_facts": [{"category": "finances", "content": "raise approved", "reason": "mentioned", "risk": "low"}],
            "observations": [],
            "conflicts": [],
            "summary": "",
        }
        cons = MemoryConsolidator(FakeAgent(memory, payload), memory, bot=None)
        daily = memory.memory_path / "daily_log"
        daily.mkdir(exist_ok=True)
        today = now_ksa().strftime("%Y-%m-%d")
        (daily / f"{today}.md").write_text("got a raise\n")

        result = asyncio.run(cons.run())
        assert result["applied"] == 0
        assert result["queued"] == 1


# ---------- system prompt integration ----------
class TestSystemPromptRouting:
    def test_legacy_behavior_preserved(self, memory):
        from moha_mind.agent.system_prompt import build_system_prompt

        memory.write("tasks", "# Tasks\n- buy milk")
        prompt = build_system_prompt(memory)
        assert "buy milk" in prompt  # legacy dump

    def test_router_expands_only_focus_categories(self, memory):
        from moha_mind.agent.system_prompt import build_system_prompt

        memory.write("tasks", "# Tasks\n- buy milk")
        memory.write("finances", "# Finances\n- salary 12000")
        prompt = build_system_prompt(
            memory,
            focus_categories=["profile", "tasks"],
            summaries={"finances": "salary is tracked monthly"},
        )
        assert "buy milk" in prompt
        assert "12000" not in prompt
        assert "salary is tracked monthly" in prompt
