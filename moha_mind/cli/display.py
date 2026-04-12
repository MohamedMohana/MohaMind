"""Rich display panels for briefings, tasks, memory, and alerts.

All output goes through this module for a consistent, premium look.
Each function returns a renderable Rich object.
"""

from rich.columns import Columns
from rich.console import Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from moha_mind.cli.themes import get_theme


def display_response(text: str, mood: str = "neutral") -> Markdown:
    return Markdown(text)


def display_briefing(text: str, mood: str = "neutral") -> Panel:
    theme = get_theme(mood)
    return Panel(
        Markdown(text),
        title="☀️ Morning Briefing",
        title_align="left",
        border_style=theme["panel_border"],
        padding=(1, 2),
    )


def display_attention_radar(text: str, mood: str = "neutral") -> Panel:
    theme = get_theme(mood)
    return Panel(
        Markdown(text),
        title="🎯 Attention Radar",
        title_align="left",
        border_style=theme["panel_border"],
        padding=(1, 2),
    )


def display_calendar_snapshot(text: str, mood: str = "neutral") -> Panel:
    theme = get_theme(mood)
    return Panel(
        Markdown(text),
        title="🗓 Calendar Horizon",
        title_align="left",
        border_style=theme["panel_border"],
        padding=(1, 2),
    )


def display_command_center(sections: list[dict], mood: str = "neutral") -> Group:
    theme = get_theme(mood)
    panels = [
        Panel(
            Markdown(section["body"]),
            title=section["title"],
            title_align="left",
            border_style=theme["panel_border"],
            padding=(1, 2),
        )
        for section in sections
    ]
    header = Text("Majlis Command Center", style=theme["panel_title"])
    return Group(header, Columns(panels, equal=True, expand=True))


def display_tasks(tasks: list[dict], mood: str = "neutral") -> Panel:
    theme = get_theme(mood)

    table = Table(show_header=True, box=None, padding=(0, 1), expand=True)
    table.add_column("Status", width=3)
    table.add_column("Priority", width=8, style=theme["accent"])
    table.add_column("Task", style=theme["primary"])
    table.add_column("Due", style=theme["dim"], width=12)

    priority_styles = {
        "high": "bold red",
        "medium": "yellow",
        "low": "green",
    }

    for task in tasks:
        done = task.get("done", False)
        status = "✅" if done else "⬜"
        priority = task.get("priority", "medium")
        prio_style = priority_styles.get(priority, "")
        text = task.get("text", "")
        due = task.get("due", "")

        if done:
            status = "✅"
            text_obj = Text(text, style="dim strikethrough")
        else:
            text_obj = Text(text)

        table.add_row(
            status,
            Text(priority.upper(), style=prio_style),
            text_obj,
            Text(due or "", style="dim"),
        )

    return Panel(
        table,
        title="📋 Tasks",
        title_align="left",
        border_style=theme["panel_border"],
        padding=(1, 2),
    )


def display_expiring(items: list[dict], mood: str = "neutral") -> Panel:
    theme = get_theme(mood)

    table = Table(show_header=True, box=None, padding=(0, 1), expand=True)
    table.add_column("Urgency", width=3)
    table.add_column("Category", width=12, style=theme["accent"])
    table.add_column("Detail", style=theme["primary"])
    table.add_column("Days Left", width=10)

    for item in items:
        days = item.get("days_left", 999)
        if days <= 1:
            urgency = "🔴"
            days_style = "bold red"
        elif days <= 7:
            urgency = "🟡"
            days_style = "yellow"
        else:
            urgency = "🟢"
            days_style = "green"

        table.add_row(
            urgency,
            item.get("category", "").upper(),
            Text(item.get("detail", "")),
            Text(f"{days}d", style=days_style),
        )

    return Panel(
        table,
        title="⏰ Expiring Items",
        title_align="left",
        border_style=theme["panel_border"],
        padding=(1, 2),
    )


def display_memory_search(results: list[dict], mood: str = "neutral") -> Panel:
    theme = get_theme(mood)

    table = Table(show_header=True, box=None, padding=(0, 1), expand=True)
    table.add_column("Category", width=14, style=theme["accent"])
    table.add_column("Line", width=6, style="dim")
    table.add_column("Context", style=theme["primary"])

    for r in results[:10]:
        table.add_row(
            r.get("category", ""),
            str(r.get("line_number", "")),
            Text(r.get("context", "").strip()),
        )

    count = len(results)
    title = f"🔍 Memory Search ({count} result{'s' if count != 1 else ''})"
    return Panel(
        table,
        title=title,
        title_align="left",
        border_style=theme["panel_border"],
        padding=(1, 2),
    )


def display_tool_call(tool_name: str, args: dict, result: str, mood: str = "neutral") -> Group:
    theme = get_theme(mood)
    header = Text(f"  ⚙ {tool_name}", style=f"dim {theme['accent']}")
    if args:
        args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
        header.append(f"({args_str})", style="dim")
    header.append(f" → {result[:80]}", style="dim")
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
    bar.append(" ── ", style="dim")
    bar.append(f"🧠 {provider}/{model}", style=theme["accent"])
    bar.append(" │ ", style="dim")
    bar.append(f"📋 {tasks_active}", style=theme["primary"])
    bar.append(" │ ", style="dim")
    if expiring_soon > 0:
        bar.append(f"⏰ {expiring_soon}", style="bold red")
    else:
        bar.append("✓ all good", style="green")
    bar.append(" ──", style="dim")
    return bar


def display_help(commands: list[dict], mood: str = "neutral") -> Panel:
    theme = get_theme(mood)

    table = Table(show_header=True, box=None, padding=(0, 2), expand=True)
    table.add_column("Command", style=f"bold {theme['accent']}", width=16)
    table.add_column("Description", style=theme["primary"])

    for cmd in commands:
        table.add_row(cmd["name"], cmd["description"])

    return Panel(
        table,
        title="📖 Commands",
        title_align="left",
        border_style=theme["panel_border"],
        padding=(1, 2),
    )


def display_error(message: str) -> Panel:
    return Panel(
        Text(message, style="red"),
        title="❌ Error",
        title_align="left",
        border_style="red",
        padding=(1, 2),
    )


def display_success(message: str) -> Panel:
    return Panel(
        Text(message, style="green"),
        border_style="green",
        padding=(0, 2),
    )
