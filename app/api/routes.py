from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.api.schemas import ChatCompletionRequest
from app.services.llm_service import llm_service


router = APIRouter(tags=["Chat"])

@router.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest) -> StreamingResponse:
    if request.stream is not True:
        raise HTTPException(
            status_code=400,
            detail="当前网关仅支持流式请求 (stream=True)",
        )

    return StreamingResponse(
        llm_service.stream_chat(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
