"""Hermes-inspired color themes for the MohaMind CLI.

One strict palette — hermes blue, off-white, electric chartreuse — applied
at three intensities that track the user's energy/mood state:

    high    -> chartreuse-forward, electric
    neutral -> blue field, chartreuse accents
    low     -> dimmed blues, muted accent (night shift)

Palette source: hermes-agent.nousresearch.com
    field  #0000f2   fg  #f5f5f5   accent  #edff45   paper  #ffffff
"""

from rich.style import Style
from rich.text import Text

# ── Hermes design tokens ─────────────────────────────────────────────────────
HERMES_FIELD = "#0000f2"  # the blue field — used as a *background*
HERMES_BLUE = "#4d4dff"  # the field color lifted to read on dark terminals
HERMES_BLUE_SOFT = "#8a8aff"
HERMES_FG = "#f5f5f5"
HERMES_ACCENT = "#edff45"
HERMES_ACCENT_DIM = "#b9c53e"
HERMES_PAPER = "#ffffff"

# Decorative glyph run lifted from the Hermes hero section.
HERMES_ORNAMENT = r"/\-_=+|<  -/=  ~:*-/"

ENERGY_HIGH = {
    "primary": HERMES_FG,
    "accent": HERMES_ACCENT,
    "secondary": HERMES_PAPER,
    "brain": HERMES_ACCENT,
    "prompt": f"bold {HERMES_ACCENT}",
    "panel_border": HERMES_ACCENT,
    "panel_title": f"bold {HERMES_ACCENT}",
    "status": HERMES_FG,
    "dim": "#9d9dc7",
    "prompt_label": "majlis",
}

ENERGY_NEUTRAL = {
    "primary": HERMES_FG,
    "accent": HERMES_ACCENT,
    "secondary": HERMES_BLUE_SOFT,
    "brain": HERMES_BLUE,
    "prompt": f"bold {HERMES_ACCENT}",
    "panel_border": HERMES_BLUE,
    "panel_title": f"bold {HERMES_ACCENT}",
    "status": HERMES_BLUE_SOFT,
    "dim": "#8383b8",
    "prompt_label": "mohamind",
}

ENERGY_LOW = {
    "primary": "#d8d8e8",
    "accent": HERMES_ACCENT_DIM,
    "secondary": HERMES_BLUE_SOFT,
    "brain": "#6b6bcc",
    "prompt": f"bold {HERMES_ACCENT_DIM}",
    "panel_border": "#3535b8",
    "panel_title": f"bold {HERMES_ACCENT_DIM}",
    "status": HERMES_BLUE_SOFT,
    "dim": "#6b6b99",
    "prompt_label": "night-shift",
}

MOOD_THEMES = {
    "high": ENERGY_HIGH,
    "neutral": ENERGY_NEUTRAL,
    "low": ENERGY_LOW,
}

BRAIN_COLORS = {
    "high": [HERMES_ACCENT, HERMES_FG, "#d4e63e", HERMES_PAPER],
    "neutral": [HERMES_BLUE, HERMES_ACCENT, HERMES_BLUE_SOFT, HERMES_FG],
    "low": ["#3535b8", HERMES_BLUE_SOFT, "#6b6bcc", HERMES_ACCENT_DIM],
}


def get_theme(mood: str = "neutral") -> dict[str, str]:
    return MOOD_THEMES.get(mood, ENERGY_NEUTRAL)


def get_brain_colors(mood: str = "neutral") -> list[str]:
    return BRAIN_COLORS.get(mood, BRAIN_COLORS["neutral"])


def style_prompt(mood: str = "neutral") -> str:
    theme = get_theme(mood)
    return theme["prompt"]


def style_panel(mood: str = "neutral") -> tuple[str, str]:
    theme = get_theme(mood)
    return theme["panel_border"], theme["panel_title"]


def colored_text(text: str, color_key: str = "primary", mood: str = "neutral") -> Text:
    theme = get_theme(mood)
    color = theme.get(color_key, theme["primary"])
    return Text(text, style=Style(color=color))
