"""MCP Client Manager - connects to all MCP servers and manages their tools."""

from typing import Any

from moha_mind.utils.logging_config import log


class MCPManager:
    """Manages connections to MCP servers and provides unified tool access."""

    def __init__(self):
        self._servers: dict[str, Any] = {}
        self._tools: dict[str, dict] = {}

    def register_server(self, name: str, server: Any) -> None:
        """Register an MCP server instance."""
        self._servers[name] = server
        log.info(f"MCP server registered: {name}")

    def get_all_tools(self) -> dict[str, dict]:
        """Get combined tools from all registered servers."""
        return self._tools.copy()

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict) -> str:
        """Call a tool on a specific MCP server."""
        server = self._servers.get(server_name)
        if not server:
            return f"Server '{server_name}' not found"
        try:
            result = await server.handle_tool(tool_name, arguments)
            return result
        except Exception as e:
            log.error(f"MCP tool call failed [{server_name}.{tool_name}]: {e}")
            return f"Error: {str(e)}"
