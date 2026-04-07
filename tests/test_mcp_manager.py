"""Tests for MCP Manager."""

import pytest

from moha_mind.mcp_servers.manager import MCPManager


class TestMCPManager:
    def test_register_server(self):
        manager = MCPManager()
        manager.register_server("test", {"some": "server"})
        assert "test" in manager._servers

    def test_get_all_tools_empty(self):
        manager = MCPManager()
        assert manager.get_all_tools() == {}

    @pytest.mark.asyncio
    async def test_call_tool_unknown_server(self):
        manager = MCPManager()
        result = await manager.call_tool("unknown", "tool", {})
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_call_tool_on_server(self):
        manager = MCPManager()

        class FakeServer:
            async def handle_tool(self, name, args):
                return f"handled {name} with {args}"

        manager.register_server("test", FakeServer())
        result = await manager.call_tool("test", "my_tool", {"x": 1})
        assert "handled my_tool" in result

    @pytest.mark.asyncio
    async def test_call_tool_server_error(self):
        manager = MCPManager()

        class BrokenServer:
            async def handle_tool(self, name, args):
                raise ValueError("boom")

        manager.register_server("broken", BrokenServer())
        result = await manager.call_tool("broken", "tool", {})
        assert "Error" in result
