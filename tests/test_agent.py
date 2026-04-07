"""Tests for the agent core."""

from unittest.mock import patch

import pytest

from moha_mind.agent.core import MohaMindAgent
from moha_mind.agent.memory import MemoryManager


@pytest.fixture
def agent(tmp_path):
    memory = MemoryManager(memory_dir=str(tmp_path))
    memory.ensure_templates()
    with patch.dict(
        "os.environ",
        {
            "ZAI_API_KEY": "test-key",
            "PRIMARY_LLM": "zai",
            "ZAI_MODEL": "test-model",
        },
    ):
        from moha_mind.config import Settings

        with patch(
            "moha_mind.agent.core.settings",
            Settings(
                zai_api_key="test-key",
                primary_llm="zai",
                zai_model="test-model",
            ),
        ):
            a = MohaMindAgent(memory)
            return a


class TestAgentCore:
    def test_register_tool(self, agent):
        async def dummy(**kwargs):
            return "ok"

        agent.register_tool("test_tool", dummy)
        assert "test_tool" in agent._tool_handlers

    def test_get_tools_schema(self, agent):
        tools = agent.get_tools_schema()
        assert len(tools) > 0
        names = [t["function"]["name"] for t in tools]
        assert "save_memory" in names
        assert "search_memory" in names
        assert "add_task" in names
        assert "list_tasks" in names

    @pytest.mark.asyncio
    async def test_handle_tool_save_memory(self, agent):
        result = await agent.handle_tool_call(
            "save_memory",
            {
                "category": "profile",
                "content": "# Test\nHello world",
            },
        )
        assert "Saved" in result

    @pytest.mark.asyncio
    async def test_handle_tool_add_task(self, agent):
        result = await agent.handle_tool_call(
            "add_task",
            {
                "text": "Test task item",
                "priority": "high",
            },
        )
        assert "Test task item" in result

    @pytest.mark.asyncio
    async def test_handle_tool_list_tasks(self, agent):
        result = await agent.handle_tool_call("list_tasks", {})
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_handle_tool_unknown(self, agent):
        result = await agent.handle_tool_call("nonexistent_tool", {})
        assert "Unknown" in result or "Error" in result

    @pytest.mark.asyncio
    async def test_handle_tool_external(self, agent):
        async def external_handler(**kwargs):
            return "external result"

        agent.register_tool("ext_tool", external_handler)
        result = await agent.handle_tool_call("ext_tool", {"arg": "value"})
        assert result == "external result"

    @pytest.mark.asyncio
    async def test_handle_tool_search_memory(self, agent):
        agent.memory.write("profile", "Name: Moha\nLocation: Riyadh")
        result = await agent.handle_tool_call("search_memory", {"query": "Riyadh"})
        assert "Riyadh" in result
