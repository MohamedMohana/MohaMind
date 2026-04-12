import re
from dataclasses import dataclass
from datetime import datetime

from moha_mind.utils.date_helpers import next_occurrence
from moha_mind.utils.timezone import days_until, now_ksa


@dataclass
class OccasionEntry:
    title: str
    kind: str
    month: int
    day: int
    original_year: int | None
    next_date: datetime
    days_left: int
    source_line: str


def _extract_month_day(line: str) -> tuple[int, int, int | None] | None:
    full_match = re.search(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)", line)
    if full_match:
        year = int(full_match.group(1))
        month = int(full_match.group(2))
        day = int(full_match.group(3))
        return month, day, year

    short_match = re.search(r"(?<!\d)(\d{2})-(\d{2})(?!\d)", line)
    if short_match:
        month = int(short_match.group(1))
        day = int(short_match.group(2))
        return month, day, None

    return None


def _kind_from_section(section: str, line: str) -> str:
    lowered = f"{section} {line}".lower()
    if "birthday" in lowered:
        return "birthday"
    if "annivers" in lowered:
        return "anniversary"
    return "annual_event"


def _title_from_line(line: str) -> str:
    raw = line.lstrip("- ").strip()
    if ":" in raw:
        return raw.split(":", 1)[0].strip()

    cleaned = re.sub(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)", "", raw)
    cleaned = re.sub(r"(?<!\d)\d{2}-\d{2}(?!\d)", "", cleaned)
    cleaned = re.sub(r"\(\s*recurring\s*\)", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" -") or raw


def parse_occasions(content: str, reference: datetime | None = None) -> list[OccasionEntry]:
    if not content.strip():
        return []

    now = reference or now_ksa()
    section = ""
    entries = []

    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("## "):
            section = stripped[3:].strip()
            continue
        if not stripped.startswith("-"):
            continue

        parsed = _extract_month_day(stripped)
        if not parsed:
            continue

        month, day, original_year = parsed
        next_date = next_occurrence(month, day, now)
        entries.append(
            OccasionEntry(
                title=_title_from_line(stripped),
                kind=_kind_from_section(section, stripped),
                month=month,
                day=day,
                original_year=original_year,
                next_date=next_date,
                days_left=days_until(next_date),
                source_line=stripped,
            )
        )

    return sorted(entries, key=lambda item: (item.days_left, item.title.lower()))


def upcoming_occasions(
    content: str,
    days_ahead: int = 30,
    kinds: set[str] | None = None,
    reference: datetime | None = None,
) -> list[OccasionEntry]:
    entries = parse_occasions(content, reference=reference)
    return [
        entry
        for entry in entries
        if 0 <= entry.days_left <= days_ahead and (not kinds or entry.kind in kinds)
    ]
