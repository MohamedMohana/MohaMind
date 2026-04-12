"""Neural pulse spinner - brain-wave thinking animation.

Instead of a boring spinner, shows an animated neural signal
propagating through brain nodes. Each frame shows a different
pattern of active neurons firing.
"""

import threading

from rich.console import Console, Group
from rich.live import Live
from rich.text import Text

from moha_mind.cli.themes import get_brain_colors

NEURAL_FRAMES = [
    "◉──○──○──○──○",
    "○──◉──○──○──○",
    "○──○──◉──○──○",
    "○──○──○──◉──○",
    "○──○──○──○──◉",
    "◉──○──◉──○──○",
    "○──◉──○──◉──○",
    "○──○──◉──○──◉",
    "◉──○──○──◉──○",
    "○──◉──◉──◉──○",
    "◉──◉──◉──○──○",
    "◉──◉──◉──◉──◉",
]

THINKING_MESSAGES = [
    "Scanning your orbit...",
    "Checking the command deck...",
    "Linking memories...",
    "Reading your signals...",
    "Plotting next moves...",
    "Synthesizing context...",
    "Sorting priorities...",
    "Bringing it together...",
]


class NeuralPulse:
    def __init__(self, console: Console, mood: str = "neutral"):
        self.console = console
        self.mood = mood
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._active = False

    def _build_frame(self, frame_idx: int, msg_idx: int) -> Group:
        colors = get_brain_colors(self.mood)
        frame = NEURAL_FRAMES[frame_idx % len(NEURAL_FRAMES)]
        msg = THINKING_MESSAGES[msg_idx % len(THINKING_MESSAGES)]

        colored_frame = Text()
        for i, char in enumerate(frame):
            if char == "◉":
                color = colors[i % len(colors)]
                colored_frame.append(char, style=f"bold {color}")
            elif char == "─":
                colored_frame.append(char, style="dim")
            else:
                colored_frame.append(char, style="dim white")

        label = Text(f"  {msg}", style="italic dim")
        return Group(colored_frame, label)

    def _spin(self, live: Live) -> None:
        idx = 0
        while not self._stop_event.is_set():
            frame = self._build_frame(idx, idx)
            live.update(frame)
            idx += 1
            self._stop_event.wait(0.12)

    def start(self) -> None:
        if self._active:
            return
        self._active = True
        self._stop_event.clear()
        self._live = Live(
            Text(""),
            console=self.console,
            refresh_per_second=10,
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
