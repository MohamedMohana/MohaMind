"""Telegram message formatters - convert Markdown-ish LLM output to safe Telegram HTML.

Telegram supports two parse modes: MarkdownV2 and HTML. HTML is used here because:
- It doesn't require escaping `.`, `-`, `!`, `(`, `)`, `|`, etc.
- Arabic, emoji, and 12-hour times render without breakage.
- Tables and lists can be rendered cleanly without fighting parser rules.

Only `&`, `<`, `>` need escaping in HTML mode.
"""

from __future__ import annotations

import html
import re

from telegram.constants import ParseMode
from telegram.helpers import escape_markdown as telegram_escape_markdown

_CODE_PLACEHOLDER = "\x00CODE{}\x00"
_CODE_PLACEHOLDER_RE = re.compile(r"\x00CODE(\d+)\x00")


def escape_markdown(text: str) -> str:
    """Escape special MarkdownV2 characters (kept for callers that build raw MarkdownV2)."""
    return telegram_escape_markdown(text, version=2)


def escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram HTML parse mode."""
    return html.escape(text, quote=False)


def _format_inline_html(text: str) -> str:
    """Convert inline Markdown (bold, italic, code) inside a single line to HTML."""
    code_chunks: list[str] = []

    def _stash_code(match: re.Match[str]) -> str:
        code_chunks.append(match.group(1))
        return _CODE_PLACEHOLDER.format(len(code_chunks) - 1)

    text = re.sub(r"`([^`\n]+?)`", _stash_code, text)
    text = escape_html(text)

    text = re.sub(r"\*\*([^*\n]+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__([^_\n]+?)__", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*([^*\n]+?)\*(?![\w*])", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w_])_([^_\n]+?)_(?![\w_])", r"<i>\1</i>", text)

    def _restore_code(match: re.Match[str]) -> str:
        idx = int(match.group(1))
        return f"<code>{escape_html(code_chunks[idx])}</code>"

    return _CODE_PLACEHOLDER_RE.sub(_restore_code, text)


def _is_table_separator(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if "---" not in stripped and "—" not in stripped and "–" not in stripped:
        return False
    cleaned = re.sub(r"[|\-:\s—–]", "", stripped)
    return cleaned == ""


def _split_table_row(line: str) -> list[str]:
    row = line.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [cell.strip() for cell in row.split("|")]


def _detect_table(lines: list[str], start: int) -> tuple[list[list[str]] | None, int]:
    """Detect a Markdown pipe table starting at lines[start]. Return (rows, consumed)."""
    if start + 1 >= len(lines):
        return None, 0
    first = lines[start].strip()
    second = lines[start + 1].strip()
    if not (first.startswith("|") and "|" in first[1:]):
        return None, 0
    if not _is_table_separator(second):
        return None, 0

    rows = [_split_table_row(first)]
    consumed = 2
    for idx in range(start + 2, len(lines)):
        line = lines[idx].strip()
        if not line.startswith("|"):
            break
        rows.append(_split_table_row(line))
        consumed += 1
    return rows, consumed


def _render_table(rows: list[list[str]]) -> list[str]:
    """Render a Markdown table as clean labeled lines. Telegram has no real table support."""
    if len(rows) < 2:
        return []
    header = rows[0]
    rendered: list[str] = []
    for data_row in rows[1:]:
        parts = []
        for i, cell in enumerate(data_row):
            cell_text = cell.strip()
            if not cell_text:
                continue
            label = header[i].strip() if i < len(header) else ""
            if label:
                parts.append(f"<b>{_format_inline_html(label)}:</b> {_format_inline_html(cell_text)}")
            else:
                parts.append(_format_inline_html(cell_text))
        if parts:
            rendered.append("• " + " — ".join(parts))
    return rendered


def format_telegram_html(text: str) -> str:
    """Convert LLM Markdown output into Telegram-safe HTML."""
    if not text:
        return ""

    lines = text.splitlines()
    output: list[str] = []
    i = 0
    in_code_block = False
    code_buffer: list[str] = []

    while i < len(lines):
        raw_line = lines[i]
        stripped = raw_line.strip()

        fence = re.match(r"^```(\w*)\s*$", stripped)
        if fence:
            if in_code_block:
                output.append("<pre>" + escape_html("\n".join(code_buffer)) + "</pre>")
                code_buffer = []
                in_code_block = False
            else:
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            code_buffer.append(raw_line)
            i += 1
            continue

        if stripped.startswith("|") and "|" in stripped[1:]:
            rows, consumed = _detect_table(lines, i)
            if rows and consumed >= 2:
                output.extend(_render_table(rows))
                i += consumed
                continue

        if not stripped:
            output.append("")
            i += 1
            continue

        if re.match(r"^[-*_]{3,}$", stripped):
            output.append("────────")
            i += 1
            continue

        heading = re.match(r"^#{1,6}\s+(.+)$", stripped)
        if heading:
            output.append(f"<b>{_format_inline_html(heading.group(1).strip())}</b>")
            i += 1
            continue

        unordered = re.match(r"^[-*+]\s+(.+)$", stripped)
        if unordered:
            output.append(f"• {_format_inline_html(unordered.group(1))}")
            i += 1
            continue

        ordered = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if ordered:
            output.append(f"{ordered.group(1)}. {_format_inline_html(ordered.group(2))}")
            i += 1
            continue

        output.append(_format_inline_html(raw_line))
        i += 1

    if in_code_block and code_buffer:
        output.append("<pre>" + escape_html("\n".join(code_buffer)) + "</pre>")

    return "\n".join(output).rstrip() + ("\n" if output and output[-1] == "" else "")


def format_telegram_markdown(text: str) -> str:
    """Back-compat alias. Prefer ``format_telegram_html`` for new code."""
    return format_telegram_html(text)


async def reply_markdown(message, text: str) -> None:
    """Reply using Telegram HTML with a plain-text fallback."""
    if not text or not text.strip():
        return

    html_text = format_telegram_html(text)
    try:
        await message.reply_text(html_text, parse_mode=ParseMode.HTML)
        return
    except Exception:
        pass

    try:
        await message.reply_text(_strip_html(html_text))
    except Exception:
        await message.reply_text(text)


def _strip_html(text: str) -> str:
    """Best-effort HTML stripper for the plain-text fallback path."""
    stripped = re.sub(r"<[^>]+>", "", text)
    return html.unescape(stripped)


def format_briefing(text: str) -> str:
    """Format a morning briefing for Telegram HTML."""
    return format_telegram_html(text)


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
