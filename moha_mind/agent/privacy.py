"""Privacy tiers for MohaMind memory.

Defines which memory categories are "sensitive" and provides helpers to
redact content before it leaves the primary agent — e.g. before the
verifier sees it, before it goes into the session store, or before a
daily log captures it.

Design:
- Sensitivity is defined per category, not per line.
- Redaction is conservative: we keep the shape of the text but replace
  likely sensitive spans (numbers, amounts, document IDs) with tokens.
- None of this is cryptography — it only reduces accidental leakage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from moha_mind.config import settings

DEFAULT_SENSITIVE_CATEGORIES = ("finances", "health", "documents")


@dataclass(frozen=True)
class PrivacyPolicy:
    sensitive_categories: frozenset[str]
    redact_in_sessions: bool
    redact_in_verifier: bool
    redact_in_daily_log: bool

    @classmethod
    def from_settings(cls) -> "PrivacyPolicy":
        raw = getattr(settings, "sensitive_categories", "") or ""
        if isinstance(raw, str):
            parsed = [item.strip().lower() for item in raw.split(",") if item.strip()]
        else:
            parsed = [str(item).strip().lower() for item in raw if str(item).strip()]
        categories = frozenset(parsed) if parsed else frozenset(DEFAULT_SENSITIVE_CATEGORIES)

        return cls(
            sensitive_categories=categories,
            redact_in_sessions=bool(getattr(settings, "privacy_redact_sessions", True)),
            redact_in_verifier=bool(getattr(settings, "privacy_redact_verifier", True)),
            redact_in_daily_log=bool(getattr(settings, "privacy_redact_daily_log", True)),
        )

    def is_sensitive(self, category: str) -> bool:
        return category.lower() in self.sensitive_categories


_AMOUNT_RE = re.compile(r"\b\d{3,}(?:[.,]\d{1,3})?\s?(?:SAR|USD|EUR|ريال|\$|€)?\b", re.IGNORECASE)
_LONG_DIGITS_RE = re.compile(r"\b\d{6,}\b")  # IDs, account numbers, passport numbers
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s-]{7,})")


def redact(text: str) -> str:
    """Return a version of text with sensitive-looking spans replaced by tags.

    This is a conservative heuristic — it does NOT guarantee full redaction.
    It is used on content that will leave the primary agent (verifier,
    session store, daily log) so accidental leakage is reduced.
    """
    if not text:
        return text
    out = _EMAIL_RE.sub("[email]", text)
    out = _PHONE_RE.sub(lambda m: "[phone]" if sum(ch.isdigit() for ch in m.group(0)) >= 8 else m.group(0), out)
    out = _LONG_DIGITS_RE.sub("[id]", out)
    out = _AMOUNT_RE.sub("[amount]", out)
    return out


def redact_if(text: str, *, when: bool) -> str:
    """Shortcut: redact only when `when` is True."""
    if not when:
        return text
    return redact(text)


def summarize_sensitive(text: str, max_len: int = 80) -> str:
    """Return a short privacy-safe placeholder used when a full redaction is too noisy."""
    redacted = redact(text or "")
    cleaned = " ".join(redacted.split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3].rstrip() + "..."
