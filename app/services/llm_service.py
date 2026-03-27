import json
import time
import uuid
from typing import AsyncGenerator

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
        if requested_model and requested_model != "agent-core-v1":
            return requested_model
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
