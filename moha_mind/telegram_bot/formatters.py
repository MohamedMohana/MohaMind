"""Telegram message formatters - make output beautiful for Telegram."""

import re

from telegram.constants import ParseMode
from telegram.helpers import escape_markdown as telegram_escape_markdown


def escape_markdown(text: str) -> str:
    """Escape special MarkdownV2 characters."""
    return telegram_escape_markdown(text, version=2)


def _format_inline_markdown_v2(text: str) -> str:
    parts = re.split(r"(\*\*[^*\n]+\*\*|__[^_\n]+__)", text)
    formatted = []
    for part in parts:
        if not part:
            continue
        if (part.startswith("**") and part.endswith("**")) or (part.startswith("__") and part.endswith("__")):
            formatted.append(f"*{escape_markdown(part[2:-2])}*")
        else:
            formatted.append(escape_markdown(part))
    return "".join(formatted)


def format_telegram_markdown(text: str) -> str:
    """Convert a safe subset of common Markdown to Telegram MarkdownV2."""
    lines = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            lines.append("")
            continue

        heading = re.match(r"^#{1,6}\s+(.+)$", stripped)
        if heading:
            lines.append(f"*{escape_markdown(heading.group(1).strip())}*")
            continue

        unordered = re.match(r"^[-*]\s+(.+)$", stripped)
        if unordered:
            lines.append(f"• {_format_inline_markdown_v2(unordered.group(1))}")
            continue

        ordered = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if ordered:
            lines.append(f"{ordered.group(1)}\\. {_format_inline_markdown_v2(ordered.group(2))}")
            continue

        lines.append(_format_inline_markdown_v2(raw_line))

    return "\n".join(lines)


async def reply_markdown(message, text: str) -> None:
    """Reply using MarkdownV2 with a plain-text fallback."""
    if not text or not text.strip():
        return

    try:
        await message.reply_text(format_telegram_markdown(text), parse_mode=ParseMode.MARKDOWN_V2)
    except Exception:
        await message.reply_text(text)


def format_briefing(text: str) -> str:
    """Format a morning briefing for Telegram."""
    text = text.replace("**", "*").replace("__", "_")
    lines = text.split("\n")
    formatted = []
    for line in lines:
        if line.strip().startswith("#"):
            formatted.append(f"\n*{line.strip('# ').strip()}*\n")
        elif line.strip().startswith("-"):
            formatted.append(f"  {line}")
        else:
            formatted.append(line)
    return "\n".join(formatted)


def format_task_list(tasks_text: str) -> str:
    """Format task list for Telegram."""
    return tasks_text


def format_expiry_alert(items_text: str) -> str:
    """Format expiry alert for Telegram with urgency."""
    lines = items_text.split("\n")
    formatted = []
    for line in lines:
        if "[0d]" in line or "[1d]" in line:
            formatted.append(f"🔴 URGENT: {line}")
        elif any(f"[{d}d]" in line for d in range(2, 8)):
            formatted.append(f"🟡 {line}")
        else:
            formatted.append(f"🟢 {line}")
    return "\n".join(formatted)


def truncate_message(text: str, max_length: int = 4096) -> list[str]:
    """Split long messages for Telegram's 4096 char limit."""
    if len(text) <= max_length:
        return [text]

    parts = []
    while text:
        if len(text) <= max_length:
            parts.append(text)
            break

        split_at = text.rfind("\n", 0, max_length)
        if split_at == -1:
            split_at = max_length

        parts.append(text[:split_at])
        text = text[split_at:].lstrip("\n")

    return parts
