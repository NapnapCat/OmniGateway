import itertools
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "MCPTool":
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ValueError("MCP tool is missing name")

        description = str(payload.get("description") or f"MCP tool: {name}")
        input_schema = payload.get("inputSchema") or payload.get("input_schema") or {}
        if not isinstance(input_schema, dict):
            input_schema = {}
        if not input_schema:
            input_schema = {"type": "object", "properties": {}}

        return cls(name=name, description=description, input_schema=input_schema)

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


class MCPClient:
    def __init__(self, server_url: str, timeout_seconds: float = 10) -> None:
        self.server_url = server_url
        self.timeout_seconds = timeout_seconds
        self._ids = itertools.count(1)

    async def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        packet = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": next(self._ids),
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(self.server_url, json=packet)
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, dict):
            raise ValueError("MCP response must be a JSON object")
        if payload.get("error"):
            error = payload["error"]
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise RuntimeError(f"MCP {method} failed: {message}")
        result = payload.get("result")
        return result if isinstance(result, dict) else {}

    async def list_tools(self) -> list[MCPTool]:
        result = await self._request("tools/list")
        raw_tools = result.get("tools", [])
        if not isinstance(raw_tools, list):
            return []

        tools: list[MCPTool] = []
        for raw_tool in raw_tools:
            if isinstance(raw_tool, dict):
                tools.append(MCPTool.from_payload(raw_tool))
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments,
            },
        )
