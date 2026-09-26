import asyncio
from datetime import timedelta
from tempfile import TemporaryDirectory

from rich.console import Console, Group
from rich.table import Table
from rich.text import Text

from moha_mind.agent.focus import FocusPlan, FocusPlanner, FocusRequest
from moha_mind.agent.memory import MemoryManager
from moha_mind.cli.display import hermes_panel
from moha_mind.cli.themes import get_theme
from moha_mind.utils.timezone import now_ksa


def display_focus_plan(plan: FocusPlan):
    theme = get_theme(plan.energy)
    summary = Text(
        f"{plan.planned_minutes}/{plan.budget_minutes} minutes · {plan.energy} energy · "
        f"{plan.active_tasks} active · {plan.overdue_tasks} overdue",
        style=theme["accent"],
    )
    table = Table(box=None, expand=True, padding=(0, 1), header_style=theme["dim"])
    table.add_column("minutes", width=9)
    table.add_column("focus", ratio=2)
    table.add_column("why this", ratio=1)
    offset = 0
    for block in plan.blocks:
        style = theme["dim"] if block.kind == "break" else theme["primary"]
        table.add_row(
            Text(f"{offset}–{offset + block.minutes}", style=style),
            Text(block.title, style=style),
            Text(block.reason, style=style),
        )
        offset += block.minutes
    parts = [summary, Text(""), table]
    if not plan.blocks:
        parts.append(Text("A clear slate. Add your first task with /add task <text>.", style=theme["primary"]))
    if plan.remaining_tasks:
        parts.append(Text(f"\n{plan.remaining_tasks} task(s) left for later. Re-run /focus when ready."))
    if plan.reminders:
        parts.append(Text("\nReminders · overdue and next 24 hours (Asia/Riyadh)", style=theme["accent"]))
        for reminder in plan.reminders:
            status = "overdue" if reminder.overdue else "upcoming"
            parts.append(Text(f"  {reminder.remind_at} · {reminder.title} · {status}"))
    for warning in plan.warnings:
        parts.append(Text(f"\n{warning}", style="yellow"))
    parts.append(
        Text(
            "\nSuggested work blocks, not completion estimates. Calendar availability is not checked.\n"
            "Complete a task with /done <task text>, then re-run /focus.",
            style=theme["dim"],
        )
    )
    return hermes_panel(Group(*parts), "your next move", theme)


def _seed_demo(memory: MemoryManager) -> None:
    now = now_ksa()
    today = now.date()
    yesterday = today - timedelta(days=1)
    reminder_time = (now + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
    (memory.memory_path / "tasks.md").write_text(
        "# Tasks\n\n## Active\n"
        f"- [ ] Send the project proposal [HIGH] due:{yesterday}\n"
        f"- [ ] Prepare for tomorrow's meeting [HIGH] due:{today}\n"
        "- [ ] Practice Arabic for ten minutes\n"
        "- [ ] Choose a book for the weekend [LOW]\n",
        encoding="utf-8",
    )
    (memory.memory_path / "reminders.md").write_text(
        f"# Reminders\n\n## Active\n- [ ] Call a friend | remind_at:{reminder_time} | repeat:none\n",
        encoding="utf-8",
    )


async def run_focus(request: FocusRequest, *, demo: bool = False, as_json: bool = False) -> None:
    if demo:
        with TemporaryDirectory(prefix="mohamind-demo-") as directory:
            memory = await asyncio.to_thread(MemoryManager, directory)
            await asyncio.to_thread(_seed_demo, memory)
            plan = await FocusPlanner(memory).build(request)
    else:
        memory = await asyncio.to_thread(MemoryManager)
        plan = await FocusPlanner(memory).build(request)
    if as_json:
        print(plan.model_dump_json(indent=2))
        return
    console = Console()
    if demo:
        console.print(Text("MohaMind demo · fictional data · no API key needed", style="bold green"))
    console.print(display_focus_plan(plan))
    if demo:
        console.print(Text("\nMake it yours: uv run mohamind setup\nYour personal memory was not used or changed."))
