"""
KST 시간 유틸리티
"""
from datetime import datetime, time
import pytz
import config

KST = pytz.timezone("Asia/Seoul")


def now_kst() -> datetime:
    return datetime.now(KST)


def today_str() -> str:
    """pykrx용 날짜 문자열 YYYYMMDD"""
    return now_kst().strftime("%Y%m%d")


def is_market_open() -> bool:
    """현재 장중인지 확인"""
    now = now_kst()
    if now.weekday() >= 5:  # 주말
        return False
    open_t  = time(config.MARKET_OPEN_HOUR,  config.MARKET_OPEN_MINUTE)
    close_t = time(config.MARKET_CLOSE_HOUR, config.MARKET_CLOSE_MINUTE)
    return open_t <= now.time() <= close_t


def is_optimal_run_time() -> bool:
    """최적 실행 시간대인지 확인 (14:30~15:10)"""
    now = now_kst()
    start_t = time(config.OPTIMAL_RUN_HOUR_START, config.OPTIMAL_RUN_MIN_START)
    end_t   = time(config.OPTIMAL_RUN_HOUR_END,   config.OPTIMAL_RUN_MIN_END)
    return start_t <= now.time() <= end_t


def minutes_to_close() -> int:
    """장 마감까지 남은 분"""
    now = now_kst()
    close = now.replace(
        hour=config.MARKET_CLOSE_HOUR,
        minute=config.MARKET_CLOSE_MINUTE,
        second=0,
        microsecond=0
    )
    delta = close - now
    return max(0, int(delta.total_seconds() / 60))


def get_prev_business_day(date_str: str) -> str:
    """이전 영업일 반환 (간단 구현: 주말 건너뜀)"""
    from datetime import timedelta
    dt = datetime.strptime(date_str, "%Y%m%d")
    dt -= timedelta(days=1)
    while dt.weekday() >= 5:
        dt -= timedelta(days=1)
    return dt.strftime("%Y%m%d")
