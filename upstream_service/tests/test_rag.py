import asyncio
import json
import sys
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]

if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.agent.graph import graph_app
from app.agent.nodes import RAG_TOKEN_LIMIT, get_token_encoding
from app.services.llm_service import llm_service


def build_long_documents() -> list[str]:
    base_line = (
        "RAG 边界测试文档。关键事实：天穹数据库的主键是 SKY-42，"
        "回滚口令是 ALPHA-OMEGA，维护窗口在周三 03:00。"
    )
    long_document = base_line * 80
    return [long_document for _ in range(10)]


def extract_context_from_messages(messages: list[dict]) -> str:
    if not messages:
        return ""
    system_prompt = messages[0].get("content", "")
    marker = "Background Context:"
    start_index = system_prompt.find(marker)
    if start_index == -1:
        return ""
    return system_prompt[start_index:].strip()


async def run_test() -> None:
    documents = build_long_documents()
    original_total_length = sum(len(document) for document in documents)
    encoding = get_token_encoding()

    initial_state = {
        "messages": [
            {"role": "user", "content": "请告诉我天穹数据库的主键和回滚口令。"}
        ],
        "documents": documents,
        "context_text": "",
        "next_step": "input_node",
        "model": "agent-core-v1",
        "temperature": 0.2,
        "final_response": None,
    }

    async def fake_generate_reply(*, messages, model=None, temperature=0.7):
        context_text = extract_context_from_messages(messages)
        assert context_text, "context_text 没有注入到 system prompt 中"

        context_tokens = len(encoding.encode(context_text))
        assert context_tokens <= RAG_TOKEN_LIMIT, "context_text 超过了 Token 截断阈值"

        has_key_fact = "SKY-42" in context_text
        has_password_fact = "ALPHA-OMEGA" in context_text
        return (
            "[Cyber Hack] 已锁定背景文档。"
            f" 主键=SKY-42({has_key_fact})，回滚口令=ALPHA-OMEGA({has_password_fact})，"
            f" 上下文Token={context_tokens}"
        )

    original_generate_reply = llm_service.generate_reply
    llm_service.generate_reply = fake_generate_reply

    try:
        print("[RAG Test] 开始执行长文档边界测试")
        print(f"[RAG Test] 原本文档总长度: {original_total_length}")
        print(f"[RAG Test] 文档数量: {len(documents)}")

        result = await graph_app.ainvoke(initial_state)
    finally:
        llm_service.generate_reply = original_generate_reply

    context_text = result.get("context_text", "")
    truncated_length = len(context_text)
    truncated_tokens = len(encoding.encode(context_text))
    final_response = result.get("final_response", "")

    print(f"[RAG Test] 截断后的上下文长度: {truncated_length}")
    print(f"[RAG Test] 截断后的上下文Token数: {truncated_tokens}")
    print("[RAG Test] 最终状态:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("[RAG Test] 大模型最终回答:")
    print(final_response)

    assert truncated_tokens <= RAG_TOKEN_LIMIT, "截断后的上下文仍然超过 Token 上限"
    assert "SKY-42" in final_response, "最终回复没有引用文档中的主键"
    assert "ALPHA-OMEGA" in final_response, "最终回复没有引用文档中的回滚口令"


if __name__ == "__main__":
    asyncio.run(run_test())
