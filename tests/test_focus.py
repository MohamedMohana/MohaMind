import json
from datetime import datetime
from io import StringIO
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError
from rich.console import Console

from moha_mind.agent.focus import FocusPlanner, FocusRequest
from moha_mind.cli.focus import display_focus_plan, run_focus
from moha_mind.utils.timezone import KSA_TZ


@pytest.fixture(autouse=True)
def fixed_time(monkeypatch):
    current = datetime(2026, 9, 26, 12, 0, tzinfo=KSA_TZ)
    monkeypatch.setattr("moha_mind.agent.focus.now_ksa", lambda: current)


async def test_deadlines_rank_before_priority_and_completed_tasks_are_excluded(tmp_memory):
    tmp_memory.add_task("Someday", "high")
    tmp_memory.add_task("Today", "low", "2026-09-26")
    tmp_memory.add_task("Overdue", "low", "2026-09-25")
    tmp_memory.add_task("Done", "high", "2026-09-20")
    tmp_memory.complete_task("Done")
    before = tmp_memory.read("tasks")

    plan = await FocusPlanner(tmp_memory).build(FocusRequest(minutes=90))

    tasks = [block for block in plan.blocks if block.kind == "task"]
    assert [block.title for block in tasks] == ["Overdue", "Today", "Someday"]
    assert tasks[0].reason == "Overdue by 1 day(s)"
    assert plan.active_tasks == 3
    assert plan.overdue_tasks == 1
    assert plan.remaining_tasks == 0
    assert tmp_memory.read("tasks") == before


@pytest.mark.parametrize("energy,expected_count,block_size", [("low", 1, 15), ("neutral", 3, 25), ("high", 5, 45)])
async def test_energy_controls_session_size(tmp_memory, energy, expected_count, block_size):
    for index in range(6):
        tmp_memory.add_task(f"Task {index}")

    plan = await FocusPlanner(tmp_memory).build(FocusRequest(minutes=480, energy=energy))

    tasks = [block for block in plan.blocks if block.kind == "task"]
    assert len(tasks) == expected_count
    assert all(block.minutes == block_size for block in tasks)
    assert plan.remaining_tasks == 6 - expected_count


@pytest.mark.parametrize("minutes", [5, 15, 25, 29, 30, 34, 35, 60, 120, 480])
@pytest.mark.parametrize("energy", ["low", "neutral", "high"])
async def test_budget_includes_breaks_and_never_ends_with_a_break(tmp_memory, minutes, energy):
    for index in range(6):
        tmp_memory.add_task(f"Task {index}")

    plan = await FocusPlanner(tmp_memory).build(FocusRequest(minutes=minutes, energy=energy))

    assert plan.planned_minutes == sum(block.minutes for block in plan.blocks)
    assert plan.planned_minutes <= minutes
    assert all(block.minutes >= 5 for block in plan.blocks)
    assert plan.blocks[0].kind == plan.blocks[-1].kind == "task"
    assert all(plan.blocks[index].kind == "break" for index in range(1, len(plan.blocks), 2))


async def test_reminders_include_overdue_and_next_24_hours_only(tmp_memory):
    tmp_memory.add_reminder("Earlier", "2026-09-26 11:00")
    tmp_memory.add_reminder("Now", "2026-09-26 12:00")
    tmp_memory.add_reminder("Tomorrow", "2026-09-27 12:00")
    tmp_memory.add_reminder("Later", "2026-09-27 12:01")
    tmp_memory.add_reminder("Finished", "2026-09-26 10:00")
    tmp_memory.complete_reminder("Finished")

    plan = await FocusPlanner(tmp_memory).build(FocusRequest())

    assert [reminder.title for reminder in plan.reminders] == ["Earlier", "Now", "Tomorrow"]
    assert [reminder.overdue for reminder in plan.reminders] == [True, False, False]
    assert plan.generated_at.utcoffset().total_seconds() == 10800


async def test_malformed_dates_do_not_break_plan(tmp_memory):
    tmp_memory.add_task("Bad date", "high", "2026-99-99")
    tmp_memory.add_reminder("Bad reminder", "2026-99-99 12:00")

    plan = await FocusPlanner(tmp_memory).build(FocusRequest())

    assert plan.blocks[0].title == "Bad date"
    assert plan.blocks[0].due is None
    assert len(plan.warnings) == 2


