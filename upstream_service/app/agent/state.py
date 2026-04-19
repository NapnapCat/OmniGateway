from typing import NotRequired, TypedDict


class AgentState(TypedDict):
    messages: list[dict[str, str]]
    documents: list[str]
    context_text: str
    next_step: str
    model: NotRequired[str | None]
    temperature: NotRequired[float | None]
    final_response: NotRequired[str | None]
