"""
시황 + 미국 선물 지수 스코어링
"""
from typing import Optional
import config


def score_market_sentiment(market_data: Optional[dict]) -> float:
    """
    KOSPI/KOSDAQ 시황 스코어 [0.0 ~ 1.0]
    - crash:   0.0
    - bearish: 0.2
    - neutral: 0.5
    - bullish: 0.85~1.0
    """
    if not market_data:
        return 0.5

    bias = market_data.get("market_bias", "neutral")

    if bias == "crash":
        return 0.0
    if bias == "bearish":
        return 0.2

    kospi  = market_data.get("kospi", {}).get("change_pct", 0)
    kosdaq = market_data.get("kosdaq", {}).get("change_pct", 0)

    # 두 지수 평균 변화율 기반 스코어
    avg_chg = (kospi + kosdaq) / 2

    if avg_chg >= 1.5:
        return 1.0
    elif avg_chg >= 1.0:
        return 0.9
    elif avg_chg >= 0.5:
        return 0.8
    elif avg_chg >= 0.2:
        return 0.65
    elif avg_chg >= 0:
        return 0.55
    else:
        return 0.3


def score_us_futures(futures_data: Optional[dict]) -> float:
    """
    미국 선물 스코어 [0.0 ~ 1.0]
    VIX 고려한 위험자산 선호도
    """
    if not futures_data:
        return 0.5

    avg_chg   = futures_data.get("avg_change", 0.0)
    vix       = futures_data.get("vix", 20.0)
    sentiment = futures_data.get("sentiment", "neutral")

    # 기본 스코어 (선물 등락률 기반)
    if avg_chg >= 0.5:
        base_score = 0.85
    elif avg_chg >= 0.2:
        base_score = 0.70
    elif avg_chg >= 0:
        base_score = 0.55
    elif avg_chg >= -0.2:
        base_score = 0.40
    elif avg_chg >= -0.5:
        base_score = 0.25
    else:
        base_score = 0.10

    # VIX 페널티
    if vix > 35:
        vix_mult = 0.4
    elif vix > 30:
        vix_mult = 0.6
    elif vix > 25:
        vix_mult = 0.75
    elif vix > 20:
        vix_mult = 0.9
    else:
        vix_mult = 1.0

    return round(base_score * vix_mult, 3)


def is_market_killswitch(market_data: Optional[dict]) -> tuple[bool, str]:
    """
    시장 킬스위치 확인
    Returns: (should_stop, reason)
    """
    if not market_data:
        return False, ""

    bias = market_data.get("market_bias", "neutral")
    kospi_chg = market_data.get("kospi", {}).get("change_pct", 0)

    if bias == "crash" or kospi_chg <= config.MARKET_CRASH_THRESHOLD:
        return True, f"KOSPI 급락 ({kospi_chg:.2f}%) - 종가 베팅 부적합"

    return False, ""
