"""MohaMind CLI banner — Hermes-style wordmark on a solid blue field.

Off-white block letters on the hermes-blue field, chartreuse slogan,
ornament glyphs. The field is the brand; mood only tints the accents.
"""

from rich.console import Group
from rich.text import Text

from moha_mind.cli.themes import (
    HERMES_FG,
    HERMES_ORNAMENT,
    get_theme,
)

_FIELD_BG = "on #0000f2"
_MARGIN = 3  # spaces of blue field left/right of content


def _wordmark_lines() -> list[str]:
    try:
        import pyfiglet  # type: ignore[import-untyped]

        art = pyfiglet.figlet_format("MohaMind", font="ansi_shadow", width=120)
        lines = [line.rstrip() for line in art.split("\n")]
        while lines and not lines[-1].strip():
            lines.pop()
        while lines and not lines[0].strip():
            lines.pop(0)
        if lines:
            return lines
    except Exception:
        pass
    return ["M O H A M I N D"]


def _ascii_title(mood: str = "neutral") -> Text:
    """Render the wordmark on the hermes-blue field."""
    theme = get_theme(mood)
    lines = _wordmark_lines()
    slogan = "your personal agent · always on · always remembering"
    ornament = HERMES_ORNAMENT

    width = max(max(len(line) for line in lines), len(slogan), len(ornament)) + 2 * _MARGIN
    pad = " " * _MARGIN

    def field_row(content: str = "", style: str = HERMES_FG) -> Text:
        row = Text()
        row.append(f"{pad}{content}".ljust(width), style=f"{style} {_FIELD_BG}")
        row.append("\n")
        return row

    result = Text()
    result.append_text(field_row(ornament, style=theme["dim"]))
    result.append_text(field_row())
    for line in lines:
        result.append_text(field_row(line, style=f"bold {HERMES_FG}"))
    result.append_text(field_row())
    result.append_text(field_row(slogan, style=f"italic {theme['accent']}"))
    result.append_text(field_row())
    return result


def build_banner(
    version: str = "0.1.0",
    model: str = "glm-5-turbo",
    provider: str = "zai",
    timezone: str = "Asia/Riyadh",
    tasks_count: int = 0,
    expiring_count: int = 0,
    mood: str = "neutral",
    uptime_hint: str = "",
    telegram_enabled: bool = False,
    google_enabled: bool = False,
    microsoft_enabled: bool = False,
) -> Group:
    theme = get_theme(mood)
    accent = theme["accent"]
    dim = theme["dim"]

    title = _ascii_title(mood)

    # ── Status line ──────────────────────────────────────────────────
    status = Text("  ")
    status.append(provider, style=f"bold {accent}")
    status.append(f"/{model}", style=f"bold {HERMES_FG}")

    status.append("   ")
    if tasks_count:
        status.append(f"{tasks_count} tasks", style=HERMES_FG)
    else:
        status.append("no tasks", style=dim)

    status.append("   ")
    if expiring_count:
        status.append(f"{expiring_count} expiring", style=f"bold {accent}")
    else:
        status.append("nothing expiring", style=dim)

    links = []
    if telegram_enabled:
        links.append("telegram")
    if google_enabled:
        links.append("gcal")
    if microsoft_enabled:
        links.append("outlook")
    if links:
        status.append("   ")
        status.append(" · ".join(links), style=theme["secondary"])

    if uptime_hint:
        status.append("   ")
        status.append(uptime_hint, style=dim)

    status.append(f"   v{version}", style=dim)
    status.append("\n")

    # ── Hint ─────────────────────────────────────────────────────────
    hint = Text("  ")
    for i, cmd in enumerate(["/help", "/majlis", "/radar", "/briefing", "/mcp"]):
        if i:
            hint.append("  ")
        hint.append(cmd, style=f"bold {accent}")
    hint.append("   — or just start talking\n", style=dim)

    return Group(
        Text(),
        title,
        Text(),
        status,
        hint,
    )
