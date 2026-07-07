"""Comprehensive tests for agent core with mocked LLM."""

from types import SimpleNamespace
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
        assert "search_sessions" in names
        assert "add_task" in names
        assert "complete_task" in names
        assert "list_tasks" in names

    def test_get_tools_schema_includes_registered_external_tools(self, agent):
        async def attention(days_ahead: int = 30, include_social: bool = True) -> str:
            return "ok"

        agent.register_tool("get_attention_radar", attention)

        schema = agent.get_tools_schema()
        attention_schema = next(s for s in schema if s["function"]["name"] == "get_attention_radar")

        assert attention_schema["function"]["parameters"]["properties"]["days_ahead"]["type"] == "integer"
        assert attention_schema["function"]["parameters"]["properties"]["include_social"]["type"] == "boolean"

    @pytest.mark.asyncio
    async def test_handle_tool_save_memory(self, agent):
        result = await agent.handle_tool_call("save_memory", {"category": "profile", "content": "Test content"})
        assert "Saved to profile" in result

    @pytest.mark.asyncio
    async def test_handle_tool_save_memory_preserves_existing_content(self, agent):
        agent.memory.write("family", "Existing family fact")

        await agent.handle_tool_call("save_memory", {"category": "family", "content": "New family fact"})

        content = agent.memory.read("family")
        assert "Existing family fact" in content
        assert "New family fact" in content

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
    async def test_handle_tool_search_sessions(self, agent):
        agent.session_store.append_message("test_chat", "user", "Discuss passport renewal next month")
        result = await agent.handle_tool_call("search_sessions", {"query": "passport", "chat_id": "test_chat"})
        assert "passport renewal" in result.lower()

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

    def test_get_conversation_loads_persisted_messages(self, agent):
        agent.session_store.append_message("persisted_chat", "user", "Remember the dentist")
        agent.session_store.append_message("persisted_chat", "assistant", "Noted.")
        conv = agent._get_conversation("persisted_chat")
        assert len(conv) == 2
        assert conv[0]["content"] == "Remember the dentist"

    def test_llm_history_keeps_large_tool_batch_intact(self, agent):
        tool_calls = [
            {
                "id": f"call_{idx}",
                "type": "function",
                "function": {"name": "save_memory", "arguments": '{"category":"tasks","content":"x"}'},
            }
            for idx in range(25)
        ]
        conversation = [
            {"role": "user", "content": "Save these reminders"},
            {"role": "assistant", "content": None, "tool_calls": tool_calls},
            *[
                {
                    "role": "tool",
                    "tool_call_id": f"call_{idx}",
                    "content": "Saved",
                }
                for idx in range(25)
            ],
        ]

        messages = agent._build_llm_messages("system", conversation, max_messages=20)

        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"
        assert len([message for message in messages if message["role"] == "tool"]) == 25

    def test_llm_history_drops_orphan_tool_messages(self, agent):
        conversation = [
            {"role": "tool", "tool_call_id": "missing_call", "content": "orphan"},
            {"role": "user", "content": "hello"},
        ]

        messages = agent._build_llm_messages("system", conversation)

        assert [message["role"] for message in messages] == ["system", "user"]

    def test_recall_combines_memory_and_sessions(self, agent):
        agent.memory.write("profile", "Passport number: A123")
        agent.session_store.append_message("cli", "user", "We talked about passport renewal")
        result = agent.recall("passport", chat_id="cli")
        assert "Structured Memory" in result
        assert "Past Conversations" in result

    def test_recall_arabic_labels(self, agent):
        agent.memory.write("profile", "Passport number: A123")
        result = agent.recall("passport", chat_id="telegram", language="ar")
        assert "الذاكرة المنظمة" in result

    def test_persisted_sessions_load_in_new_agent_instance(self, tmp_memory):
        with patch("moha_mind.agent.core.settings") as mock_settings:
            mock_settings.active_llm_config = {
                "api_key": "test-key",
                "model": "test-model",
                "base_url": "https://test.api",
                "provider": "test",
            }
            mock_settings.fallback_llm_config = None
            with patch("moha_mind.agent.core.AsyncOpenAI"):
                first = MohaMindAgent(tmp_memory)
                first.session_store.append_message("shared_chat", "user", "Book dentist appointment")

                second = MohaMindAgent(tmp_memory)
                conv = second._get_conversation("shared_chat")

        assert len(conv) == 1
        assert conv[0]["content"] == "Book dentist appointment"

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

    def test_switch_to_fallback_skips_same_model(self, agent):
        agent.model = "same-model"
        agent.provider = "same-provider"
        with patch("moha_mind.agent.core.settings") as mock_settings:
            mock_settings.fallback_llm_config = {
                "api_key": "fallback-key",
                "model": "same-model",
                "base_url": None,
                "provider": "same-provider",
            }
            result = agent._switch_to_fallback()
            assert result is False


class _FakeCompletions:
    def __init__(self, content: str | None = None, error: Exception | None = None):
        self.content = content
        self.error = error

    async def create(self, **kwargs):
        if self.error:
            raise self.error
        message = SimpleNamespace(content=self.content, tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class _FakeClient:
    def __init__(self, completions: _FakeCompletions):
        self.chat = SimpleNamespace(completions=completions)


class TestAgentCoreFallbackGeneration:
    @pytest.mark.asyncio
    async def test_briefing_uses_fallback_on_primary_error(self, agent):
        agent.provider = "zai"
        agent.model = "bad-model"
        agent.client = _FakeClient(_FakeCompletions(error=RuntimeError("model does not exist")))
        fallback_client = _FakeClient(_FakeCompletions(content="ملخص جاهز"))

        with (
            patch("moha_mind.agent.core.settings") as mock_settings,
            patch("moha_mind.agent.core.AsyncOpenAI", return_value=fallback_client),
        ):
            mock_settings.fallback_llm_config = {
                "api_key": "fallback-key",
                "model": "fallback-model",
                "base_url": None,
                "provider": "openai",
            }
            result = await agent.generate_briefing()

        assert result == "ملخص جاهز"
        assert agent.provider == "openai"
        assert agent.model == "fallback-model"
