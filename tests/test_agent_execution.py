import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from moha_mind.agent.core import MohaMindAgent
from moha_mind.config import Settings


@pytest.fixture
def execution_agent(tmp_memory, monkeypatch):
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    config = Settings(_env_file=None, llm_strategy="solo", memory_router_enabled=False)
    with (
        patch("moha_mind.agent.core.settings", config),
        patch("moha_mind.agent.core.AsyncOpenAI"),
        patch("moha_mind.agent.core.build_embedder", return_value=None),
    ):
        agent = MohaMindAgent(tmp_memory)
        agent._route_memory_context = MagicMock(return_value=([], {}))
        agent._build_recall_context = MagicMock(return_value="")
        yield agent, config


def tool_call(arguments="{}", call_id="call-1", name="test_tool"):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


def response(calls=None, content=None):
    message = MagicMock(tool_calls=calls, content=content)
    message.model_dump.return_value = {
        "role": "assistant",
        "content": content,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.function.name, "arguments": call.function.arguments},
            }
            for call in calls or []
        ],
    }
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@pytest.mark.parametrize("arguments", ["{", "", "null", "[]", '"text"', "42", "true", None])
async def test_invalid_arguments_never_execute_a_tool(execution_agent, arguments):
    agent, _ = execution_agent
    handler = AsyncMock(return_value="changed")
    agent.register_tool("test_tool", handler)

    result = await agent._execute_model_tool_call(tool_call(arguments))

    assert "not executed" in result
    handler.assert_not_awaited()


async def test_valid_arguments_reach_handler(execution_agent):
    agent, _ = execution_agent
    handler = AsyncMock(return_value="saved")
    agent.register_tool("test_tool", handler)

    result = await agent._execute_model_tool_call(tool_call('{"text":"تجربة","priority":"high"}'))

    assert result == "saved"
    handler.assert_awaited_once_with(text="تجربة", priority="high")


async def test_timeout_cancels_handler_without_retry(execution_agent):
    agent, config = execution_agent
    config.agent_tool_timeout_seconds = 0.01
    cancelled = asyncio.Event()

    async def slow_tool():
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    handler = AsyncMock(side_effect=slow_tool)
    agent.register_tool("test_tool", handler)

    result = await agent._execute_model_tool_call(tool_call())

    assert "timed out" in result
    assert "outcome is unknown" in result
    assert cancelled.is_set()
    handler.assert_awaited_once()


async def test_cancellation_propagates(execution_agent):
    agent, _ = execution_agent
    started = asyncio.Event()

    async def slow_tool():
        started.set()
        await asyncio.Event().wait()

    agent.register_tool("test_tool", slow_tool)
    task = asyncio.create_task(agent._execute_model_tool_call(tool_call()))
    await asyncio.wait_for(started.wait(), timeout=1)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


async def test_large_result_is_bounded_and_marked(execution_agent):
    agent, config = execution_agent
    config.agent_max_tool_result_chars = 128
    agent.register_tool("test_tool", AsyncMock(return_value="أ" * 1000))

    result = await agent._execute_model_tool_call(tool_call())

    assert len(result) == 128
    assert result.startswith("أ")
    assert "truncated" in result


@pytest.mark.parametrize("workflow", ["chat", "generate_briefing", "generate_weekly_review"])
async def test_workflows_bound_batches_and_preserve_tool_responses(execution_agent, workflow):
    agent, config = execution_agent
    config.agent_max_tool_calls = 2
    handler = AsyncMock(return_value="ok")
    agent.register_tool("test_tool", handler)
    calls = [tool_call(call_id=f"call-{i}") for i in range(4)]
    agent._chat_completion_with_fallback = AsyncMock(
        side_effect=[response(calls=calls), response(content="Two tools completed; two skipped.")]
    )

    result = await getattr(agent, workflow)(*(["Run tools"] if workflow == "chat" else []))

    assert result == "Two tools completed; two skipped."
    assert handler.await_count == 2
    final_request = agent._chat_completion_with_fallback.call_args.kwargs
    assert "tools" not in final_request
    results = [message for message in final_request["messages"] if message["role"] == "tool"]
    assert [message["tool_call_id"] for message in results] == [call.id for call in calls]
    assert [message["content"] for message in results[:2]] == ["ok", "ok"]
    assert all("not executed" in message["content"] for message in results[2:])


async def test_chat_budget_counts_across_rounds(execution_agent):
    agent, config = execution_agent
    config.agent_max_tool_calls = 3
    handler = AsyncMock(return_value="ok")
    agent.register_tool("test_tool", handler)
    agent._chat_completion_with_fallback = AsyncMock(
        side_effect=[
            response(calls=[tool_call(call_id="call-1"), tool_call(call_id="call-2")]),
            response(calls=[tool_call(call_id="call-3"), tool_call(call_id="call-4")]),
            response(content="Finished"),
        ]
    )

    assert await agent.chat("Run tools") == "Finished"
    assert handler.await_count == 3
    assert "tools" not in agent._chat_completion_with_fallback.call_args.kwargs
    assert agent.session_store.load_recent_messages("default")[-1]["content"] == "Finished"


async def test_chat_round_limit_forces_final_response(execution_agent):
    agent, config = execution_agent
    config.agent_max_tool_rounds = 1
    handler = AsyncMock(return_value="ok")
    agent.register_tool("test_tool", handler)
    agent._chat_completion_with_fallback = AsyncMock(
        side_effect=[response(calls=[tool_call()]), response(content="Finished")]
    )

    assert await agent.chat("Run tools") == "Finished"
    handler.assert_awaited_once()
    assert "tools" not in agent._chat_completion_with_fallback.call_args.kwargs


@pytest.mark.parametrize("workflow", ["chat", "generate_briefing", "generate_weekly_review"])
async def test_workflows_recover_from_invalid_arguments(execution_agent, workflow):
    agent, _ = execution_agent
    handler = AsyncMock(return_value="changed")
    agent.register_tool("test_tool", handler)
    agent._chat_completion_with_fallback = AsyncMock(
        side_effect=[response(calls=[tool_call("{")]), response(content="Could not execute")]
    )

    result = await getattr(agent, workflow)(*(["Run tools"] if workflow == "chat" else []))

    assert result == "Could not execute"
    handler.assert_not_awaited()
    messages = agent._chat_completion_with_fallback.call_args.kwargs["messages"]
    assert any(message["role"] == "tool" and "not executed" in message["content"] for message in messages)
