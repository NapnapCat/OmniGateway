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


def build_long_state() -> dict[str, Any]:
    messages: list[dict[str, Any]] = []
    for index in range(8):
        messages.append({"role": "user", "content": f"第 {index} 轮无关用户废话"})
        messages.append({"role": "assistant", "content": f"[Cyber Hack] 第 {index} 轮无关助手回复"})
    messages.append({"role": "user", "content": "帮我查一下北京天气"})

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


def build_weather_tool_call() -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "call_weather_beijing",
                "type": "function",
                "function": {
                    "name": WEATHER_TOOL_NAME,
                    "arguments": json.dumps({"city": "北京"}, ensure_ascii=False),
                },
            }
        ],
    }


async def run_test() -> None:
    call_count = 0

    async def fake_generate_message(*, messages, model=None, temperature=0.7, tools=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return build_weather_tool_call()

        tool_content = next(
            (message.get("content", "") for message in reversed(messages) if message.get("role") == "tool"),
            "",
        )
        return {
            "role": "assistant",
            "content": f"[Cyber Hack] 北京天气查询失败，工具回传：{tool_content}",
        }

    def broken_weather_tool(city: str) -> str:
        raise ConnectionError("气象卫星失联")

    original_generate_message = llm_service.generate_message
    original_weather_tool = TOOL_REGISTRY[WEATHER_TOOL_NAME]
    llm_service.generate_message = fake_generate_message
    TOOL_REGISTRY[WEATHER_TOOL_NAME] = broken_weather_tool

    try:
        print("[Full State Machine Test] 开始执行 5 节点鲁棒性测试")
        result = await graph_app.ainvoke(build_long_state())
    finally:
        llm_service.generate_message = original_generate_message
        TOOL_REGISTRY[WEATHER_TOOL_NAME] = original_weather_tool

    final_messages = result.get("messages", [])
    final_response = result.get("final_response", "")

    print(f"[Full State Machine Test] 最终 messages 长度: {len(final_messages)}")
    print("[Full State Machine Test] 最终回复:")
    print(final_response)
    print("[Full State Machine Test] 最终 State:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    assert result.get("next_step") == "end", "图没有正常走到 output_node/END"
    assert len(final_messages) <= MAX_MESSAGE_HISTORY, "消息历史没有被裁剪到合理范围"
    assert "[Cyber Hack]" in final_response, "最终回复缺少赛博黑客人设"
    assert "气象卫星失联" in final_response, "最终回复没有处理工具错误信息"


if __name__ == "__main__":
    asyncio.run(run_test())
