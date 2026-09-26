"""External MCP client — connects MohaMind to real MCP servers.

The built-in servers under ``moha_mind/mcp_servers/`` are in-process Python
classes. This module speaks the actual Model Context Protocol so the agent
can also use any third-party MCP server (filesystem, GitHub, web fetch,
Notion, ...) over stdio or streamable HTTP.

Servers are declared in a Claude-compatible ``mcp_servers.json``:

    {
      "mcpServers": {
        "fetch":  {"command": "uvx", "args": ["mcp-server-fetch"]},
        "github": {
          "command": "npx",
          "args": ["-y", "@modelcontextprotocol/server-github"],
          "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"}
        },
        "context7": {"url": "https://mcp.context7.com/mcp"}
      }
    }

``${VAR}`` in env values and headers is expanded from the environment, so
secrets can stay in ``.env`` / the shell instead of the config file.
"""

import asyncio
import json
import os
import re
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from moha_mind.utils.logging_config import log

CONNECT_TIMEOUT_SECONDS = 25
MAX_TOOL_NAME_LENGTH = 64


@dataclass
class ExternalServerConfig:
    name: str
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    enabled: bool = True

    @property
    def transport(self) -> str:
        return "http" if self.url else "stdio"


def _expand(value: str) -> str:
    return os.path.expandvars(value)


def load_mcp_config(path: str | Path) -> list[ExternalServerConfig]:
    """Parse a Claude-style mcpServers config file. Missing file -> []."""
    config_path = Path(path)
    if not config_path.exists():
        return []

    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning(f"Could not read MCP config {config_path}: {exc}")
        return []

    servers = raw.get("mcpServers") or {}
    if not isinstance(servers, dict):
        log.warning(f"MCP config {config_path}: 'mcpServers' must be an object")
        return []

    configs: list[ExternalServerConfig] = []
    for name, spec in servers.items():
        if not isinstance(spec, dict):
            log.warning(f"MCP server '{name}': config must be an object, skipping")
            continue

        enabled = not spec.get("disabled", False)
        if "enabled" in spec:
            enabled = bool(spec["enabled"])

        configs.append(
            ExternalServerConfig(
                name=str(name),
                command=str(spec.get("command", "")),
                args=[str(a) for a in spec.get("args", [])],
                env={str(k): _expand(str(v)) for k, v in (spec.get("env") or {}).items()},
                url=str(spec.get("url", "")),
                headers={str(k): _expand(str(v)) for k, v in (spec.get("headers") or {}).items()},
                enabled=enabled,
            )
        )
    return configs


def sanitize_tool_name(server_name: str, tool_name: str) -> str:
    """Build an OpenAI-safe function name: [a-zA-Z0-9_-], max 64 chars."""
    combined = f"{server_name}_{tool_name}"
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", combined)
    return cleaned[:MAX_TOOL_NAME_LENGTH]


def format_tool_result(result: Any) -> str:
    """Flatten an mcp CallToolResult into the plain string the agent expects."""
    parts: list[str] = []
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(text)
            continue
        # Non-text blocks (images, resources): keep a useful reference.
        uri = getattr(getattr(block, "resource", None), "uri", None)
        if uri is not None:
            parts.append(f"[resource: {uri}]")
        else:
            parts.append(f"[{getattr(block, 'type', 'non-text')} content]")

    if not parts:
        structured = getattr(result, "structuredContent", None)
        if structured is not None:
            parts.append(json.dumps(structured, ensure_ascii=False, default=str))

    text = "\n".join(parts) if parts else "(empty result)"
    if getattr(result, "isError", False):
        return f"Tool error: {text}"
    return text


