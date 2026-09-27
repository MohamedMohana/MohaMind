from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from moha_mind.agent.core import MohaMindAgent
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


def test_completed_tasks_are_not_active_context(tmp_memory):
    tmp_memory.add_task("Finished appointment", due="2025-01-01")
    tmp_memory.complete_task("Finished appointment")
    assert "Finished appointment" not in build_system_prompt(tmp_memory)


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
