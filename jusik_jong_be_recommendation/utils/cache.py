"""
간단한 인메모리 캐시 (TTL 기반)
"""
import time
import threading
from typing import Any, Optional
import config


class Cache:
    def __init__(self, ttl: int = config.CACHE_TTL_SECONDS):
        self._store: dict[str, tuple[Any, float]] = {}
        self._ttl = ttl
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._store:
                return None
            value, timestamp = self._store[key]
            if time.time() - timestamp > self._ttl:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = (value, time.time())

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


# 전역 캐시 인스턴스
_global_cache = Cache()


def get_cache() -> Cache:
    return _global_cache
