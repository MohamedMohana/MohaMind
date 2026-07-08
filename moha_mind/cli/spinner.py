"""Hermes signal spinner — a pulse travelling through the ornament glyphs.

Instead of a generic spinner, a bright chartreuse window slides across the
Hermes glyph run while the rest stays field-blue. Same NeuralPulse API.
"""

import threading

from rich.console import Console, Group
from rich.live import Live
from rich.text import Text

from moha_mind.cli.themes import get_brain_colors, get_theme

SIGNAL = r"/\-_=+|<-/=~:*-/\-_=+|<"
PULSE_WIDTH = 5

THINKING_MESSAGES = [
    "scanning your orbit...",
    "checking the command deck...",
    "linking memories...",
    "reading your signals...",
    "plotting next moves...",
    "synthesizing context...",
    "sorting priorities...",
    "bringing it together...",
]


class NeuralPulse:
    def __init__(self, console: Console, mood: str = "neutral"):
        self.console = console
        self.mood = mood
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._active = False

    def _build_frame(self, frame_idx: int, msg_idx: int) -> Group:
        theme = get_theme(self.mood)
        colors = get_brain_colors(self.mood)
        pulse_start = frame_idx % len(SIGNAL)
        msg = THINKING_MESSAGES[(msg_idx // len(SIGNAL)) % len(THINKING_MESSAGES)]

        line = Text("  ")
        for i, char in enumerate(SIGNAL):
            offset = (i - pulse_start) % len(SIGNAL)
            if offset < PULSE_WIDTH:
                # Head of the pulse is brightest, trailing glyphs fade.
                color = colors[min(offset, len(colors) - 1)]
                line.append(char, style=f"bold {color}")
            else:
                line.append(char, style=theme["dim"])

        label = Text(f"  {msg}", style=f"italic {theme['dim']}")
        return Group(line, label)

    def _spin(self, live: Live) -> None:
        idx = 0
        while not self._stop_event.is_set():
            frame = self._build_frame(idx, idx)
            live.update(frame)
            idx += 1
            self._stop_event.wait(0.08)

    def start(self) -> None:
        if self._active:
            return
        self._active = True
        self._stop_event.clear()
        self._live = Live(
            Text(""),
            console=self.console,
            refresh_per_second=12,
            transient=True,
        )
        self._live.start()
        self._thread = threading.Thread(target=self._spin, args=(self._live,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._active:
            return
        self._active = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=0.5)
        if hasattr(self, "_live"):
            self._live.stop()
