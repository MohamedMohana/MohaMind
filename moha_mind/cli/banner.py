"""ASCII art brain banner with live stats panel.

Shows a stylized brain neural network on the left,
and a dynamic stats dashboard on the right.
"""

from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from moha_mind.cli.themes import BRAIN_COLORS, get_theme

BRAIN_ART = r"""
        ╔══════════════════════════╗
        ║  __  __  __  __  __  __ ║
        ║ /  \/  \/  \/  \/  \/  ║
        ║ \_/\_/\_/\_/\_/\_/\_/\ ║
        ║  /  \/  \/  \/  \/  \/ ║
        ║  \_/\_/\_/\_/\_/\_/\_/ ║
        ║   ╱╲  ╱╲  ╱╲  ╱╲  ╱╲  ║
        ║  ╱  ╲╱  ╲╱  ╲╱  ╲╱  ╲ ║
        ║ ╱ ●  ●  ●  ●  ●  ●  ● ║
        ║  ╲  ╱╲  ╱╲  ╱╲  ╱╲  ╱ ║
        ║   ╲╱  ╲╱  ╲╱  ╲╱  ╲╱  ║
        ╚══════════════════════════╝"""

COMPACT_BRAIN = "🧠 MohaMind"

NEURAL_NODES = [
    "  ◉──◉──◉  ",
    " /|\\ /|\\   ",
    "◉──◉──◉──◉",
    " \\|/ \\|/   ",
    "  ◉──◉──◉  ",
]


def _render_brain(mood: str = "neutral") -> Text:
    colors = BRAIN_COLORS.get(mood, BRAIN_COLORS["neutral"])
    lines = []
    for i, line in enumerate(NEURAL_NODES):
        color = colors[i % len(colors)]
        lines.append(Text(line, style={"color": color, "bold": True}))
    return Text("\n").join(lines)


def build_banner(
    version: str = "0.1.0",
    model: str = "glm-4-plus",
    provider: str = "z.ai",
    timezone: str = "Asia/Riyadh",
    tasks_count: int = 0,
    expiring_count: int = 0,
    mood: str = "neutral",
    uptime_hint: str = "",
) -> Group:
    theme = get_theme(mood)

    title = Text()
    title.append("M", style="bold red")
    title.append("o", style="bold yellow")
    title.append("h", style="bold green")
    title.append("a", style="bold cyan")
    title.append("M", style="bold blue")
    title.append("i", style="bold magenta")
    title.append("n", style="bold red")
    title.append("d", style="bold yellow")

    subtitle = Text("Your Personal AI Agent", style=f"italic {theme['dim']}")

    stats_table = Table(show_header=False, box=None, padding=(0, 2))
    stats_table.add_column(style=theme["accent"], width=14)
    stats_table.add_column(style=theme["primary"])
    stats_table.add_row("Model:", f"{model}")
    stats_table.add_row("Provider:", f"{provider}")
    stats_table.add_row("Timezone:", f"{timezone}")
    stats_table.add_row("Tasks:", f"{tasks_count} active")
    stats_table.add_row("Expiring:", f"{expiring_count} items" if expiring_count else "All clear")
    if uptime_hint:
        stats_table.add_row("Time:", uptime_hint)

    brain = _render_brain(mood)

    left_panel = Panel(
        Group(title, subtitle, Text(), brain),
        border_style=theme["panel_border"],
        padding=(1, 2),
        title="[bold]🧠 Neural Core[/]",
        title_align="center",
    )

    right_panel = Panel(
        stats_table,
        border_style=theme["panel_border"],
        padding=(1, 2),
        title="[bold]📊 Status[/]",
        title_align="center",
    )

    columns = Columns([left_panel, right_panel], equal=True, expand=True)

    bottom_bar = Text()
    bottom_bar.append("─" * 60, style=theme["dim"])
    bottom_bar.append("\n  Ready. Type ")
    bottom_bar.append("/help", style=f"bold {theme['accent']}")
    bottom_bar.append(" for commands or just start talking.\n")

    return Group(columns, bottom_bar)
