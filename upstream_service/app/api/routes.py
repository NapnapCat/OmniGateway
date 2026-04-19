import time
import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from app.agent.graph import graph_app
from app.api.schemas import ChatCompletionRequest
from app.services.llm_service import llm_service


router = APIRouter(tags=["Chat"])

@router.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    if request.stream is True:
        return StreamingResponse(
            llm_service.stream_chat(request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    result = await graph_app.ainvoke(
        {
            "messages": [message.model_dump() for message in request.messages],
            "documents": request.documents or [],
            "context_text": "",
            "next_step": "input_node",
            "model": request.model,
            "temperature": request.temperature,
            "final_response": None,
        }
    )
    model_name = llm_service.resolve_model(request.model)
    content = result.get("final_response") or ""

    payload = {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_name,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": "stop",
            }
        ],
    }
    return JSONResponse(content=payload)
