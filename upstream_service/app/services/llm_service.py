import json
import time
import uuid
from typing import Any, AsyncGenerator

from openai import AsyncOpenAI

from app.api.schemas import ChatCompletionRequest
from app.core.config import settings


class LLMService:
    def __init__(self) -> None:
        if not settings.supports_openai_compatible:
            raise ValueError(
                f"Unsupported API_INTERFACE: {settings.api_interface}. "
                "Only 'openai_compatible' is supported now."
            )
        self.client = AsyncOpenAI(
            api_key=settings.api_key,
            base_url=settings.api_base_url,
            timeout=settings.request_timeout,
        )

    def resolve_model(self, requested_model: str | None) -> str:
        normalized_model = (requested_model or "").strip()
        if normalized_model and normalized_model != "agent-core-v1":
            return normalized_model
        return settings.default_model

    def build_chunk_payload(
        self,
        *,
        chunk_id: str,
        created: int,
        model_name: str,
        delta: dict,
        finish_reason: str | None,
    ) -> str:
        payload = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "delta": delta,
                    "finish_reason": finish_reason,
                }
            ],
        }
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def build_messages(self, request: ChatCompletionRequest) -> list[dict]:
        messages = [
            {
                "role": "system",
                "content": settings.default_system_prompt,
            }
        ]
        messages.extend(message.model_dump() for message in request.messages)
        return messages

    async def generate_reply(
        self,
        *,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = 0.7,
    ) -> str:
        model_name = self.resolve_model(model)
        response = await self.client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            stream=False,
        )

        choice = response.choices[0] if response.choices else None
        if choice is None or choice.message is None:
            return ""

        content = choice.message.content
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                text_value = getattr(item, "text", None)
                if text_value:
                    parts.append(text_value)
            return "".join(parts)

        return ""

    async def generate_message(
        self,
        *,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = 0.7,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        model_name = self.resolve_model(model)
        request_kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if tools:
            request_kwargs["tools"] = tools
            request_kwargs["tool_choice"] = "auto"

        response = await self.client.chat.completions.create(**request_kwargs)
        choice = response.choices[0] if response.choices else None
        if choice is None or choice.message is None:
            return {"role": "assistant", "content": ""}

        message = choice.message
        tool_calls = getattr(message, "tool_calls", None)
        payload: dict[str, Any] = {
            "role": "assistant",
            "content": message.content if tool_calls else (message.content or ""),
        }
        reasoning_content = getattr(message, "reasoning_content", None)
        if reasoning_content:
            payload["reasoning_content"] = reasoning_content

        if tool_calls:
            payload["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": tool_call.type,
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
                for tool_call in tool_calls
            ]

        return payload

    async def stream_chat(
        self, request: ChatCompletionRequest
    ) -> AsyncGenerator[str, None]:
        chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = int(time.time())
        role_sent = False
        model_name = request.model or "unknown-model"

        try:
            model_name = self.resolve_model(request.model)
            messages = self.build_messages(request)
            stream = await self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=request.temperature,
                stream=True,
            )

            async for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None
                if choice is None:
                    continue

                delta = {}
                if not role_sent:
                    delta["role"] = "assistant"
                    role_sent = True

                content = getattr(choice.delta, "content", None)
                if content:
                    delta["content"] = content

                yield self.build_chunk_payload(
                    chunk_id=chunk_id,
                    created=created,
                    model_name=model_name,
                    delta=delta,
                    finish_reason=choice.finish_reason,
                )

            yield self.build_chunk_payload(
                chunk_id=chunk_id,
                created=created,
                model_name=model_name,
                delta={},
                finish_reason="stop",
            )
        except Exception as exc:
            yield self.build_chunk_payload(
                chunk_id=chunk_id,
                created=created,
                model_name=model_name,
                delta={"content": f"[网关拦截] 上游大模型服务异常: {str(exc)}"},
                finish_reason="stop",
            )

        yield "data: [DONE]\n\n"


llm_service = LLMService()
