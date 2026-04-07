"""Telegram message formatters - make output beautiful for Telegram."""


def escape_markdown(text: str) -> str:
    """Escape special MarkdownV2 characters."""
    special = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in text)


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
