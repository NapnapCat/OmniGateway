import asyncio
import os
import sys
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

from app.agent.tool_executor import execute_tool_calls


pytestmark = pytest.mark.asyncio


def make_tool_call(call_id: str, name: str, arguments: str = "{}") -> dict[str, Any]:
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": arguments,
        },
    }


class FakeRegistry:
    def __init__(
        self,
        *,
        delays: dict[str, float] | None = None,
        failures: set[str] | None = None,
        unknown: set[str] | None = None,
    ) -> None:
        self.delays = delays or {}
        self.failures = failures or set()
        self.unknown = unknown or set()
        self.active = 0
        self.max_active = 0

    async def execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(self.delays.get(name, 0))
            if name in self.failures:
                raise RuntimeError(f"{name} failed")
            if name in self.unknown:
                return f"未知工具: {name}"
            return f"{name}:{arguments.get('value', '')}"
        finally:
            self.active -= 1


async def test_multiple_tool_calls_run_concurrently():
    registry = FakeRegistry(delays={"slow_a": 0.05, "slow_b": 0.05})
    tool_calls = [
        make_tool_call("call_a", "slow_a", '{"value":"A"}'),
        make_tool_call("call_b", "slow_b", '{"value":"B"}'),
    ]

    started = asyncio.get_running_loop().time()
    messages = await execute_tool_calls(tool_calls, registry=registry, max_concurrency=2)
    elapsed = asyncio.get_running_loop().time() - started

    assert elapsed < 0.09
    assert registry.max_active == 2
    assert [message["content"] for message in messages] == ["slow_a:A", "slow_b:B"]


async def test_tool_failure_does_not_block_other_results():
    registry = FakeRegistry(failures={"bad_tool"})
    tool_calls = [
        make_tool_call("call_ok", "ok_tool", '{"value":"ok"}'),
        make_tool_call("call_bad", "bad_tool", '{"value":"bad"}'),
        make_tool_call("call_after", "after_tool", '{"value":"after"}'),
    ]

    messages = await execute_tool_calls(tool_calls, registry=registry, max_concurrency=3)

    assert messages[0]["content"] == "ok_tool:ok"
    assert "工具执行失败" in messages[1]["content"]
    assert "bad_tool failed" in messages[1]["content"]
    assert messages[2]["content"] == "after_tool:after"


async def test_tool_message_order_matches_input_order():
    registry = FakeRegistry(delays={"first": 0.04, "second": 0.01, "third": 0})
    tool_calls = [
        make_tool_call("call_1", "first", '{"value":"1"}'),
        make_tool_call("call_2", "second", '{"value":"2"}'),
        make_tool_call("call_3", "third", '{"value":"3"}'),
    ]

    messages = await execute_tool_calls(tool_calls, registry=registry, max_concurrency=3)

    assert [message["tool_call_id"] for message in messages] == ["call_1", "call_2", "call_3"]
    assert [message["name"] for message in messages] == ["first", "second", "third"]


async def test_unknown_tool_returns_controlled_error():
    registry = FakeRegistry(unknown={"missing_tool"})
    messages = await execute_tool_calls(
        [make_tool_call("call_missing", "missing_tool")],
        registry=registry,
    )

    assert messages[0]["content"] == "未知工具: missing_tool"


async def test_invalid_tool_arguments_returns_controlled_error_without_calling_registry():
    registry = FakeRegistry()
    messages = await execute_tool_calls(
        [make_tool_call("call_invalid", "some_tool", "{not-json")],
        registry=registry,
    )

    assert "tool_arguments_invalid_json" in messages[0]["content"]
    assert registry.max_active == 0


async def test_tool_call_timeout_returns_controlled_error():
    registry = FakeRegistry(delays={"slow_tool": 0.05})
    messages = await execute_tool_calls(
        [make_tool_call("call_timeout", "slow_tool")],
        registry=registry,
        timeout_seconds=0.01,
    )

    assert "tool_call_timeout" in messages[0]["content"]
    assert "Tool call timed out" in messages[0]["content"]


async def test_max_concurrency_limit_is_respected():
    registry = FakeRegistry(delays={f"tool_{index}": 0.02 for index in range(6)})
    tool_calls = [
        make_tool_call(f"call_{index}", f"tool_{index}", f'{{"value":"{index}"}}')
        for index in range(6)
    ]

    messages = await execute_tool_calls(tool_calls, registry=registry, max_concurrency=2)

    assert registry.max_active == 2
    assert [message["tool_call_id"] for message in messages] == [f"call_{index}" for index in range(6)]
