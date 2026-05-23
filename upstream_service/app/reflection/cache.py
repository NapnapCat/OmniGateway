import time
from typing import Any


class InMemoryReflectionCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, dict[str, Any]]] = {}

    async def write(self, key: str, value: dict[str, Any], ttl_seconds: float) -> None:
        expires_at = time.time() + max(0, ttl_seconds)
        self._store[key] = (expires_at, value)

    async def get(self, key: str) -> dict[str, Any] | None:
        item = self._store.get(key)
        if item is None:
            return None

        expires_at, value = item
        if expires_at < time.time():
            self._store.pop(key, None)
            return None
        return value

    def clear(self) -> None:
        self._store.clear()


reflection_cache = InMemoryReflectionCache()
