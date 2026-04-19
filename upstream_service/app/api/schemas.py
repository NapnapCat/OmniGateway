from pydantic import BaseModel, Field
from typing import List, Optional

# ==========================================
# 1. 基础消息结构 (严格对齐 OpenAI)
# ==========================================
class ChatMessage(BaseModel):
    role: str = Field(..., description="消息发送者的角色，通常为 'user', 'assistant' 或 'system'")
    content: str = Field(..., description="消息的具体文本内容")

# ==========================================
# 2. 接收请求的模型 (客户端 -> Python服务)
# ==========================================
class ChatCompletionRequest(BaseModel):
    model: str = Field(
        default="agent-core-v1",
        description="请求调用的模型名称；传 agent-core-v1 时会回退到服务端默认模型",
    )
    messages: List[ChatMessage] = Field(..., description="历史对话列表，最后一项为当前问题")
    documents: Optional[List[str]] = Field(default=None, description="可选 RAG 文档列表")
    stream: Optional[bool] = Field(default=False, description="是否使用 SSE 流式输出")
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0, description="大模型的发散度")

    # 预留给后续 Agent 和 MCP 的扩展字段 (比如强行指定只用哪个工具)
    tool_choice: Optional[str] = None
    
