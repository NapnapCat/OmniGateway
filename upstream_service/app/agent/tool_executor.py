import asyncio
import json
from typing import Any

from app.core.config import settings
from app.mcp.registry import ToolRegistry, tool_registry


def _safe_error_message(exc: Exception) -> str:
    return str(exc).splitlines()[0][:200]


def _tool_log(tool_name: str, tool_call_id: str | None, status: str, error: str | None = None) -> None:
    base = f"[Tool] name={tool_name or '<missing>'} id={tool_call_id or '<missing>'} status={status}"
    if error:
        base = f"{base} error={error}"
    print(base)


def parse_tool_arguments_strict(raw_arguments: str | dict[str, Any] | None) -> tuple[dict[str, Any], str | None]:
    if raw_arguments is None:
        return {}, None
    if isinstance(raw_arguments, dict):
        return raw_arguments, None
    if not isinstance(raw_arguments, str):
        return {}, "tool_arguments_invalid_json"
    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError:
        return {}, "tool_arguments_invalid_json"
    if not isinstance(parsed, dict):
        return {}, "tool_arguments_invalid_json"
    return parsed, None


def build_tool_message(tool_call: dict[str, Any], content: str) -> dict[str, Any]:
    function_info = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}
    return {
        "role": "tool",
        "tool_call_id": tool_call.get("id") if isinstance(tool_call, dict) else None,
        "name": function_info.get("name", "") if isinstance(function_info, dict) else "",
        "content": content,
    }


async def _execute_one_tool_call(
    tool_call: dict[str, Any],
    *,
    registry: ToolRegistry,
    semaphore: asyncio.Semaphore,
    timeout_seconds: float,
) -> dict[str, Any]:
    function_info = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}
    tool_name = function_info.get("name", "") if isinstance(function_info, dict) else ""
    tool_call_id = tool_call.get("id") if isinstance(tool_call, dict) else None
    arguments, parse_error = parse_tool_arguments_strict(
        function_info.get("arguments") if isinstance(function_info, dict) else None
    )

    if parse_error:
        _tool_log(tool_name, tool_call_id, "failure", parse_error)
        return build_tool_message(
            tool_call,
            '{"error":"tool_arguments_invalid_json","message":"Tool arguments must be a JSON object"}',
        )

    async with semaphore:
        try:
            result = await asyncio.wait_for(
                registry.execute_tool(tool_name, arguments),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            _tool_log(tool_name, tool_call_id, "failure", "tool_call_timeout")
            result = '{"error":"tool_call_timeout","message":"Tool call timed out"}'
        except Exception as exc:
            error_message = _safe_error_message(exc)
            _tool_log(tool_name, tool_call_id, "failure", error_message)
            result = f"工具执行失败: {error_message}"
        else:
            if result.startswith("未知工具:") or "工具调用失败" in result or "工具不可用" in result:
                _tool_log(tool_name, tool_call_id, "failure", result[:200])
            else:
                _tool_log(tool_name, tool_call_id, "success")

    return build_tool_message(tool_call, result)


async def execute_tool_calls(
    tool_calls: list[dict[str, Any]],
    *,
    registry: ToolRegistry = tool_registry,
    max_concurrency: int | None = None,
    timeout_seconds: float | None = None,
) -> list[dict[str, Any]]:
    if not tool_calls:
        return []

    concurrency = max(1, max_concurrency or settings.mcp_tool_max_concurrency)
    configured_timeout = timeout_seconds if timeout_seconds is not None else settings.mcp_tool_call_timeout_seconds
    timeout = max(0.001, configured_timeout)
    semaphore = asyncio.Semaphore(concurrency)

    tasks = [
        _execute_one_tool_call(
            tool_call,
            registry=registry,
            semaphore=semaphore,
            timeout_seconds=timeout,
        )
        for tool_call in tool_calls
    ]
    return await asyncio.gather(*tasks)
