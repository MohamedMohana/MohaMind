from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from moha_mind.agent.core import MohaMindAgent
from moha_mind.agent.memory_summarizer import MemorySummarizer
from moha_mind.agent.system_prompt import build_system_prompt
from moha_mind.mcp_servers.tasks.server import TaskServer
from moha_mind.utils.i18n import t


@pytest.mark.asyncio
async def test_archive_requires_confirmation_and_preserves_history(tmp_memory):
    tmp_memory.add_task("Old appointment", due="2025-01-01")
    server = TaskServer(tmp_memory)
    before = tmp_memory.read("tasks")
    await server.handle_tool("archive_task", {"task_text": "Old appointment"})
    assert tmp_memory.read("tasks") == before
    result = await server.handle_tool("archive_task", {"task_text": "Old appointment", "confirmed": True})
    assert "Task archived" in result
    assert not tmp_memory.get_task_section()
    assert "Old appointment" in tmp_memory.read("tasks")
    assert "Old appointment" not in build_system_prompt(tmp_memory)


def test_archive_rejects_partial_empty_and_ambiguous_matches(tmp_memory):
    tmp_memory.add_task("Buy supplies")
    tmp_memory.add_task("Buy supplies tomorrow")
    assert not tmp_memory.archive_task("")
    assert not tmp_memory.archive_task("Buy")
    assert tmp_memory.archive_task("Buy supplies")
    assert len(tmp_memory.get_task_section()) == 1
    tmp_memory.add_task("Buy supplies tomorrow")
    assert not tmp_memory.archive_task("Buy supplies tomorrow")


@pytest.mark.parametrize("existing_archive", [False, True])
def test_archive_moves_task_and_details_out_of_active_section(tmp_memory, existing_archive):
    content = "# Tasks\n## Active\n- [ ] Old appointment\n  Appointment details\n- [ ] Current task\n"
    if existing_archive:
        content += "## Archived\n- Earlier record\n"
    tmp_memory.write("tasks", content)
    assert tmp_memory.archive_task("Old appointment")
    active, archived = tmp_memory.read("tasks").split("## Archived")
    assert "Old appointment" not in active
    assert "Appointment details" not in active
    assert "Current task" in active
    assert "Old appointment" in archived
    assert "Appointment details" in archived
    if existing_archive:
        assert "Earlier record" in archived


def test_routed_task_summary_excludes_history_and_refreshes_old_cache(tmp_memory):
    content = (
        "# Tasks\n## Active\n- Archived 2025-01-01: Old appointment\n"
        "  Old details\n- [x] Finished task\n- Call a friend\n"
        "## Archived\n- Earlier record\n"
    )
    tmp_memory.write("tasks", content)
    summarizer = MemorySummarizer(tmp_memory)
    summarizer._write_cache("tasks", "Active: Archived Old appointment", source_text=content)
    summary = summarizer.get_summary("tasks")
    prompt = build_system_prompt(tmp_memory, focus_categories=["profile"], summaries={"tasks": summary})
    assert "Call a friend" in prompt
    for text in ("Old appointment", "Old details", "Finished task", "Earlier record"):
        assert text not in prompt
    assert summarizer.get_summary("tasks") == summary


@pytest.mark.asyncio
async def test_llm_task_summary_receives_only_active_context(tmp_memory):
    tmp_memory.write("tasks", "# Tasks\n## Active\n- [ ] Current task\n- [ ] Old appointment\n")
    assert tmp_memory.archive_task("Old appointment")
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(
                    return_value=SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content="Current task"))]
                    )
                )
            )
        )
    )
    summarizer = MemorySummarizer(tmp_memory, llm_client=client)
    assert await summarizer.refresh_async("tasks") == "Current task"
    messages = client.chat.completions.create.call_args.kwargs["messages"]
    assert "Current task" in messages[-1]["content"]
    assert "Old appointment" not in messages[-1]["content"]
    assert summarizer.get_summary("tasks") == "Current task"


def test_completed_tasks_are_not_active_context(tmp_memory):
    tmp_memory.add_task("Finished appointment", due="2025-01-01")
    tmp_memory.complete_task("Finished appointment")
    assert "Finished appointment" not in build_system_prompt(tmp_memory)


@pytest.mark.parametrize("focus", [None, ["tasks"], ["profile"]])
def test_legacy_tasks_preserve_context_without_history(tmp_memory, focus):
    tmp_memory.write(
        "tasks",
        "\n".join(
            [
                "# Tasks",
                "## Active",
                "- buy milk",
                "- [ ] Open task",
                "  Active details",
                "- [x] Finished task",
                "  Finished details",
                "- Archived 2025-01-01: Old task",
                "  Archived details",
                "## Completed",
                "- Past task",
                "### Notes",
                "Historical detail",
                "## Recurring",
                "- Repeat task",
            ]
        ),
    )
    prompt = build_system_prompt(tmp_memory, focus_categories=focus)
    for text in ("buy milk", "Open task", "Active details", "Repeat task"):
        assert (text in prompt) == (focus != ["profile"])
    for text in ("Finished task", "Finished details", "Old task", "Archived details", "Past task", "Historical detail"):
        assert text not in prompt


@pytest.mark.asyncio
async def test_weekly_review_asks_only_about_overdue_active_tasks(tmp_memory):
    tmp_memory.add_task("Expired appointment", due="2025-01-01")
    tmp_memory.add_task("Future appointment", due="2027-01-01")
    tmp_memory.add_task("Today appointment", due="2026-09-27")
    tmp_memory.add_task("Undated task")
    tmp_memory.add_task("Finished appointment", due="2025-01-01")
    tmp_memory.complete_task("Finished appointment")
    tmp_memory.add_task("Archived appointment", due="2025-01-01")
    tmp_memory.archive_task("Archived appointment")
    before = tmp_memory.read("tasks")
    agent = MohaMindAgent.__new__(MohaMindAgent)
    agent.memory = tmp_memory
    agent._tool_handlers = {}
    agent._tool_schemas = {}
    agent._chat_completion_with_fallback = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Review", tool_calls=None))]
        )
    )
    with patch("moha_mind.agent.core.ksa_today_str", return_value="2026-09-27"):
        result = await agent.generate_weekly_review()
    assert t("review.cleanup") in result
    assert "Expired appointment" in result
    for name in (
        "Future appointment",
        "Today appointment",
        "Undated task",
        "Finished appointment",
        "Archived appointment",
    ):
        assert name not in result
    assert tmp_memory.read("tasks") == before
    tools = agent._chat_completion_with_fallback.call_args.kwargs["tools"]
    assert all(tool["function"]["name"] not in {"save_memory", "complete_task", "archive_task"} for tool in tools)
