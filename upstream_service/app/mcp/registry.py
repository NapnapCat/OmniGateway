import time
from typing import Any

from app.agent.tools import AVAILABLE_TOOLS, TOOL_REGISTRY
from app.core.config import settings
from app.mcp.client import MCPClient, MCPTool


class ToolRegistry:
    def __init__(self, client: MCPClient | None = None) -> None:
        self.client = client
        self._mcp_tools: dict[str, MCPTool] = {}
        self._openai_tools_cache: list[dict[str, Any]] | None = None
        self._expires_at = 0.0

    def _mcp_configured(self) -> bool:
        return bool(settings.mcp_enabled and settings.mcp_server_url)

    def _get_client(self) -> MCPClient | None:
        if not self._mcp_configured():
            return None
        if self.client is None:
            self.client = MCPClient(
                settings.mcp_server_url,
                timeout_seconds=settings.mcp_request_timeout_seconds,
            )
        return self.client

    def _local_tool_names(self) -> set[str]:
        return set(TOOL_REGISTRY)

    async def refresh_tools(self, force: bool = False) -> list[MCPTool]:
        now = time.monotonic()
        if not force and self._openai_tools_cache is not None and now < self._expires_at:
            return list(self._mcp_tools.values())

        client = self._get_client()
        if client is None:
            self._mcp_tools = {}
            self._openai_tools_cache = list(AVAILABLE_TOOLS)
            self._expires_at = now + settings.mcp_tool_cache_ttl_seconds
            return []

        try:
            tools = await client.list_tools()
        except Exception as exc:
            print(f"[MCP] tools/list 失败，降级为本地工具: {exc}")
            self._mcp_tools = {}
            self._openai_tools_cache = list(AVAILABLE_TOOLS)
            self._expires_at = now + settings.mcp_tool_cache_ttl_seconds
            return []

        self._mcp_tools = {tool.name: tool for tool in tools}
        self._openai_tools_cache = [tool.to_openai_tool() for tool in tools] or list(AVAILABLE_TOOLS)
        self._expires_at = now + settings.mcp_tool_cache_ttl_seconds
        return tools

    async def list_openai_tools(self) -> list[dict[str, Any]]:
        await self.refresh_tools()
        return list(self._openai_tools_cache or AVAILABLE_TOOLS)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        await self.refresh_tools()

        if name in self._mcp_tools:
            client = self._get_client()
            if client is None:
                return {"error": f"MCP 工具不可用: {name}"}
            try:
                return await client.call_tool(name, arguments)
            except Exception as exc:
                return {"error": f"MCP 工具调用失败: {str(exc)}"}

        if name in self._local_tool_names():
            try:
                return {"content": TOOL_REGISTRY[name](**arguments)}
            except Exception as exc:
                return {"error": f"本地工具调用失败: {str(exc)}"}

        return {"error": f"未知工具: {name}"}

    async def execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        result = await self.call_tool(name, arguments)
        return format_tool_result(result)


def format_tool_result(result: dict[str, Any]) -> str:
    if "error" in result:
        return str(result["error"])

    content = result.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and item.get("text"):
                    parts.append(str(item["text"]))
                elif item.get("content"):
                    parts.append(str(item["content"]))
            elif item is not None:
                parts.append(str(item))
        if parts:
            return "\n".join(parts)

    if "result" in result:
        return str(result["result"])
    return str(result)


tool_registry = ToolRegistry()
