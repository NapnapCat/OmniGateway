import asyncio
import json
import sys
from pathlib import Path
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]

if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.agent.graph import graph_app
from app.agent.nodes import MAX_MESSAGE_HISTORY
from app.agent.tools import TOOL_REGISTRY, WEATHER_TOOL_NAME
from app.services.llm_service import llm_service


def build_long_history() -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for index in range(8):
        messages.append({"role": "user", "content": f"第 {index} 轮废话用户消息"})
        messages.append({"role": "assistant", "content": f"[Cyber Hack] 第 {index} 轮废话助手回复"})
    messages.append({"role": "user", "content": "帮我查一下上海天气"})
    return messages


def build_initial_state(messages: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "messages": messages,
        "documents": [],
        "context_text": "",
        "next_step": "input_node",
        "model": "agent-core-v1",
        "temperature": 0.2,
        "tool_rounds": 0,
        "final_response": None,
    }


def make_tool_call_message(call_id: str = "call_weather_shanghai") -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": WEATHER_TOOL_NAME,
                    "arguments": json.dumps({"city": "上海"}, ensure_ascii=False),
                },
            }
        ],
    }


async def collect_graph_run(initial_state: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    visited_nodes: list[str] = []
    final_state: dict[str, Any] = {}

    async for update in graph_app.astream(initial_state, stream_mode="updates"):
        for node_name, state_update in update.items():
            visited_nodes.append(node_name)
            final_state.update(state_update)
            print(f"[Chaos Test] 节点完成: {node_name}, next_step={state_update.get('next_step')}")

    return final_state, visited_nodes


async def test_memory_pruning() -> None:
    call_count = 0

    async def fake_generate_message(*, messages, model=None, temperature=0.7, tools=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return make_tool_call_message()

        tool_content = next(
            (message.get("content", "") for message in reversed(messages) if message.get("role") == "tool"),
            "",
        )
        return {
            "role": "assistant",
            "content": f"[Cyber Hack] 上海天气链路回传：{tool_content}",
        }

    original_generate_message = llm_service.generate_message
    llm_service.generate_message = fake_generate_message

    try:
        final_state, visited_nodes = await collect_graph_run(build_initial_state(build_long_history()))
    finally:
        llm_service.generate_message = original_generate_message

    print("[Chaos Test] 消息裁剪测试节点顺序:")
    print(" -> ".join(visited_nodes))
    print(f"[Chaos Test] 最终 messages 长度: {len(final_state.get('messages', []))}")

    assert len(final_state.get("messages", [])) <= MAX_MESSAGE_HISTORY + 2, (
        "最终消息没有被压制在合理长度内"
    )
    assert final_state.get("final_response", "").startswith("[Cyber Hack]")


async def test_tool_error_self_healing() -> None:
    call_count = 0

    async def fake_generate_message(*, messages, model=None, temperature=0.7, tools=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return make_tool_call_message("call_weather_timeout")

        tool_content = next(
            (message.get("content", "") for message in reversed(messages) if message.get("role") == "tool"),
            "",
        )
        return {
            "role": "assistant",
            "content": f"[Cyber Hack] 天气工具失败，已捕获原因：{tool_content}",
        }

    def broken_weather_tool(city: str) -> str:
        raise TimeoutError("气象局接口超时响应")

    original_generate_message = llm_service.generate_message
    original_weather_tool = TOOL_REGISTRY[WEATHER_TOOL_NAME]
    llm_service.generate_message = fake_generate_message
    TOOL_REGISTRY[WEATHER_TOOL_NAME] = broken_weather_tool

    try:
        final_state, visited_nodes = await collect_graph_run(
            build_initial_state([{"role": "user", "content": "帮我查一下上海天气"}])
        )
    finally:
        llm_service.generate_message = original_generate_message
        TOOL_REGISTRY[WEATHER_TOOL_NAME] = original_weather_tool

    effective_order = [node for node in visited_nodes if node != "context_node"]
    final_response = final_state.get("final_response", "")

    print("[Chaos Test] 工具错误自愈测试节点顺序:")
    print(" -> ".join(visited_nodes))
    print("[Chaos Test] 最终回复:")
    print(final_response)

    assert effective_order == [
        "input_node",
        "llm_node",
        "action_node",
        "llm_node",
        "output_node",
    ]
    assert "[Cyber Hack]" in final_response
    assert "气象局接口超时响应" in final_response


async def run_test() -> None:
    print("[Chaos Test] 场景 1：消息裁剪")
    await test_memory_pruning()
    print("[Chaos Test] 场景 2：工具崩溃自愈")
    await test_tool_error_self_healing()


if __name__ == "__main__":
    asyncio.run(run_test())
