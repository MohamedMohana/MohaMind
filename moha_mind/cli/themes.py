"""Mood-aware color themes for MohaMind CLI.

Colors adapt based on the user's detected energy/mood state.
Inspired by neural activity visualization - warmer tones for high energy,
cooler tones for calm/focus, muted tones for low energy.
"""

from rich.style import Style
from rich.text import Text

ENERGY_HIGH = {
    "primary": "#F97316",
    "accent": "#FACC15",
    "secondary": "#FB7185",
    "brain": "#FDBA74",
    "prompt": "bold #F97316",
    "panel_border": "#F97316",
    "panel_title": "bold #FACC15",
    "status": "#FB7185",
    "dim": "#8B8B8B",
    "prompt_label": "majlis",
}

ENERGY_NEUTRAL = {
    "primary": "#0F766E",
    "accent": "#14B8A6",
    "secondary": "#C08457",
    "brain": "#2DD4BF",
    "prompt": "bold #0F766E",
    "panel_border": "#0F766E",
    "panel_title": "bold #14B8A6",
    "status": "#C08457",
    "dim": "#7A7A7A",
    "prompt_label": "mohamind",
}

ENERGY_LOW = {
    "primary": "#1D4ED8",
    "accent": "#7C3AED",
    "secondary": "#38BDF8",
    "brain": "#60A5FA",
    "prompt": "bold #1D4ED8",
    "panel_border": "#1D4ED8",
    "panel_title": "bold #7C3AED",
    "status": "#38BDF8",
    "dim": "#676767",
    "prompt_label": "night-shift",
}

MOOD_THEMES = {
    "high": ENERGY_HIGH,
    "neutral": ENERGY_NEUTRAL,
    "low": ENERGY_LOW,
}

BRAIN_COLORS = {
    "high": ["#F97316", "#FACC15", "#FB7185", "#FDBA74"],
    "neutral": ["#0F766E", "#14B8A6", "#2DD4BF", "#C08457"],
    "low": ["#1D4ED8", "#7C3AED", "#60A5FA", "#38BDF8"],
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
