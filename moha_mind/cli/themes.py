"""Mood-aware color themes for MohaMind CLI.

Colors adapt based on the user's detected energy/mood state.
Inspired by neural activity visualization - warmer tones for high energy,
cooler tones for calm/focus, muted tones for low energy.
"""

from rich.style import Style
from rich.text import Text

ENERGY_HIGH = {
    "primary": "#FF6B6B",
    "accent": "#FFD93D",
    "secondary": "#6BCB77",
    "brain": "#FF8E53",
    "prompt": "bold #FF6B6B",
    "panel_border": "#FF6B6B",
    "panel_title": "bold #FFD93D",
    "status": "#6BCB77",
    "dim": "#888888",
}

ENERGY_NEUTRAL = {
    "primary": "#4ECDC4",
    "accent": "#45B7D1",
    "secondary": "#96CEB4",
    "brain": "#5EEAD4",
    "prompt": "bold #4ECDC4",
    "panel_border": "#4ECDC4",
    "panel_title": "bold #45B7D1",
    "status": "#96CEB4",
    "dim": "#888888",
}

ENERGY_LOW = {
    "primary": "#667EEA",
    "accent": "#764BA2",
    "secondary": "#A78BFA",
    "brain": "#818CF8",
    "prompt": "bold #667EEA",
    "panel_border": "#667EEA",
    "panel_title": "bold #A78BFA",
    "status": "#764BA2",
    "dim": "#666666",
}

MOOD_THEMES = {
    "high": ENERGY_HIGH,
    "neutral": ENERGY_NEUTRAL,
    "low": ENERGY_LOW,
}

BRAIN_COLORS = {
    "high": ["#FF6B6B", "#FFD93D", "#FF8E53", "#6BCB77"],
    "neutral": ["#4ECDC4", "#45B7D1", "#5EEAD4", "#96CEB4"],
    "low": ["#667EEA", "#764BA2", "#818CF8", "#A78BFA"],
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