class ExternalMCPConnection:
    """One live MCP server connection (own exit stack, session, and tools)."""

    def __init__(self, config: ExternalServerConfig):
        self.config = config
        self.session: Any = None
        self.tools: list[Any] = []
        self.error: str = ""
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    @property
    def connected(self) -> bool:
        return self.session is not None

    async def connect(self) -> None:
        self._stop.clear()
        ready = asyncio.get_running_loop().create_future()
        self._task = asyncio.create_task(self._run(ready))
        try:
            await ready
        except BaseException:
            self._task.cancel()
            await self.aclose()
            raise

    async def _run(self, ready: asyncio.Future) -> None:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        try:
            async with AsyncExitStack() as stack:
                if self.config.transport == "http":
                    from mcp.client.streamable_http import streamablehttp_client

                    read, write, _ = await stack.enter_async_context(
                        streamablehttp_client(self.config.url, headers=self.config.headers or None)
                    )
                else:
                    params = StdioServerParameters(
                        command=self.config.command,
                        args=self.config.args,
                        env={**os.environ, **self.config.env},
                    )
                    read, write = await stack.enter_async_context(stdio_client(params))

                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                tools_result = await session.list_tools()
                self.session = session
                self.tools = list(tools_result.tools)
                ready.set_result(None)
                await self._stop.wait()
        except Exception as exc:
            self.error = str(exc) or type(exc).__name__
            if not ready.done():
                ready.set_exception(exc)
            else:
                log.warning(f"MCP server '{self.config.name}' connection ended: {exc}")
        finally:
            self.session = None
            if not ready.done():
                ready.cancel()

    async def aclose(self) -> None:
        if self._task is not None:
            self._stop.set()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None


class ExternalMCPManager:
    """Loads config, connects to every enabled server, registers their tools."""

    def __init__(self, configs: list[ExternalServerConfig]):
        self.configs = configs
        self.connections: dict[str, ExternalMCPConnection] = {}

    @classmethod
    def from_config(cls, path: str | Path) -> "ExternalMCPManager":
        return cls(load_mcp_config(path))

    async def connect_all(self, timeout: float = CONNECT_TIMEOUT_SECONDS) -> None:
        for config in self.configs:
            connection = ExternalMCPConnection(config)
            self.connections[config.name] = connection

            if not config.enabled:
                connection.error = "disabled"
                continue
            if not config.command and not config.url:
                connection.error = "no command or url configured"
                log.warning(f"MCP server '{config.name}': no command or url configured")
                continue

            try:
                await asyncio.wait_for(connection.connect(), timeout=timeout)
                log.info(f"MCP server connected: {config.name} ({len(connection.tools)} tools)")
            except asyncio.TimeoutError:
                connection.error = f"timed out after {timeout:.0f}s"
                log.warning(f"MCP server '{config.name}' timed out after {timeout:.0f}s")
            except Exception as exc:
                connection.error = str(exc) or type(exc).__name__
                log.warning(f"MCP server '{config.name}' failed to connect: {exc}")

    def _build_handler(self, connection: ExternalMCPConnection, tool_name: str):
        async def handler(**kwargs) -> str:
            result = await connection.session.call_tool(tool_name, kwargs or None)
            return format_tool_result(result)

        return handler

    def register_into(self, agent: Any) -> int:
        """Register every discovered tool on the agent. Returns the count."""
        registered = 0
        for connection in self.connections.values():
            if not connection.connected:
                continue
            server_name = connection.config.name
            for tool in connection.tools:
                exposed_name = sanitize_tool_name(server_name, tool.name)
                description = (tool.description or "").strip().splitlines()
                summary = description[0] if description else f"{tool.name} (via {server_name} MCP server)"
                schema = {
                    "type": "function",
                    "function": {
                        "name": exposed_name,
                        "description": summary[:1024],
                        "parameters": tool.inputSchema or {"type": "object", "properties": {}},
                    },
                }
                agent.register_tool(exposed_name, self._build_handler(connection, tool.name), schema=schema)
                registered += 1
        return registered

    def status(self) -> list[dict]:
        """Human-readable status for each configured server (for /mcp)."""
        report = []
        for config in self.configs:
            connection = self.connections.get(config.name)
            if connection is None:
                state, detail = "not started", ""
            elif connection.connected:
                state, detail = "connected", f"{len(connection.tools)} tools"
            elif connection.error == "disabled":
                state, detail = "disabled", ""
            else:
                state, detail = "failed", connection.error
            report.append(
                {
                    "name": config.name,
                    "transport": config.transport,
                    "target": config.url or " ".join([config.command, *config.args]).strip(),
                    "state": state,
                    "detail": detail,
                    "tools": [t.name for t in connection.tools] if connection and connection.connected else [],
                }
            )
        return report

    async def aclose(self) -> None:
        for connection in self.connections.values():
            await connection.aclose()
