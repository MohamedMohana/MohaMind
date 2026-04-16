"""Verifier agent - a second LLM that double-checks the primary agent's replies.

When `LLM_STRATEGY=verify`, MohaMind sends the user question and the primary
agent's final answer to the verifier. The verifier returns structured JSON:

    {
      "ok": true | false,
      "severity": "none" | "low" | "medium" | "high",
      "issues": ["..."],
      "suggestion": "short improvement note or empty string"
    }

If the verifier flags the answer, the primary agent is re-prompted once with
the critique so it can fix the response.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from openai import AsyncOpenAI

from moha_mind.utils.logging_config import log

STRICTNESS_GUIDANCE = {
    "lenient": (
        "Only flag the answer if it contains a clear factual mistake, a hallucinated "
        "date, a wrong memory category, a dangerous instruction, or a missing tool call "
        "that the user explicitly asked for."
    ),
    "balanced": (
        "Flag the answer if it is factually wrong, ignores explicit user instructions, "
        "stores data in the wrong memory category, fabricates times/dates, mixes "
        "Arabic/English awkwardly, or leaves the user's request half-answered."
    ),
    "strict": (
        "Flag the answer for any factual, logical, tone, formatting, language, or "
        "completeness issue — including unnecessary English in Arabic replies, vague "
        "times (e.g. الساعة 4 without صباح/مساء), and missed confirmations."
    ),
}

VERIFIER_SYSTEM_PROMPT = (
    "You are the VERIFIER for MohaMind, a personal AI agent that runs in Saudi Arabia "
    "timezone (Asia/Riyadh) and speaks Arabic + English.\n\n"
    "Your job is to rate the PRIMARY agent's reply to a user message. You do NOT answer "
    "the user yourself. You judge the reply only.\n\n"
    "Output VALID JSON with exactly these keys:\n"
    '- "ok": boolean — true when the reply is acceptable as-is.\n'
    '- "severity": one of "none", "low", "medium", "high".\n'
    '- "issues": array of short strings naming concrete problems (empty array if none).\n'
    '- "suggestion": a single short sentence telling the primary agent how to fix the '
    'reply (empty string if ok).\n\n'
    "Rules:\n"
    "- Never output anything except the JSON object.\n"
    '- Keep issues concrete: "wrong date", "missed the user\'s question about X", etc.\n'
    "- Judge factual correctness, completeness, language match, and tool-choice appropriateness.\n"
    "- If the user wrote in Arabic, the reply should be in Arabic. If the user wrote in "
    "English, reply in English.\n"
    "- Times in 12-hour format should be disambiguated (ص/م or AM/PM).\n"
)


@dataclass
class VerifierConfig:
    api_key: str
    model: str
    base_url: str | None
    provider: str
    strictness: Literal["lenient", "balanced", "strict"] = "balanced"
    max_retries: int = 1


@dataclass
class VerifierVerdict:
    ok: bool
    severity: Literal["none", "low", "medium", "high"]
    issues: list[str]
    suggestion: str
    raw: str = ""

    @classmethod
    def accept(cls) -> "VerifierVerdict":
        return cls(ok=True, severity="none", issues=[], suggestion="", raw="")


class Verifier:
    """Thin wrapper around a secondary LLM that grades primary replies."""

    def __init__(self, config: VerifierConfig):
        self.config = config
        self.client = AsyncOpenAI(api_key=config.api_key, base_url=config.base_url)

    @property
    def provider(self) -> str:
        return self.config.provider

    @property
    def model(self) -> str:
        return self.config.model

    async def review(self, user_message: str, assistant_reply: str, language_hint: str = "auto") -> VerifierVerdict:
        """Ask the verifier to rate an assistant reply. Never raises."""
        if not assistant_reply or not assistant_reply.strip():
            return VerifierVerdict(
                ok=False,
                severity="medium",
                issues=["empty reply"],
                suggestion="Regenerate the reply with real content.",
            )

        guidance = STRICTNESS_GUIDANCE.get(self.config.strictness, STRICTNESS_GUIDANCE["balanced"])
        system_prompt = f"{VERIFIER_SYSTEM_PROMPT}\n\nSTRICTNESS: {guidance}"

        # Privacy: redact sensitive-looking spans before sending to the secondary LLM.
        safe_user = user_message.strip()
        safe_reply = assistant_reply.strip()
        try:
            from moha_mind.agent.privacy import PrivacyPolicy, redact_if

            policy = PrivacyPolicy.from_settings()
            safe_user = redact_if(safe_user, when=policy.redact_in_verifier)
            safe_reply = redact_if(safe_reply, when=policy.redact_in_verifier)
        except Exception as exc:  # pragma: no cover - defensive
            log.debug(f"Verifier privacy redaction skipped: {exc}")

        user_prompt = (
            f"LANGUAGE HINT: {language_hint}\n\n"
            f"USER MESSAGE:\n{safe_user}\n\n"
            f"PRIMARY REPLY:\n{safe_reply}\n\n"
            "Respond with the JSON verdict object."
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=400,
                temperature=0.0,
                response_format={"type": "json_object"},
            )
        except TypeError:
            # Some compat endpoints don't support response_format — retry without it.
            try:
                response = await self.client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=400,
                    temperature=0.0,
                )
            except Exception as exc:
                log.warning(f"Verifier ({self.provider}) call failed: {exc}")
                return VerifierVerdict.accept()
        except Exception as exc:
            log.warning(f"Verifier ({self.provider}) call failed: {exc}")
            return VerifierVerdict.accept()

        content = ""
        try:
            content = (response.choices[0].message.content or "").strip()
        except (AttributeError, IndexError):
            content = ""

        return self._parse_verdict(content)

    @staticmethod
    def _parse_verdict(content: str) -> VerifierVerdict:
        if not content:
            return VerifierVerdict.accept()

        raw = content
        # Try to find a JSON object even if the model wrapped it in prose.
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            content = content[start : end + 1]

        try:
            data: dict[str, Any] = json.loads(content)
        except json.JSONDecodeError:
            log.debug(f"Verifier returned non-JSON response: {raw[:200]}")
            return VerifierVerdict.accept()

        ok = bool(data.get("ok", True))
        severity = str(data.get("severity", "none")).lower()
        if severity not in {"none", "low", "medium", "high"}:
            severity = "none"

        raw_issues = data.get("issues") or []
        if isinstance(raw_issues, str):
            issues = [raw_issues]
        else:
            issues = [str(item).strip() for item in raw_issues if str(item).strip()]

        suggestion = str(data.get("suggestion", "")).strip()

        # If the model said not-ok but gave no suggestion, synthesize one.
        if not ok and not suggestion:
            suggestion = "Please revise the reply to address the issues listed."

        return VerifierVerdict(
            ok=ok,
            severity=severity,  # type: ignore[arg-type]
            issues=issues,
            suggestion=suggestion,
            raw=raw,
        )
