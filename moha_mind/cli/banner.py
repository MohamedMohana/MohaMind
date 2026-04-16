"""MohaMind CLI banner — block-art header with brain visual and green gradient."""

from rich.console import Group
from rich.text import Text

# ── Green gradient (left → right across ASCII art) ───────────────────────────
_GRADIENT = ["#00FF87", "#00E676", "#00C853", "#00BFA5", "#1DE9B6", "#00E5FF"]

# ── Brain art — two hemispheres with folds, block-art style ─────────────────
#    Designed to sit to the right of the title — 6 lines to match.
_BRAIN = [
    r"      ▄▄███▄  ▄███▄▄",
    r"    ▄██╭╮╭╮██  ██╭╮╭╮██▄",
    r"   ██▌╰╯╭╯██▌▐██╰╮╰╯▐██",
    r"   ██▌╭╮╰╮██▌▐██╭╯╭╮▐██",
    r"    ▀██╰╯╰╯██▌▐██╰╯╰╯██▀",
    r"      ▀▀██▄▄▐▌▄▄██▀▀",
]


def _ascii_title(mood: str = "neutral") -> Text:
    """Render 'MohaMind' block-art + brain side-by-side with green gradient."""
    try:
        import pyfiglet  # type: ignore[import-untyped]

        art = pyfiglet.figlet_format("MohaMind", font="ansi_shadow", width=120)
    except Exception:
        return Text("  MohaMind\n", style="bold #00FF87")

    title_lines = art.split("\n")
    while title_lines and not title_lines[-1].strip():
        title_lines.pop()
    if not title_lines:
        return Text("  MohaMind\n", style="bold #00FF87")

    # Pad brain and title to same height
    brain = list(_BRAIN)
    while len(brain) < len(title_lines):
        brain.append(" " * len(_BRAIN[0]))
    while len(title_lines) < len(brain):
        title_lines.append("")

    title_w = max(len(ln) for ln in title_lines) or 1
    gap = "  "
    colors = _GRADIENT

    # Brain gradient: darker green → bright green → cyan (top to bottom)
    brain_colors = ["#00C853", "#00E676", "#00FF87", "#00FF87", "#00E676", "#00C853"]

    result = Text()
    for i, (tl, bl) in enumerate(zip(title_lines, brain)):
        # Title chars with left-to-right gradient
        padded_t = tl.ljust(title_w)
        for j, ch in enumerate(padded_t):
            idx = min(int(j / title_w * len(colors)), len(colors) - 1)
            result.append(ch, style=f"bold {colors[idx]}")

        # Gap
        result.append(gap)

        # Brain chars with per-row color
        bc = brain_colors[i % len(brain_colors)]
        result.append(bl, style=f"bold {bc}")

        result.append("\n")

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
    g = "#00FF87"
    d = "#555555"

    # ── Title + Brain ────────────────────────────────────────────────
    title = _ascii_title(mood)

    # ── Slogan ───────────────────────────────────────────────────────
    slogan = Text(
        "  Your Personal Agent  ·  Always On  ·  Always Remembering\n",
        style=f"italic {d}",
    )

    # ── Status line ──────────────────────────────────────────────────
    status = Text("  ")
    status.append(provider, style=f"bold {g}")
    status.append(f"/{model}", style="bold white")

    status.append("   ", style=d)
    if tasks_count:
        status.append(f"{tasks_count} tasks", style="bold white")
    else:
        status.append("no tasks", style=d)

    status.append("   ", style=d)
    if expiring_count:
        status.append(f"{expiring_count} expiring", style="bold #FF5252")
    else:
        status.append("nothing expiring", style=d)

    links = []
    if telegram_enabled:
        links.append("telegram")
    if google_enabled:
        links.append("gcal")
    if microsoft_enabled:
        links.append("outlook")
    if links:
        status.append("   ", style=d)
        status.append(" ".join(links), style=d)

    if uptime_hint:
        status.append("   ", style=d)
        status.append(uptime_hint, style=d)

    status.append("\n")

    # ── Hint ─────────────────────────────────────────────────────────
    hint = Text("  ")
    cmds = ["/help", "/majlis", "/radar", "/briefing"]
    for i, cmd in enumerate(cmds):
        if i:
            hint.append("  ", style=d)
        hint.append(cmd, style=f"bold {g}")
    hint.append("  or just start talking\n", style=d)

    # ── Assemble ─────────────────────────────────────────────────────
    return Group(
        Text(),
        title,
        slogan,
        status,
        Text(),
        hint,
    )
