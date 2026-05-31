import hashlib
import json
import re
import time
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.reflection.cache import InMemoryReflectionCache, reflection_cache


ERROR_MARKERS = (
    "工具执行失败",
    "tool_call_timeout",
    "tool_arguments_invalid_json",
    "未知工具",
    "MCP 工具调用失败",
    "本地工具调用失败",
    "核心链路断开",
    "上游大模型服务异常",
    "Traceback",
)

ERROR_EXPLANATION_MARKERS = (
    "失败",
    "错误",
    "超时",
    "未知",
    "无法",
    "原因",
    "已捕获",
    "不可用",
)

VOLATILE_MARKERS = (
    "今天",
    "当前",
    "实时",
    "刚刚",
    "现在",
)


@dataclass(frozen=True)
class ReflectionResult:
    score: float
    passed: bool
    reasons: list[str]
    cacheable: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "passed": self.passed,
            "reasons": list(self.reasons),
            "cacheable": self.cacheable,
        }


class ReflectionService:
    async def evaluate_response(
        self,
        input_messages: list[dict[str, Any]],
        output_text: str | None,
        tool_results: list[dict[str, Any]] | None = None,
    ) -> ReflectionResult:
        text = (output_text or "").strip()
        reasons: list[str] = []
        score = 1.0
        cacheable = True

        if not text:
            return ReflectionResult(
                score=0.0,
                passed=False,
                reasons=["empty_response"],
                cacheable=False,
            )

        if len(text) < 12:
            score -= 0.35
            reasons.append("too_short")

        if self._contains_error_marker(text):
            score -= 0.45
            cacheable = False
            reasons.append("error_marker_in_response")

        if self._tool_error_unexplained(text, tool_results or []):
            score -= 0.35
            cacheable = False
            reasons.append("unexplained_tool_error")

        if self._is_generic_non_answer(text):
            score -= 0.35
            cacheable = False
            reasons.append("generic_non_answer")

        if self._is_volatile(input_messages, text):
            cacheable = False
            reasons.append("volatile_result")

        score = max(0.0, min(1.0, score))
        passed = score >= settings.reflection_min_score
        if not passed and "below_min_score" not in reasons:
            reasons.append("below_min_score")

        return ReflectionResult(
            score=score,
            passed=passed,
            reasons=reasons or ["quality_ok"],
            cacheable=cacheable,
        )

    def build_cache_key(self, input_messages: list[dict[str, Any]]) -> str:
        normalized_messages = []
        for message in input_messages:
            role = str(message.get("role") or "").strip()
            content = self._normalize_text(str(message.get("content") or ""))
            if role and content:
                normalized_messages.append({"role": role, "content": content})

        payload = json.dumps(normalized_messages, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"reflection:{digest}"

    async def evaluate_and_cache(
        self,
        *,
        input_messages: list[dict[str, Any]],
        output_text: str | None,
        tool_results: list[dict[str, Any]] | None = None,
        cache: InMemoryReflectionCache = reflection_cache,
    ) -> ReflectionResult | None:
        if not settings.reflection_enabled:
            return None

        result = await self.evaluate_response(input_messages, output_text, tool_results)
        if not settings.reflection_cache_enabled or not result.passed or not result.cacheable:
            return result

        key = self.build_cache_key(input_messages)
        value = {
            "answer": output_text or "",
            "reflection_score": result.score,
            "reasons": list(result.reasons),
            "created_at": time.time(),
        }
        try:
            await cache.write(key, value, settings.reflection_cache_ttl_seconds)
        except Exception as exc:
            print(f"[Reflection] cache_write_failed error={str(exc)[:200]}")
        return result

    def _contains_error_marker(self, text: str) -> bool:
        return any(marker in text for marker in ERROR_MARKERS)

    def _tool_error_unexplained(self, output_text: str, tool_results: list[dict[str, Any]]) -> bool:
        has_tool_error = any(
            self._contains_error_marker(str(result.get("content") or ""))
            for result in tool_results
        )
        if not has_tool_error:
            return False
        return not any(marker in output_text for marker in ERROR_EXPLANATION_MARKERS)

    def _is_generic_non_answer(self, text: str) -> bool:
        normalized = self._normalize_text(text)
        if normalized in {"不知道", "不清楚", "无法回答", "我不知道"}:
            return True
        return len(normalized) < 8

    def _is_volatile(self, input_messages: list[dict[str, Any]], output_text: str) -> bool:
        combined = output_text + " " + " ".join(str(message.get("content") or "") for message in input_messages)
        return any(marker in combined for marker in VOLATILE_MARKERS)

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()


reflection_service = ReflectionService()
