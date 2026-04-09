"""
모든 콜렉터의 추상 기반 클래스
"""
from abc import ABC, abstractmethod
from typing import Any, Optional
import time
from utils.cache import Cache
from utils.logger import get_logger


class BaseCollector(ABC):
    def __init__(self, cache: Cache):
        self._cache = cache
        self._logger = get_logger(self.__class__.__name__)

    @abstractmethod
    def collect(self) -> Optional[dict]:
        """데이터 수집. 실패 시 None 반환"""
        ...

    def _fetch_with_retry(
        self,
        fn,
        *args,
        max_retries: int = 3,
        backoff: float = 2.0,
        **kwargs,
    ) -> Optional[Any]:
        """지수 백오프 재시도 래퍼"""
        last_exc = None
        for attempt in range(max_retries):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                wait = backoff ** attempt
                self._logger.warning(
                    f"[{self.__class__.__name__}] 시도 {attempt + 1}/{max_retries} 실패: {exc}. "
                    f"{wait:.1f}초 후 재시도"
                )
                time.sleep(wait)
        self._logger.error(
            f"[{self.__class__.__name__}] 최대 재시도 초과. 마지막 오류: {last_exc}"
        )
        return None
