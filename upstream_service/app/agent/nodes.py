import traceback

from app.agent.state import AgentState
from app.agent.tools import AVAILABLE_TOOLS, execute_tool, parse_tool_arguments
from app.core.config import settings
from app.services.llm_service import llm_service
from app.services.rag_service import (
    RAG_TOKEN_LIMIT,
    build_context_text as build_context_text_from_rag_service,
    count_tokens,
    get_token_encoding as get_rag_token_encoding,
)


CYBER_HACK_PREFIX = "[Cyber Hack]"
RAG_INSTRUCTION = "请仅根据提供的背景上下文回答问题。如果上下文不足以回答，请直说不知道。"
MAX_MESSAGE_HISTORY = 10


def ensure_cyber_hack_style(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return f"{CYBER_HACK_PREFIX} 信号回来了，但内容被黑洞吃了。"
    if cleaned.startswith(CYBER_HACK_PREFIX):
        return cleaned
    return f"{CYBER_HACK_PREFIX} {cleaned}"


def get_token_encoding():
    return get_rag_token_encoding()


def has_system_identity(message: dict) -> bool:
    if message.get("role") == "system":
        return True
    content = str(message.get("content") or "")
    return CYBER_HACK_PREFIX in content


def is_tool_call_message(message: dict) -> bool:
    return message.get("role") == "assistant" and bool(message.get("tool_calls"))


def is_tool_result_message(message: dict) -> bool:
    return message.get("role") == "tool"


def prune_message_history(messages: list[dict], max_messages: int = MAX_MESSAGE_HISTORY) -> list[dict]:
    if len(messages) <= max_messages:
        return messages

    preserved_first = messages[0] if messages and has_system_identity(messages[0]) else None
    tail_limit = max_messages - 1 if preserved_first else max_messages
    tail = messages[-tail_limit:]
    paired_tool_call = None

    if tail and is_tool_result_message(tail[0]):
        tool_call_id = tail[0].get("tool_call_id")
        previous_message = messages[: -tail_limit][-1] if len(messages) > tail_limit else None
        if previous_message and is_tool_call_message(previous_message):
            previous_tool_ids = {
                tool_call.get("id")
                for tool_call in previous_message.get("tool_calls", []) or []
            }
            if tool_call_id in previous_tool_ids:
                paired_tool_call = previous_message
                tail = [paired_tool_call, *tail]
                while len(tail) > tail_limit and len(tail) > 1:
                    tail.pop(1)

    pruned_messages = [preserved_first, *tail] if preserved_first else tail
    while len(pruned_messages) > max_messages:
        drop_index = 1 if preserved_first else 0
        if paired_tool_call is not None and pruned_messages[drop_index] is paired_tool_call:
            drop_index += 1
        if drop_index >= len(pruned_messages):
            break
        pruned_messages.pop(drop_index)

    print(f"[Memory] 消息历史过长，已裁剪至 {len(pruned_messages)} 条")
    return pruned_messages


def build_context_text(documents: list[str], token_limit: int = RAG_TOKEN_LIMIT) -> str:
    base_context_text = build_context_text_from_rag_service(documents, token_limit=token_limit)
    if not base_context_text:
        return ""

    context_body = base_context_text
    current_tokens = count_tokens(context_body)
    context_text = f"# Context Tokens: {current_tokens}\n{context_body}"

    while count_tokens(context_text) > token_limit and context_body:
        print("[RAG] 警告：上下文最终检查仍超限，开始执行暴力字符截断")
        context_body = context_body[:-64].rstrip()
        current_tokens = count_tokens(context_body)
        context_text = f"# Context Tokens: {current_tokens}\n{context_body}"

    final_tokens = count_tokens(context_text)
    if final_tokens > token_limit:
        print(f"[RAG] 严重警告：上下文仍超过 {token_limit} Tokens，请检查模板开销估算")

    return context_text


def input_node(state: AgentState) -> AgentState:
    print("收到用户输入")
    return {
        "messages": state.get("messages", []),
        "documents": state.get("documents", []),
        "context_text": state.get("context_text", ""),
        "next_step": "context_node",
        "model": state.get("model"),
        "temperature": state.get("temperature"),
        "tool_rounds": state.get("tool_rounds", 0),
        "final_response": state.get("final_response"),
    }


def context_node(state: AgentState) -> AgentState:
    context_text = build_context_text(state.get("documents", []))
    return {
        "messages": state.get("messages", []),
        "documents": state.get("documents", []),
        "context_text": context_text,
        "next_step": "llm_node",
        "model": state.get("model"),
        "temperature": state.get("temperature"),
        "tool_rounds": state.get("tool_rounds", 0),
        "final_response": state.get("final_response"),
    }


async def llm_node(state: AgentState) -> AgentState:
    system_prompt = settings.default_system_prompt
    context_text = state.get("context_text", "").strip()
    if context_text:
        system_prompt = f"{system_prompt}\n\n{RAG_INSTRUCTION}\n\n{context_text}"

    pruned_history = prune_message_history(state.get("messages", []))
    messages = [{"role": "system", "content": system_prompt}, *pruned_history]

    try:
        assistant_message = await llm_service.generate_message(
            messages=messages,
            model=state.get("model"),
            temperature=state.get("temperature", 0.7),
            tools=AVAILABLE_TOOLS,
        )
        if not assistant_message.get("tool_calls"):
            assistant_message["content"] = ensure_cyber_hack_style(
                str(assistant_message.get("content") or "")
            )
        can_call_tool = state.get("tool_rounds", 0) < 1
        next_step = "action_node" if assistant_message.get("tool_calls") and can_call_tool else "output_node"
    except AssertionError:
        traceback.print_exc()
        raise
    except Exception:
        assistant_message = {
            "role": "assistant",
            "content": f"{CYBER_HACK_PREFIX} 核心链路断开，该死的服务器又在装死。",
        }
        next_step = "output_node"

    updated_messages = [
        *pruned_history,
        assistant_message,
    ]

    return {
        "messages": updated_messages,
        "documents": state.get("documents", []),
        "context_text": state.get("context_text", ""),
        "next_step": next_step,
        "model": state.get("model"),
        "temperature": state.get("temperature"),
        "tool_rounds": state.get("tool_rounds", 0),
        "final_response": state.get("final_response"),
    }


def action_node(state: AgentState) -> AgentState:
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else {}
    tool_messages = []

    for tool_call in last_message.get("tool_calls", []) or []:
        function_info = tool_call.get("function", {})
        tool_name = function_info.get("name", "")
        arguments = parse_tool_arguments(function_info.get("arguments"))
        try:
            result = execute_tool(tool_name, arguments)
        except Exception as exc:
            result = f"工具执行失败: {str(exc)}"
        tool_messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.get("id"),
                "name": tool_name,
                "content": result,
            }
        )

    return {
        "messages": [*messages, *tool_messages],
        "documents": state.get("documents", []),
        "context_text": state.get("context_text", ""),
        "next_step": "llm_node",
        "model": state.get("model"),
        "temperature": state.get("temperature"),
        "tool_rounds": state.get("tool_rounds", 0) + 1,
        "final_response": state.get("final_response"),
    }


def output_node(state: AgentState) -> AgentState:
    print("工作流执行完毕")
    pruned_messages = prune_message_history(state.get("messages", []))
    assistant_messages = [
        message
        for message in pruned_messages
        if message.get("role") == "assistant"
    ]
    final_response = assistant_messages[-1]["content"] if assistant_messages else None

    return {
        "messages": pruned_messages,
        "documents": state.get("documents", []),
        "context_text": state.get("context_text", ""),
        "next_step": "end",
        "model": state.get("model"),
        "temperature": state.get("temperature"),
        "tool_rounds": state.get("tool_rounds", 0),
        "final_response": final_response,
    }
