"""
가격/거래대금 모멘텀 스코어링
"""
import math
from typing import Optional


def score_momentum(ticker: str, stock_data: dict) -> float:
    """
    가격 + 거래대금 모멘텀 스코어 [0.0 ~ 1.0]

    구성:
    - 당일 가격 변화율 (open → current close)
    - 거래대금 수준 (절대값 기준)
    - 고가/저가 위치 (당일 강도)
    """
    info = stock_data.get(ticker, {})
    open_p  = info.get("open", 0)
    high    = info.get("high", 0)
    low     = info.get("low", 0)
    close   = info.get("close", 0)
    volume  = info.get("volume", 0)
    tv      = info.get("trading_value", 0)

    if open_p <= 0 or close <= 0:
        return 0.5

    # 가격 변화율 (시가 대비)
    price_chg = (close - open_p) / open_p * 100

    # 당일 강도: 종가가 고-저 범위에서 어느 위치인가
    if high > low:
        strength = (close - low) / (high - low)  # 0: 저가권, 1: 고가권
    else:
        strength = 0.5

    # 가격 변화율 스코어 (시그모이드)
    price_score = 1 / (1 + math.exp(-price_chg * 0.4))

    # 강도 스코어 (0~1 그대로 사용)
    strength_score = strength

    # 거래대금 스코어 (로그 스케일, 30억 기준)
    tv_baseline = 3_000_000_000  # 30억
    if tv > 0:
        tv_score = min(1.0, math.log10(tv / tv_baseline + 1) / math.log10(34))
        # log10(34+1)/log10(34) ≈ 1.0 at tv=100배 기준
        tv_score = max(0.0, min(1.0, tv_score))
    else:
        tv_score = 0.0

    # 가중 합산
    score = (
        price_score    * 0.50 +
        strength_score * 0.30 +
        tv_score       * 0.20
    )

    return round(score, 3)


def score_volume_rank(ticker: str, volume_data: Optional[dict]) -> float:
    """
    거래대금 순위 스코어 [0.0 ~ 1.0]
    거래대금 상위 50위 기준
    """
    if not volume_data:
        return 0.3

    top_tickers = volume_data.get("top_tickers", set())
    kospi_top   = [t[0] for t in volume_data.get("kospi_top", [])]
    kosdaq_top  = [t[0] for t in volume_data.get("kosdaq_top", [])]

    if ticker not in top_tickers:
        return 0.2

    # 순위 찾기
    rank = None
    combined = kospi_top + kosdaq_top
    if ticker in combined:
        rank = combined.index(ticker) + 1

    if rank is None:
        return 0.5

    # 1위: 1.0, 50위: 0.5
    score = 1.0 - (rank - 1) / 100
    return round(max(0.3, min(1.0, score)), 3)
