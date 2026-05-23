from typing import Any, NotRequired, TypedDict


class AgentState(TypedDict):
    messages: list[dict[str, Any]]
    documents: list[str]
    context_text: str
    next_step: str
    model: NotRequired[str | None]
    temperature: NotRequired[float | None]
    tool_rounds: NotRequired[int]
    final_response: NotRequired[str | None]
    reflection: NotRequired[dict[str, Any] | None]
