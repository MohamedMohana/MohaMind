"""Tests for the external MCP client layer (config, naming, registration)."""

import json
from types import SimpleNamespace

import pytest

from moha_mind.mcp_servers.external import (
    ExternalMCPConnection,
    ExternalMCPManager,
    ExternalServerConfig,
    format_tool_result,
    load_mcp_config,
    sanitize_tool_name,
)


def _write_config(tmp_path, payload) -> str:
    path = tmp_path / "mcp_servers.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


class TestLoadConfig:
    def test_missing_file_returns_empty(self, tmp_path):
        assert load_mcp_config(tmp_path / "nope.json") == []

    def test_invalid_json_returns_empty(self, tmp_path):
        path = tmp_path / "mcp_servers.json"
        path.write_text("{not json", encoding="utf-8")
        assert load_mcp_config(path) == []

    def test_stdio_server_parsed(self, tmp_path):
        path = _write_config(
            tmp_path,
            {"mcpServers": {"fetch": {"command": "uvx", "args": ["mcp-server-fetch"]}}},
        )
        configs = load_mcp_config(path)
        assert len(configs) == 1
        assert configs[0].name == "fetch"
        assert configs[0].command == "uvx"
        assert configs[0].args == ["mcp-server-fetch"]
        assert configs[0].transport == "stdio"
        assert configs[0].enabled

    def test_http_server_parsed(self, tmp_path):
        path = _write_config(
            tmp_path,
            {"mcpServers": {"context7": {"url": "https://mcp.context7.com/mcp"}}},
        )
        configs = load_mcp_config(path)
        assert configs[0].transport == "http"
        assert configs[0].url == "https://mcp.context7.com/mcp"

    def test_disabled_flag(self, tmp_path):
        path = _write_config(
            tmp_path,
            {"mcpServers": {"off": {"command": "x", "disabled": True}}},
        )
        assert not load_mcp_config(path)[0].enabled

    def test_env_expansion(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MY_TOKEN", "secret123")
        path = _write_config(
            tmp_path,
            {"mcpServers": {"gh": {"command": "npx", "env": {"TOKEN": "${MY_TOKEN}"}}}},
        )
        assert load_mcp_config(path)[0].env == {"TOKEN": "secret123"}

    def test_non_dict_server_skipped(self, tmp_path):
        path = _write_config(tmp_path, {"mcpServers": {"bad": "nope", "ok": {"command": "x"}}})
        configs = load_mcp_config(path)
        assert [c.name for c in configs] == ["ok"]


class TestSanitizeToolName:
    def test_simple(self):
        assert sanitize_tool_name("github", "create_issue") == "github_create_issue"

    def test_special_chars_replaced(self):
        assert sanitize_tool_name("my server", "do.things!") == "my_server_do_things_"

    def test_truncated_to_64(self):
        name = sanitize_tool_name("a" * 40, "b" * 40)
        assert len(name) == 64


class TestFormatToolResult:
    def test_text_blocks_joined(self):
        result = SimpleNamespace(
            content=[SimpleNamespace(text="hello"), SimpleNamespace(text="world")],
            isError=False,
        )
        assert format_tool_result(result) == "hello\nworld"

    def test_error_flag_prefixes(self):
        result = SimpleNamespace(content=[SimpleNamespace(text="boom")], isError=True)
        assert format_tool_result(result) == "Tool error: boom"

    def test_structured_content_fallback(self):
        result = SimpleNamespace(content=[], structuredContent={"a": 1}, isError=False)
        assert format_tool_result(result) == '{"a": 1}'

    def test_empty_result(self):
        result = SimpleNamespace(content=[], structuredContent=None, isError=False)
        assert format_tool_result(result) == "(empty result)"


class FakeAgent:
    def __init__(self):
        self.tools: dict[str, tuple] = {}

    def register_tool(self, name, handler, schema=None):
        self.tools[name] = (handler, schema)


class FakeSession:
    def __init__(self):
        self.calls: list[tuple] = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return SimpleNamespace(content=[SimpleNamespace(text="ok")], isError=False)


def _connected(name: str, tools: list) -> ExternalMCPConnection:
    connection = ExternalMCPConnection(ExternalServerConfig(name=name, command="fake"))
    connection.session = FakeSession()
    connection.tools = tools
    return connection


class TestRegisterInto:
    @pytest.fixture
    def manager(self):
        tool = SimpleNamespace(
            name="get_weather",
            description="Get the weather.\nLong details here.",
            inputSchema={"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
        )
        mgr = ExternalMCPManager([ExternalServerConfig(name="weather", command="fake")])
        mgr.connections["weather"] = _connected("weather", [tool])
        return mgr

    def test_registers_prefixed_tool_with_schema(self, manager):
        agent = FakeAgent()
        assert manager.register_into(agent) == 1

        handler, schema = agent.tools["weather_get_weather"]
        assert schema["function"]["name"] == "weather_get_weather"
        assert schema["function"]["description"] == "Get the weather."
        assert schema["function"]["parameters"]["required"] == ["city"]

    async def test_handler_calls_session_with_original_name(self, manager):
        agent = FakeAgent()
        manager.register_into(agent)
        handler, _ = agent.tools["weather_get_weather"]

        result = await handler(city="Riyadh")
        assert result == "ok"

        session = manager.connections["weather"].session
        assert session.calls == [("get_weather", {"city": "Riyadh"})]

    def test_disconnected_servers_skipped(self):
        mgr = ExternalMCPManager([ExternalServerConfig(name="dead", command="fake")])
        dead = ExternalMCPConnection(ExternalServerConfig(name="dead", command="fake"))
        dead.error = "spawn failed"
        mgr.connections["dead"] = dead

        agent = FakeAgent()
        assert mgr.register_into(agent) == 0
        assert not agent.tools


class TestStatus:
    def test_status_states(self):
        ok_cfg = ExternalServerConfig(name="ok", command="fake")
        bad_cfg = ExternalServerConfig(name="bad", command="fake")
        off_cfg = ExternalServerConfig(name="off", command="fake", enabled=False)
        mgr = ExternalMCPManager([ok_cfg, bad_cfg, off_cfg])

        mgr.connections["ok"] = _connected("ok", [SimpleNamespace(name="t1")])
        bad = ExternalMCPConnection(bad_cfg)
        bad.error = "boom"
        mgr.connections["bad"] = bad
        off = ExternalMCPConnection(off_cfg)
        off.error = "disabled"
        mgr.connections["off"] = off

        by_name = {entry["name"]: entry for entry in mgr.status()}
        assert by_name["ok"]["state"] == "connected"
        assert by_name["ok"]["tools"] == ["t1"]
        assert by_name["bad"]["state"] == "failed"
        assert by_name["bad"]["detail"] == "boom"
        assert by_name["off"]["state"] == "disabled"


class TestConnectAll:
    async def test_unconfigured_server_marked_failed(self):
        mgr = ExternalMCPManager([ExternalServerConfig(name="empty")])
        await mgr.connect_all(timeout=1)
        assert mgr.connections["empty"].error == "no command or url configured"

    async def test_disabled_server_not_connected(self):
        mgr = ExternalMCPManager([ExternalServerConfig(name="off", command="x", enabled=False)])
        await mgr.connect_all(timeout=1)
        assert mgr.connections["off"].error == "disabled"
        assert not mgr.connections["off"].connected

    async def test_broken_command_fails_gracefully(self):
        mgr = ExternalMCPManager(
            [ExternalServerConfig(name="ghost", command="/nonexistent/binary/definitely-not-real")]
        )
        await mgr.connect_all(timeout=5)
        assert not mgr.connections["ghost"].connected
        assert mgr.connections["ghost"].error
