import sys
import os
from pathlib import Path
from typing import Any

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]

if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("DEFAULT_MODEL", "test-model")

from app.agent.tools import WEATHER_TOOL_NAME
from app.mcp.client import MCPTool
from app.mcp.registry import ToolRegistry


class FakeMCPClient:
    def __init__(
        self,
        *,
        tools: list[MCPTool] | None = None,
        list_error: Exception | None = None,
        call_result: dict[str, Any] | None = None,
        call_error: Exception | None = None,
    ) -> None:
        self.tools = tools or []
        self.list_error = list_error
        self.call_result = call_result or {"content": [{"type": "text", "text": "ok"}]}
        self.call_error = call_error
        self.list_calls = 0

    async def list_tools(self) -> list[MCPTool]:
        self.list_calls += 1
        if self.list_error:
            raise self.list_error
        return self.tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if self.call_error:
            raise self.call_error
        return self.call_result


@pytest.mark.asyncio
async def test_mcp_tools_list_converts_to_openai_schema(monkeypatch):
    monkeypatch.setattr("app.mcp.registry.settings.mcp_enabled", True)
    monkeypatch.setattr("app.mcp.registry.settings.mcp_server_url", "http://mcp.test/rpc")
    registry = ToolRegistry(
        client=FakeMCPClient(
            tools=[
                MCPTool(
                    name="search_docs",
                    description="Search project docs",
                    input_schema={
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                )
            ]
        )
    )

    tools = await registry.list_openai_tools()

    assert tools == [
        {
            "type": "function",
            "function": {
                "name": "search_docs",
                "description": "Search project docs",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        }
    ]


@pytest.mark.asyncio
async def test_mcp_tools_list_failure_falls_back_to_local_tool(monkeypatch):
    monkeypatch.setattr("app.mcp.registry.settings.mcp_enabled", True)
    monkeypatch.setattr("app.mcp.registry.settings.mcp_server_url", "http://mcp.test/rpc")
    registry = ToolRegistry(client=FakeMCPClient(list_error=RuntimeError("down")))

    tools = await registry.list_openai_tools()

    names = {tool["function"]["name"] for tool in tools}
    assert WEATHER_TOOL_NAME in names


@pytest.mark.asyncio
async def test_mcp_tool_call_success_returns_text(monkeypatch):
    monkeypatch.setattr("app.mcp.registry.settings.mcp_enabled", True)
    monkeypatch.setattr("app.mcp.registry.settings.mcp_server_url", "http://mcp.test/rpc")
    registry = ToolRegistry(
        client=FakeMCPClient(
            tools=[MCPTool("search_docs", "Search docs", {"type": "object", "properties": {}})],
            call_result={"content": [{"type": "text", "text": "matched docs"}]},
        )
    )

    result = await registry.execute_tool("search_docs", {"query": "gateway"})

    assert result == "matched docs"


@pytest.mark.asyncio
async def test_mcp_tool_call_failure_returns_controlled_error(monkeypatch):
    monkeypatch.setattr("app.mcp.registry.settings.mcp_enabled", True)
    monkeypatch.setattr("app.mcp.registry.settings.mcp_server_url", "http://mcp.test/rpc")
    registry = ToolRegistry(
        client=FakeMCPClient(
            tools=[MCPTool("search_docs", "Search docs", {"type": "object", "properties": {}})],
            call_error=TimeoutError("timeout"),
        )
    )

    result = await registry.execute_tool("search_docs", {"query": "gateway"})

    assert "MCP 工具调用失败" in result
    assert "timeout" in result


@pytest.mark.asyncio
async def test_unknown_tool_does_not_crash(monkeypatch):
    monkeypatch.setattr("app.mcp.registry.settings.mcp_enabled", False)
    monkeypatch.setattr("app.mcp.registry.settings.mcp_server_url", None)
    registry = ToolRegistry()

    result = await registry.execute_tool("missing_tool", {})

    assert result == "未知工具: missing_tool"