@pytest.mark.parametrize("minutes", [-1, 0, 4, 481, 5.5, True, "60"])
def test_invalid_budgets_are_rejected(minutes):
    with pytest.raises(ValidationError):
        FocusRequest(minutes=minutes)


async def test_empty_plan_is_actionable(tmp_memory):
    plan = await FocusPlanner(tmp_memory).build(FocusRequest())
    output = StringIO()
    Console(file=output, width=120).print(display_focus_plan(plan))

    assert plan.planned_minutes == plan.active_tasks == 0
    assert "/add task" in output.getvalue()


async def test_display_preserves_user_text_as_literal(tmp_memory):
    tmp_memory.add_task("[bold]Literal[/bold] موعد")
    plan = await FocusPlanner(tmp_memory).build(FocusRequest())
    output = StringIO()
    Console(file=output, width=160).print(display_focus_plan(plan))

    assert "[bold]Literal[/bold] موعد" in output.getvalue()


async def test_tool_returns_structured_plan(tmp_memory):
    tmp_memory.add_task("Make progress")

    result = json.loads(await FocusPlanner(tmp_memory).get_focus_plan(minutes=15, energy="low"))

    assert result["blocks"][0]["title"] == "Make progress"
    assert result["planned_minutes"] == 15


async def test_demo_is_isolated_and_emits_valid_json(tmp_path, monkeypatch, capsys):
    from moha_mind.config import settings

    private = tmp_path / "private-memory"
    private.mkdir()
    (private / "tasks.md").write_text("Do not read or change this private task")
    monkeypatch.setattr(settings, "memory_dir", str(private))
    monkeypatch.chdir(tmp_path)
    before = {path: path.read_bytes() for path in private.rglob("*") if path.is_file()}

    await run_focus(FocusRequest(), demo=True, as_json=True)

    output = capsys.readouterr().out
    assert json.loads(output)["active_tasks"] == 4
    assert "private task" not in output
    assert {path: path.read_bytes() for path in private.rglob("*") if path.is_file()} == before
    assert not (tmp_path / ".env").exists()


async def test_focus_slash_command_uses_saved_energy_and_handles_bad_input(tmp_memory, monkeypatch):
    from moha_mind.cli.app import MohaMindCLI

    monkeypatch.setattr("moha_mind.cli.app.InputHandler", Mock())
    cli = MohaMindCLI(tmp_memory, Mock())
    output = StringIO()
    cli.console = Console(file=output, width=120)
    tmp_memory.write("energy_log", "- Mood: low")
    tmp_memory.add_task("One small step")

    await cli._cmd_focus("20")
    assert "low energy" in output.getvalue()
    assert "One small step" in output.getvalue()
    assert cli.registry.get("focus") is not None

    for invalid in ["0", "twenty", "20 turbo", "20 low extra"]:
        await cli._cmd_focus(invalid)
    assert output.getvalue().count("Usage: /focus") == 4


def test_demo_entrypoint_skips_auth_and_bootstrap(monkeypatch):
    from moha_mind import main

    monkeypatch.setattr("sys.argv", ["mohamind", "demo", "--json"])
    auth = Mock(side_effect=AssertionError("Demo must not check API keys"))
    monkeypatch.setattr(main, "_has_api_key", auth)
    run = AsyncMock()
    monkeypatch.setattr("moha_mind.cli.focus.run_focus", run)

    main.run()

    run.assert_awaited_once_with(FocusRequest(), demo=True, as_json=True)
    auth.assert_not_called()


def test_one_shot_reserved_word_is_still_a_prompt(monkeypatch):
    from moha_mind import main

    monkeypatch.setattr("sys.argv", ["mohamind", "-p", "doctor"])
    monkeypatch.setattr(main, "_has_api_key", lambda: True)
    monkeypatch.setattr(main, "configure_logging", Mock())
    run = AsyncMock()
    monkeypatch.setattr(main, "run_one_shot", run)

    main.run()

    run.assert_awaited_once_with("doctor")
