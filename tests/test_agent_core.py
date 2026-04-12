"""Comprehensive tests for agent core with mocked LLM."""

from unittest.mock import patch

import pytest

from moha_mind.agent.core import MohaMindAgent


@pytest.fixture
def agent(tmp_memory):
    with patch("moha_mind.agent.core.settings") as mock_settings:
        mock_settings.active_llm_config = {
            "api_key": "test-key",
            "model": "test-model",
            "base_url": "https://test.api",
            "provider": "test",
        }
        mock_settings.fallback_llm_config = None
        with patch("moha_mind.agent.core.AsyncOpenAI"):
            a = MohaMindAgent(tmp_memory)
    return a


class TestAgentCoreTools:
    def test_register_tool(self, agent):
        async def fake_tool():
            return "ok"

        agent.register_tool("test_tool", fake_tool)
        assert "test_tool" in agent._tool_handlers

    def test_get_tools_schema(self, agent):
        schema = agent.get_tools_schema()
        assert isinstance(schema, list)
        names = [s["function"]["name"] for s in schema]
        assert "save_memory" in names
        assert "search_memory" in names
        assert "add_task" in names
        assert "complete_task" in names
        assert "list_tasks" in names

    @pytest.mark.asyncio
    async def test_handle_tool_save_memory(self, agent):
        result = await agent.handle_tool_call("save_memory", {"category": "profile", "content": "Test content"})
        assert "Saved to profile" in result

    @pytest.mark.asyncio
    async def test_handle_tool_search_memory(self, agent):
        agent.memory.write("profile", "Name: Mohana")
        result = await agent.handle_tool_call("search_memory", {"query": "Mohana"})
        assert "Mohana" in result

    @pytest.mark.asyncio
    async def test_handle_tool_search_empty(self, agent):
        result = await agent.handle_tool_call("search_memory", {"query": "xyznonexistent"})
        assert "No results" in result

    @pytest.mark.asyncio
    async def test_handle_tool_add_task(self, agent):
        result = await agent.handle_tool_call("add_task", {"text": "Buy milk", "priority": "high"})
        assert "Task added" in result

    @pytest.mark.asyncio
    async def test_handle_tool_complete_task(self, agent):
        agent.memory.add_task("Test task")
        result = await agent.handle_tool_call("complete_task", {"task_text": "Test task"})
        assert "completed" in result.lower()

    @pytest.mark.asyncio
    async def test_handle_tool_complete_task_not_found(self, agent):
        result = await agent.handle_tool_call("complete_task", {"task_text": "Nonexistent"})
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_handle_tool_list_tasks(self, agent):
        agent.memory.add_task("Task one")
        agent.memory.add_task("Task two")
        result = await agent.handle_tool_call("list_tasks", {})
        assert "Task one" in result
        assert "Task two" in result

    @pytest.mark.asyncio
    async def test_handle_tool_list_tasks_empty(self, agent):
        result = await agent.handle_tool_call("list_tasks", {})
        assert "No active tasks" in result

    @pytest.mark.asyncio
    async def test_handle_tool_get_expiring(self, agent):
        result = await agent.handle_tool_call("get_expiring", {"days": 90})
        assert "expiring" in result.lower() or "Nothing" in result

    @pytest.mark.asyncio
    async def test_handle_tool_append_to_section(self, agent):
        result = await agent.handle_tool_call(
            "append_to_section", {"category": "profile", "section": "Hobbies", "line": "- Reading"}
        )
        assert "profile" in result

    @pytest.mark.asyncio
    async def test_handle_tool_save_note(self, agent):
        result = await agent.handle_tool_call("save_note", {"title": "Test", "content": "Hello"})
        assert "Note saved" in result

    @pytest.mark.asyncio
    async def test_handle_tool_save_daily_log(self, agent):
        result = await agent.handle_tool_call("save_daily_log", {"summary": "Had a good day"})
        assert "Daily log" in result

    @pytest.mark.asyncio
    async def test_handle_tool_external(self, agent):
        async def fake_tool(x):
            return f"handled {x}"

        agent.register_tool("my_tool", fake_tool)
        result = await agent.handle_tool_call("my_tool", {"x": 42})
        assert "handled 42" in result

    @pytest.mark.asyncio
    async def test_handle_tool_external_error(self, agent):
        async def broken_tool():
            raise ValueError("boom")

        agent.register_tool("broken", broken_tool)
        result = await agent.handle_tool_call("broken", {})
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_handle_tool_unknown(self, agent):
        result = await agent.handle_tool_call("nonexistent_tool", {})
        assert "Unknown tool" in result


class TestAgentCoreConversation:
    def test_get_conversation_new(self, agent):
        conv = agent._get_conversation("test_chat")
        assert conv == []

    def test_get_conversation_existing(self, agent):
        agent.conversations["test_chat"] = [{"role": "user", "content": "hi"}]
        conv = agent._get_conversation("test_chat")
        assert len(conv) == 1

    def test_switch_to_fallback_no_fallback(self, agent):
        with patch("moha_mind.agent.core.settings") as mock_settings:
            mock_settings.fallback_llm_config = None
            result = agent._switch_to_fallback()
            assert result is False

    def test_switch_to_fallback_with_fallback(self, agent):
        with patch("moha_mind.agent.core.settings") as mock_settings:
            mock_settings.fallback_llm_config = {
                "api_key": "fallback-key",
                "model": "fallback-model",
                "base_url": None,
                "provider": "fallback",
            }
            result = agent._switch_to_fallback()
            assert result is True
            assert agent.model == "fallback-model"
            assert agent.provider == "fallback"
