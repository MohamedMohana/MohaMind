"""Tests for the verifier agent and its integration with the core agent."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from moha_mind.agent.core import MohaMindAgent
from moha_mind.agent.verifier import Verifier, VerifierVerdict


class _FakeCompletions:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        content = self.responses.pop(0) if self.responses else ""
        message = SimpleNamespace(content=content, tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class _FakeClient:
    def __init__(self, completions: _FakeCompletions):
        self.chat = SimpleNamespace(completions=completions)


class TestVerifierVerdict:
    def test_parse_valid_ok_verdict(self):
        verdict = Verifier._parse_verdict(
            '{"ok": true, "severity": "none", "issues": [], "suggestion": ""}'
        )
        assert verdict.ok is True
        assert verdict.severity == "none"
        assert verdict.issues == []

    def test_parse_flagged_verdict(self):
        verdict = Verifier._parse_verdict(
            '{"ok": false, "severity": "high", "issues": ["wrong date"], '
            '"suggestion": "use KSA timezone"}'
        )
        assert verdict.ok is False
        assert verdict.severity == "high"
        assert "wrong date" in verdict.issues
        assert verdict.suggestion == "use KSA timezone"

    def test_parse_invalid_json_accepts(self):
        verdict = Verifier._parse_verdict("not json at all")
        assert verdict.ok is True
        assert verdict.severity == "none"

    def test_parse_json_wrapped_in_prose(self):
        raw = 'Sure thing! {"ok": false, "severity": "medium", "issues": ["tone"], "suggestion": "be warmer"} OK?'
        verdict = Verifier._parse_verdict(raw)
        assert verdict.ok is False
        assert verdict.suggestion == "be warmer"

    def test_parse_normalizes_unknown_severity(self):
        verdict = Verifier._parse_verdict(
            '{"ok": false, "severity": "catastrophic", "issues": [], "suggestion": "fix it"}'
        )
        assert verdict.severity == "none"

    def test_parse_string_issues_becomes_list(self):
        verdict = Verifier._parse_verdict(
            '{"ok": false, "severity": "low", "issues": "wrong tone", "suggestion": "soften"}'
        )
        assert verdict.issues == ["wrong tone"]

    def test_verifier_verdict_accept_default(self):
        v = VerifierVerdict.accept()
        assert v.ok is True
        assert v.severity == "none"


@pytest.fixture
def agent_with_verifier(tmp_memory):
    with patch("moha_mind.agent.core.settings") as mock_settings:
        mock_settings.active_llm_config = {
            "api_key": "primary-key",
            "model": "primary-model",
            "base_url": "https://primary.test",
            "provider": "zai",
        }
        mock_settings.fallback_llm_config = None
        mock_settings.verifier_llm_config = {
            "api_key": "verifier-key",
            "model": "verifier-model",
            "base_url": None,
            "provider": "openai",
        }
        mock_settings.effective_strategy = "verify"
        mock_settings.verifier_strictness = "balanced"
        mock_settings.verifier_max_retries = 1
        with patch("moha_mind.agent.core.AsyncOpenAI"):
            a = MohaMindAgent(tmp_memory)
    return a


class TestAgentVerifierIntegration:
    def test_agent_builds_verifier_when_strategy_is_verify(self, agent_with_verifier):
        assert agent_with_verifier.verifier is not None
        assert agent_with_verifier.verifier.provider == "openai"

    @pytest.mark.asyncio
    async def test_maybe_verify_returns_original_when_verdict_ok(self, agent_with_verifier):
        async def fake_review(*args, **kwargs):
            return VerifierVerdict.accept()

        agent_with_verifier.verifier.review = fake_review

        result = await agent_with_verifier._maybe_verify_and_revise(
            message="Hi",
            current_reply="Hello!",
            conversation=[{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"}],
            system_prompt="sys",
        )
        assert result == "Hello!"

    @pytest.mark.asyncio
    async def test_maybe_verify_regenerates_when_verdict_flagged(self, agent_with_verifier):
        async def fake_review(*args, **kwargs):
            return VerifierVerdict(
                ok=False,
                severity="high",
                issues=["wrong date"],
                suggestion="fix the date",
            )

        agent_with_verifier.verifier.review = fake_review
        agent_with_verifier.client = _FakeClient(_FakeCompletions(["Here's the corrected answer."]))

        conversation = [
            {"role": "user", "content": "When is the meeting?"},
            {"role": "assistant", "content": "Tomorrow at 4."},
        ]

        result = await agent_with_verifier._maybe_verify_and_revise(
            message="When is the meeting?",
            current_reply="Tomorrow at 4.",
            conversation=conversation,
            system_prompt="sys",
        )

        assert result == "Here's the corrected answer."
        # The last assistant turn should have been replaced with the revision
        assert conversation[-1]["content"] == "Here's the corrected answer."

    @pytest.mark.asyncio
    async def test_maybe_verify_swallows_review_crash(self, agent_with_verifier):
        async def boom(*args, **kwargs):
            raise RuntimeError("verifier down")

        agent_with_verifier.verifier.review = boom

        result = await agent_with_verifier._maybe_verify_and_revise(
            message="Hi",
            current_reply="Hello!",
            conversation=[{"role": "assistant", "content": "Hello!"}],
            system_prompt="sys",
        )
        assert result == "Hello!"


@pytest.fixture
def agent_solo(tmp_memory):
    with patch("moha_mind.agent.core.settings") as mock_settings:
        mock_settings.active_llm_config = {
            "api_key": "k",
            "model": "m",
            "base_url": None,
            "provider": "zai",
        }
        mock_settings.fallback_llm_config = None
        mock_settings.verifier_llm_config = None
        mock_settings.effective_strategy = "solo"
        mock_settings.verifier_strictness = "balanced"
        mock_settings.verifier_max_retries = 1
        with patch("moha_mind.agent.core.AsyncOpenAI"):
            a = MohaMindAgent(tmp_memory)
    return a


class TestSoloAgent:
    def test_solo_has_no_verifier(self, agent_solo):
        assert agent_solo.verifier is None

    @pytest.mark.asyncio
    async def test_solo_verify_is_noop(self, agent_solo):
        result = await agent_solo._maybe_verify_and_revise(
            message="Hi",
            current_reply="Hello",
            conversation=[],
            system_prompt="sys",
        )
        assert result == "Hello"
