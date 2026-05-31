import os
import sys
from pathlib import Path

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]

if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("DEFAULT_MODEL", "test-model")

from app.reflection.cache import InMemoryReflectionCache
from app.reflection.service import ReflectionService


pytestmark = pytest.mark.asyncio


def messages():
    return [{"role": "user", "content": "解释 Python 的主要用途"}]


async def test_high_quality_answer_passes(monkeypatch):
    monkeypatch.setattr("app.reflection.service.settings.reflection_min_score", 0.7)
    service = ReflectionService()

    result = await service.evaluate_response(
        messages(),
        "Python 主要用于后端服务、数据分析、自动化脚本和机器学习开发，适合快速构建可维护的软件。",
    )

    assert result.passed is True
    assert result.score >= 0.7
    assert result.cacheable is True


async def test_empty_answer_fails():
    result = await ReflectionService().evaluate_response(messages(), "")

    assert result.passed is False
    assert result.score == 0
    assert result.cacheable is False


async def test_unexplained_tool_error_is_not_cacheable():
    result = await ReflectionService().evaluate_response(
        messages(),
        "任务已经处理完成。",
        tool_results=[{"role": "tool", "content": "工具执行失败: timeout"}],
    )

    assert result.cacheable is False
    assert "unexplained_tool_error" in result.reasons


async def test_passed_cacheable_response_writes_cache(monkeypatch):
    monkeypatch.setattr("app.reflection.service.settings.reflection_enabled", True)
    monkeypatch.setattr("app.reflection.service.settings.reflection_cache_enabled", True)
    monkeypatch.setattr("app.reflection.service.settings.reflection_min_score", 0.7)
    cache = InMemoryReflectionCache()
    service = ReflectionService()

    result = await service.evaluate_and_cache(
        input_messages=messages(),
        output_text="Python 可以用于 Web 服务、数据处理和自动化任务，生态成熟且开发效率高。",
        cache=cache,
    )

    cached = await cache.get(service.build_cache_key(messages()))
    assert result is not None and result.passed is True
    assert cached is not None
    assert cached["reflection_score"] >= 0.7


async def test_low_score_response_does_not_write_cache(monkeypatch):
    monkeypatch.setattr("app.reflection.service.settings.reflection_enabled", True)
    monkeypatch.setattr("app.reflection.service.settings.reflection_cache_enabled", True)
    monkeypatch.setattr("app.reflection.service.settings.reflection_min_score", 0.7)
    cache = InMemoryReflectionCache()
    service = ReflectionService()

    result = await service.evaluate_and_cache(
        input_messages=messages(),
        output_text="嗯",
        cache=cache,
    )

    assert result is not None and result.passed is False
    assert await cache.get(service.build_cache_key(messages())) is None


async def test_cache_write_failure_does_not_block_response(monkeypatch):
    class BrokenCache:
        async def write(self, key, value, ttl_seconds):
            raise RuntimeError("cache down")

    monkeypatch.setattr("app.reflection.service.settings.reflection_enabled", True)
    monkeypatch.setattr("app.reflection.service.settings.reflection_cache_enabled", True)
    monkeypatch.setattr("app.reflection.service.settings.reflection_min_score", 0.7)

    result = await ReflectionService().evaluate_and_cache(
        input_messages=messages(),
        output_text="Python 可以用于 Web 服务、自动化、数据分析和机器学习，适合快速开发。",
        cache=BrokenCache(),
    )

    assert result is not None and result.passed is True


async def test_reflection_disabled_skips_scoring_and_cache(monkeypatch):
    monkeypatch.setattr("app.reflection.service.settings.reflection_enabled", False)
    cache = InMemoryReflectionCache()
    service = ReflectionService()

    result = await service.evaluate_and_cache(
        input_messages=messages(),
        output_text="Python 可以用于 Web 服务、自动化、数据分析和机器学习。",
        cache=cache,
    )

    assert result is None
    assert await cache.get(service.build_cache_key(messages())) is None


async def test_cache_key_is_stable_for_same_input():
    service = ReflectionService()

    first = service.build_cache_key(messages())
    second = service.build_cache_key([{"role": "user", "content": "解释   Python 的主要用途"}])

    assert first == second
