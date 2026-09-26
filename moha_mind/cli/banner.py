"""MohaMind CLI banner — Hermes wordmark on a chartreuse field, with a brain.

Hermes-blue block letters on the chartreuse field, plus a pixel-art brain
rendered with truecolor half-blocks. On startup the brain plays a short
"neurons firing" animation (see animate_banner); the field is the brand,
mood only tints details.
"""

import random
import time

from rich.console import Group
from rich.text import Text

from moha_mind import __version__
from moha_mind.cli.themes import HERMES_ORNAMENT

_FIELD = "#edff45"  # chartreuse field
_INK = "#0000f2"  # hermes blue ink on the field
_INK_SOFT = "#5a5acc"
_FIELD_BG = f"on {_FIELD}"
_MARGIN = 3  # spaces of field left/right of content
_GAP = 2  # spaces between wordmark and brain

# ── Pixel-art brain (side view) ──────────────────────────────────────────────
# '.' = field, 'o' = outline/fold, '#' = body (blue→purple gradient by column),
# 'p' = purple lobe, 'c' = cerebellum, 's' = brainstem.
_BRAIN_GRID = [
    "......oooo....ooooo.......",
    "....oo####oooo#####oo.....",
    "...o########o#######ppo...",
    "..o##oooo###o##oooo##ppo..",
    ".o##########o########pppo.",
    ".o##oooo##o####oooo##pppo.",
    ".o#######o####o######pppo.",
    "..o##oooo######oooo##ppo..",
    "..o##########o######ppo...",
    "...oo#######o####occccco..",
    ".....oo#####o###occcccoo..",
    "........oo...sss..ooooo...",
]
_BRAIN_W = len(_BRAIN_GRID[0])

_BODY_COLORS = ["#8fb0ff", "#7a7aff", "#b07cf0"]  # left → right gradient
_PIXEL_COLORS = {
    "o": "#232399",
    "p": "#b07cf0",
    "c": "#8f7ae8",
    "s": "#7a6ad0",
    ".": _FIELD,
}
_SPARK_COLOR = "#ffffff"

_BODY_PIXELS = [
    (x, y)
    for y, row in enumerate(_BRAIN_GRID)
    for x, ch in enumerate(row)
    if ch in ("#", "p")
]


def _pixel_color(x: int, y: int, sparks: set[tuple[int, int]]) -> str:
    ch = _BRAIN_GRID[y][x]
    if (x, y) in sparks and ch in ("#", "p"):
        return _SPARK_COLOR
    if ch == "#":
        return _BODY_COLORS[min(x * len(_BODY_COLORS) // _BRAIN_W, len(_BODY_COLORS) - 1)]
    return _PIXEL_COLORS.get(ch, _FIELD)


def _brain_lines(sparks: set[tuple[int, int]] | None = None) -> list[Text]:
    """Render the pixel grid as half-block truecolor lines (2 pixels per row)."""
    sparks = sparks or set()
    lines = []
    for row_pair in range(0, len(_BRAIN_GRID), 2):
        line = Text()
        for x in range(_BRAIN_W):
            top = _pixel_color(x, row_pair, sparks)
            bottom = _pixel_color(x, row_pair + 1, sparks)
            line.append("▀", style=f"{top} on {bottom}")
        lines.append(line)
    return lines


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


def _compose_field(
    mood: str = "neutral",
    sparks: set[tuple[int, int]] | None = None,
    console_width: int | None = None,
) -> Text:
    """The chartreuse field: ornament, wordmark, brain, slogan."""
    lines = _wordmark_lines()
    slogan = "your personal agent · always on · always remembering"
    ornament = HERMES_ORNAMENT

    wordmark_w = max(len(line) for line in lines)
    show_brain = len(lines) == len(_BRAIN_GRID) // 2
    if console_width is not None and console_width < wordmark_w + _BRAIN_W + _GAP + 2 * _MARGIN:
        show_brain = False

    content_w = wordmark_w + (_GAP + _BRAIN_W if show_brain else 0)
    width = max(content_w, len(slogan), len(ornament)) + 2 * _MARGIN
    pad = " " * _MARGIN

    def field_row(content: str = "", style: str = _INK) -> Text:
        row = Text()
        row.append(f"{pad}{content}".ljust(width), style=f"{style} {_FIELD_BG}")
        row.append("\n")
        return row

    brain = _brain_lines(sparks) if show_brain else []

    result = Text()
    result.append_text(field_row(ornament, style=_INK_SOFT))
    result.append_text(field_row())
    for i, line in enumerate(lines):
        row = Text()
        row.append(f"{pad}{line.ljust(wordmark_w)}", style=f"bold {_INK} {_FIELD_BG}")
        if show_brain:
            row.append(" " * _GAP, style=_FIELD_BG)
            row.append_text(brain[i])
        remaining = width - _MARGIN - wordmark_w - ((_GAP + _BRAIN_W) if show_brain else 0)
        row.append(" " * max(0, remaining), style=_FIELD_BG)
        row.append("\n")
        result.append_text(row)
    result.append_text(field_row())
    result.append_text(field_row(slogan, style=f"bold italic {_INK}"))
    result.append_text(field_row())
    return result


def _ascii_title(mood: str = "neutral") -> Text:
    """Render the wordmark + brain on the chartreuse field."""
    return _compose_field(mood)


def build_banner(
    version: str = __version__,
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
    sparks: set[tuple[int, int]] | None = None,
    console_width: int | None = None,
) -> Group:
    from moha_mind.cli.themes import get_theme

    theme = get_theme(mood)
    accent = theme["accent"]
    dim = theme["dim"]
    fg = theme["primary"]

    title = _compose_field(mood, sparks=sparks, console_width=console_width)

    # ── Status line ──────────────────────────────────────────────────
    status = Text("  ")
    status.append(provider, style=f"bold {accent}")
    status.append(f"/{model}", style=f"bold {fg}")

    status.append("   ")
    if tasks_count:
        status.append(f"{tasks_count} tasks", style=fg)
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


def animate_banner(console, frames: int = 16, frame_delay: float = 0.07, **banner_kwargs) -> None:
    """Play the neurons-firing intro, then print the final banner.

    Falls back to a static banner on any error or when not a terminal.
    """
    banner_kwargs.setdefault("console_width", console.width)

    if not console.is_terminal:
        console.print(build_banner(**banner_kwargs))
        return

    try:
        from rich.live import Live

        with Live(console=console, refresh_per_second=24, transient=True) as live:
            for frame in range(frames):
                # Ignition curve: a few sparks, a burst, then settle.
                intensity = min(frame, frames - frame, 6)
                sparks = set(random.sample(_BODY_PIXELS, k=3 * intensity))
                live.update(build_banner(sparks=sparks, **banner_kwargs))
                time.sleep(frame_delay)
        console.print(build_banner(**banner_kwargs))
    except Exception:
        console.print(build_banner(**banner_kwargs))
