"""Helpers for colloquial Arabic normalization and interpretation hints."""

import re

ARABIC_DIGIT_TRANSLATION = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
    "01234567890123456789",
)

MORNING_TERMS = {"الصبح", "الصباح", "الفجر"}
AFTERNOON_EVENING_TERMS = {"العصر", "المسا", "المساء", "بعد الظهر"}


def contains_arabic(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06FF]", text))


def _normalize_time_period_phrases(text: str, notes: list[str]) -> str:
    pattern = re.compile(
        r"(?:(?:الساعة)\s*)?(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<period>الصبح|الصباح|الفجر|العصر|المسا|المساء|بعد\s+الظهر)"
    )

    def replacer(match: re.Match[str]) -> str:
        raw_hour = int(match.group("hour"))
        raw_minute = int(match.group("minute") or "0")
        period = re.sub(r"\s+", " ", match.group("period")).strip()

        if period in MORNING_TERMS:
            hour_24 = 0 if raw_hour == 12 else raw_hour
        elif period in AFTERNOON_EVENING_TERMS:
            hour_24 = raw_hour if raw_hour == 12 else raw_hour + 12
        else:
            return match.group(0)

        converted = f"الساعة {hour_24:02d}:{raw_minute:02d}"
        note = f"Time phrase '{match.group(0)}' should be interpreted as {hour_24:02d}:{raw_minute:02d}."
        if note not in notes:
            notes.append(note)
        return converted

    return pattern.sub(replacer, text)


def normalize_colloquial_arabic(text: str) -> tuple[str, list[str]]:
    normalized = text.translate(ARABIC_DIGIT_TRANSLATION)
    notes: list[str] = []

    if normalized != text:
        notes.append("Arabic digits such as ٧ and ١٤ should be interpreted as 7 and 14.")

    replacements = [
        (
            r"بعد\s+(?:بكره|بكرة|بكرا)",
            "بعد غد",
            "The phrase 'بعد بكره/بكرا' means the day after tomorrow.",
        ),
        (
            r"(?:عقب|ورا|ورى)\s+(?:بكره|بكرة|بكرا)",
            "بعد غد",
            "The phrase 'عقب بكره/ورا بكره' means the day after tomorrow.",
        ),
        (
            r"(?:بكره|بكرة|بكرا)",
            "غدا",
            "The phrase 'بكره/بكرا' means tomorrow.",
        ),
        (
            r"يوم\s+(?:نعم|ايه|أيه|ايوه|أيوه)\s+ويوم\s+لا",
            "كل يومين",
            "The phrase 'يوم نعم ويوم لا' means every two days.",
        ),
        (
            r"يوم\s+ورا\s+يوم",
            "كل يومين",
            "The phrase 'يوم ورا يوم' means every two days.",
        ),
        (
            r"الساعه",
            "الساعة",
            "The phrase 'الساعه' should be read as 'الساعة'.",
        ),
    ]

    for pattern, replacement, note in replacements:
        if re.search(pattern, normalized):
            normalized = re.sub(pattern, replacement, normalized)
            if note not in notes:
                notes.append(note)

    normalized = _normalize_time_period_phrases(normalized, notes)
    normalized = re.sub(r"-{2,}", "-", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized, notes


def build_arabic_understanding_context(text: str) -> str:
    if not contains_arabic(text):
        return ""

    normalized, notes = normalize_colloquial_arabic(text)
    lines = [
        "### COLLOQUIAL ARABIC INTERPRETATION",
        "The user may be speaking in Saudi/Gulf dialect. Understand it naturally and do not ask for formal Arabic.",
    ]

    if normalized != text.strip():
        lines.append(f"- normalized reading: {normalized}")

    for note in notes:
        lines.append(f"- {note}")

    return "\n".join(lines)
