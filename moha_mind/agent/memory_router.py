"""Memory Router — picks which categories are most relevant to a user message.

The router avoids dumping every category into the system prompt. Given a user
message, it returns the top-K categories to expand in full. Other categories
contribute only their short summary (see memory_summarizer.py).

Two-tier design:
1. Deterministic keyword/regex signals (cheap, works offline, bilingual).
2. Optional LLM-assisted tie-breaker when keywords don't give enough signal.

Scoring is additive and tolerates noisy inputs. When in doubt we return
defaults so the agent never loses critical context like profile/tasks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional

from moha_mind.agent.memory import MEMORY_FILES, MemoryManager
from moha_mind.utils.logging_config import log

# Bilingual keyword cues for each category. The lists are intentionally
# narrow — quality over recall. Anything ambiguous goes through the tie-breaker.
CATEGORY_CUES: dict[str, list[str]] = {
    "profile": [
        "me", "myself", "my name", "my birthday", "my age", "my job", "my work",
        "أنا", "عن نفسي", "اسمي", "عمري", "ميلادي", "شغلي", "وظيفتي",
    ],
    "family": [
        "wife", "husband", "son", "daughter", "kid", "child", "family", "pregnan",
        "زوجتي", "زوجي", "ابني", "بنتي", "عائلة", "أهل", "حامل", "حمل",
    ],
    "tasks": [
        "task", "todo", "to-do", "remind me to", "need to", "have to", "must do",
        "مهمة", "مهام", "لازم", "يجب", "أبغى أسوي",
    ],
    "reminders": [
        "remind", "reminder", "at ", "tomorrow", "tonight", "today",
        "ذكرني", "تذكير", "بكرة", "بكره", "اليوم", "الليلة", "الساعة",
    ],
    "occasions": [
        "birthday", "anniversary", "wedding", "celebration", "occasion",
        "عيد ميلاد", "ذكرى", "زواج", "مناسبة",
    ],
    "vehicle": [
        "car", "vehicle", "insurance", "plate", "service", "mileage", "tires",
        "سيارة", "سيارتي", "تأمين", "لوحة", "صيانة", "كيلومتر", "كفرات",
    ],
    "finances": [
        "salary", "bill", "rent", "invoice", "subscription", "bank", "payment",
        "SAR", "ريال", "فلوس", "راتب", "فاتورة", "إيجار", "اشتراك", "بنك", "دفع",
    ],
    "health": [
        "doctor", "medicine", "pill", "clinic", "hospital", "gym", "workout",
        "دكتور", "طبيب", "دواء", "حبوب", "عيادة", "مستشفى", "نادي", "جيم", "تمرين",
    ],
    "home": [
        "home", "apartment", "rent", "appliance", "utility", "maintenance",
        "بيت", "منزل", "شقة", "أجار", "صيانة", "غسالة", "مكيف",
    ],
    "documents": [
        "passport", "id", "license", "visa", "expire", "renew",
        "جواز", "هوية", "رخصة", "تأشيرة", "ينتهي", "تجديد",
    ],
    "travel": [
        "trip", "flight", "travel", "hotel", "visa", "booking",
        "سفر", "رحلة", "طيران", "فندق", "حجز",
    ],
    "learning": [
        "learn", "course", "book", "study", "certificate", "cert",
        "تعلم", "دورة", "كتاب", "دراسة", "شهادة",
    ],
    "shopping": [
        "buy", "shop", "store", "order", "size",
        "أشتري", "اشتري", "سوق", "متجر", "مقاس",
    ],
    "relationships": [
        "friend", "colleague", "contact", "called", "met",
        "صديق", "زميل", "اتصلت", "قابلت",
    ],
    "energy_log": [
        "tired", "energetic", "mood", "sleep", "sleepy",
        "تعبان", "نشيط", "مزاج", "نعسان",
    ],
}

# Categories we ALWAYS include in full so the agent never loses these facts.
ALWAYS_INCLUDE = ("profile",)
# Fallback set when nothing scores — gives the agent a sensible default view.
DEFAULT_FALLBACK = ("profile", "tasks", "reminders", "occasions")


@dataclass
class RouterDecision:
    categories: list[str]
    scores: dict[str, float]
    method: str  # "heuristic" | "llm" | "default"


class MemoryRouter:
    """Lightweight category selector for system prompt assembly."""

    def __init__(self, memory: MemoryManager, llm_client=None, llm_model: Optional[str] = None):
        self.memory = memory
        self.llm_client = llm_client
        self.llm_model = llm_model or ""
        self._compiled: dict[str, list[re.Pattern[str]]] = {
            cat: [self._compile_cue(cue) for cue in cues] for cat, cues in CATEGORY_CUES.items()
        }

    @staticmethod
    def _compile_cue(cue: str) -> re.Pattern[str]:
        # Word-ish boundary for ASCII; literal match for non-ASCII (Arabic).
        if re.fullmatch(r"[\w\s\-]+", cue, flags=re.ASCII):
            return re.compile(rf"(?i)\b{re.escape(cue)}\b")
        return re.compile(re.escape(cue))

    def pick(self, message: str, *, max_categories: int = 4) -> RouterDecision:
        """Return the ordered list of categories worth expanding in full."""
        scores = self._score_message(message or "")
        ranked = [cat for cat, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True) if scores[cat] > 0]

        chosen = list(dict.fromkeys(list(ALWAYS_INCLUDE) + ranked))[:max_categories]
        method = "heuristic" if ranked else "default"
        if not ranked:
            chosen = list(dict.fromkeys(list(ALWAYS_INCLUDE) + list(DEFAULT_FALLBACK)))[:max_categories]

        return RouterDecision(categories=chosen, scores=scores, method=method)

    def _score_message(self, message: str) -> dict[str, float]:
        scores: dict[str, float] = {cat: 0.0 for cat in CATEGORY_CUES}
        if not message or not message.strip():
            return scores

        for cat, patterns in self._compiled.items():
            for pat in patterns:
                hits = len(pat.findall(message))
                if hits:
                    scores[cat] += hits
        return scores

    async def pick_async(self, message: str, *, max_categories: int = 4) -> RouterDecision:
        """Async variant that can optionally consult the LLM for tie-breaking."""
        decision = self.pick(message, max_categories=max_categories)
        if decision.method != "default" or not self.llm_client:
            return decision

        try:
            llm_choice = await self._llm_tiebreak(message, max_categories)
        except Exception as exc:
            log.debug(f"LLM router tie-break failed: {exc}")
            return decision

        if llm_choice:
            categories = list(dict.fromkeys(list(ALWAYS_INCLUDE) + llm_choice))[:max_categories]
            return RouterDecision(categories=categories, scores=decision.scores, method="llm")
        return decision

    async def _llm_tiebreak(self, message: str, max_categories: int) -> Iterable[str]:
        known = ", ".join(MEMORY_FILES.keys())
        prompt = (
            f"The user said: {message!r}\n"
            f"Pick up to {max_categories} memory categories that are MOST relevant from this list: {known}.\n"
            "Return ONLY a comma-separated list of category names, no explanation."
        )
        resp = await self.llm_client.chat.completions.create(
            model=self.llm_model or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a precise memory router."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=60,
        )
        raw = (resp.choices[0].message.content or "").strip()
        picks = [tok.strip().lower() for tok in re.split(r"[,;\n]", raw) if tok.strip()]
        return [p for p in picks if p in MEMORY_FILES]
