"""Rich display panels for briefings, tasks, memory, and alerts.

All output goes through this module for a consistent Hermes look:
square thin borders, lowercase titles, blue/chartreuse/off-white only.
Each function returns a renderable Rich object.
"""

from rich import box
from rich.columns import Columns
from rich.console import Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from moha_mind.cli.themes import HERMES_ORNAMENT, get_theme


def _title(label: str, theme: dict[str, str]) -> Text:
    return Text(f" {label} ", style=theme["panel_title"])


def hermes_panel(body, label: str, theme: dict[str, str], padding: tuple[int, int] = (1, 2)) -> Panel:
    return Panel(
        body,
        title=_title(label, theme),
        title_align="left",
        box=box.SQUARE,
        border_style=theme["panel_border"],
        padding=padding,
    )


def display_response(text: str, mood: str = "neutral") -> Markdown:
    return Markdown(text)


def display_briefing(text: str, mood: str = "neutral") -> Panel:
    return hermes_panel(Markdown(text), "morning briefing", get_theme(mood))


def display_attention_radar(text: str, mood: str = "neutral") -> Panel:
    return hermes_panel(Markdown(text), "attention radar", get_theme(mood))


def display_calendar_snapshot(text: str, mood: str = "neutral") -> Panel:
    return hermes_panel(Markdown(text), "calendar horizon", get_theme(mood))


def display_command_center(sections: list[dict], mood: str = "neutral") -> Group:
    theme = get_theme(mood)
    panels = [hermes_panel(Markdown(section["body"]), section["title"], theme) for section in sections]
    header = Text()
    header.append("majlis command center", style=theme["panel_title"])
    header.append(f"  {HERMES_ORNAMENT}", style=theme["dim"])
    return Group(header, Columns(panels, equal=True, expand=True))


def display_tasks(tasks: list[dict], mood: str = "neutral") -> Panel:
    theme = get_theme(mood)

    table = Table(show_header=True, box=None, padding=(0, 1), expand=True, header_style=theme["dim"])
    table.add_column("", width=2)
    table.add_column("priority", width=8, style=theme["accent"])
    table.add_column("task", style=theme["primary"])
    table.add_column("due", style=theme["dim"], width=12)

    priority_styles = {
        "high": f"bold {theme['accent']}",
        "medium": theme["primary"],
        "low": theme["dim"],
    }

    for task in tasks:
        done = task.get("done", False)
        priority = task.get("priority", "medium")
        prio_style = priority_styles.get(priority, "")
        text = task.get("text", "")
        due = task.get("due", "")

        if done:
            marker = Text("■", style=theme["dim"])
            text_obj = Text(text, style="dim strikethrough")
        else:
            marker = Text("□", style=theme["accent"])
            text_obj = Text(text)

        table.add_row(
            marker,
            Text(priority, style=prio_style),
            text_obj,
            Text(due or "", style=theme["dim"]),
        )

    return hermes_panel(table, "tasks", theme)


def display_expiring(items: list[dict], mood: str = "neutral") -> Panel:
    theme = get_theme(mood)

    table = Table(show_header=True, box=None, padding=(0, 1), expand=True, header_style=theme["dim"])
    table.add_column("", width=2)
    table.add_column("category", width=12, style=theme["secondary"])
    table.add_column("detail", style=theme["primary"])
    table.add_column("days left", width=10)

    for item in items:
        days = item.get("days_left", 999)
        if days <= 1:
            marker, days_style = "●", "bold red"
        elif days <= 7:
            marker, days_style = "●", f"bold {theme['accent']}"
        else:
            marker, days_style = "○", theme["dim"]

        table.add_row(
            Text(marker, style=days_style),
            item.get("category", "").lower(),
            Text(item.get("detail", "")),
            Text(f"{days}d", style=days_style),
        )

    return hermes_panel(table, "expiring items", theme)


def display_memory_search(results: list[dict], mood: str = "neutral") -> Panel:
    theme = get_theme(mood)

    table = Table(show_header=True, box=None, padding=(0, 1), expand=True, header_style=theme["dim"])
    table.add_column("category", width=14, style=theme["accent"])
    table.add_column("line", width=6, style=theme["dim"])
    table.add_column("context", style=theme["primary"])

    for r in results[:10]:
        table.add_row(
            r.get("category", ""),
            str(r.get("line_number", "")),
            Text(r.get("context", "").strip()),
        )

    count = len(results)
    label = f"memory search · {count} result{'s' if count != 1 else ''}"
    return hermes_panel(table, label, theme)


def display_tool_call(tool_name: str, args: dict, result: str, mood: str = "neutral") -> Group:
    theme = get_theme(mood)
    header = Text(f"  = {tool_name}", style=f"dim {theme['accent']}")
    if args:
        args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
        header.append(f"({args_str})", style="dim")
    header.append(f" -> {result[:80]}", style="dim")
    return Group(header)


def display_status_bar(
    model: str,
    provider: str,
    mood: str = "neutral",
    tasks_active: int = 0,
    expiring_soon: int = 0,
) -> Text:
    theme = get_theme(mood)
    bar = Text()
    bar.append(" ─ ", style=theme["dim"])
    bar.append(f"{provider}/{model}", style=theme["secondary"])
    bar.append("  ·  ", style=theme["dim"])
    bar.append(f"{tasks_active} tasks", style=theme["primary"])
    bar.append("  ·  ", style=theme["dim"])
    if expiring_soon > 0:
        bar.append(f"{expiring_soon} expiring", style=f"bold {theme['accent']}")
    else:
        bar.append("all clear", style=theme["dim"])
    bar.append(" ─", style=theme["dim"])
    return bar


def display_help(commands: list[dict], mood: str = "neutral") -> Panel:
    theme = get_theme(mood)

    table = Table(show_header=True, box=None, padding=(0, 2), expand=True, header_style=theme["dim"])
    table.add_column("command", style=f"bold {theme['accent']}", width=16)
    table.add_column("description", style=theme["primary"])

    for cmd in commands:
        table.add_row(cmd["name"], cmd["description"])

    return hermes_panel(table, "commands", theme)


def display_error(message: str) -> Panel:
    return Panel(
        Text(message, style="#f5f5f5"),
        title=Text(" error ", style="bold red"),
        title_align="left",
        box=box.SQUARE,
        border_style="red",
        padding=(1, 2),
    )


def display_success(message: str) -> Panel:
    theme = get_theme("neutral")
    return Panel(
        Text.from_markup(message, style=theme["primary"]),
        box=box.SQUARE,
        border_style=theme["accent"],
        padding=(0, 2),
    )
