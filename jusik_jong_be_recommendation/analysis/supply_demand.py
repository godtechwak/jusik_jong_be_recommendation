"""
외국인/기관 수급 스코어링
"""
import math
from typing import Optional


def score_supply_demand(
    ticker: str,
    stock_data: dict,
    market_cap: int = 0,
) -> float:
    """
    외국인+기관 순매수 스코어 [0.0 ~ 1.0]

    기준:
    - 외국인 순매수 + 기관 순매수 → 합산 순매수금액
    - 시가총액 대비 비율로 정규화
    - 두 주체 모두 매수: 보너스
    """
    info = stock_data.get(ticker, {})
    foreign_net = info.get("foreign_net", 0)
    inst_net    = info.get("inst_net", 0)
    cap         = market_cap or info.get("market_cap", 1)

    if cap <= 0:
        cap = 1

    # 각각의 시총 대비 순매수 비율 (%)
    foreign_ratio = foreign_net / cap * 100
    inst_ratio    = inst_net    / cap * 100

    # 두 주체 모두 매수
    both_buying = foreign_net > 0 and inst_net > 0
    both_selling = foreign_net < 0 and inst_net < 0

    # 합산 순매수금액 기반 시그모이드 스코어
    total_net = foreign_net + inst_net
    total_ratio = total_net / cap * 100

    # 시그모이드: 0% → 0.5, +0.1% → ~0.62, -0.1% → ~0.38
    sigmoid_score = 1 / (1 + math.exp(-total_ratio * 30))

    # 보정
    if both_buying:
        sigmoid_score = min(1.0, sigmoid_score * 1.15)
    elif both_selling:
        sigmoid_score = max(0.0, sigmoid_score * 0.85)

    # 외국인 단독 대량 순매수 보너스
    if foreign_net > 0 and foreign_ratio > 0.05:
        sigmoid_score = min(1.0, sigmoid_score + 0.05)

    return round(sigmoid_score, 3)


def get_supply_demand_summary(ticker: str, stock_data: dict) -> str:
    """수급 요약 텍스트"""
    info = stock_data.get(ticker, {})
    foreign_net = info.get("foreign_net", 0)
    inst_net    = info.get("inst_net", 0)

    parts = []
    if foreign_net > 0:
        parts.append(f"외국인 +{foreign_net/1e8:.0f}억")
    elif foreign_net < 0:
        parts.append(f"외국인 {foreign_net/1e8:.0f}억")

    if inst_net > 0:
        parts.append(f"기관 +{inst_net/1e8:.0f}억")
    elif inst_net < 0:
        parts.append(f"기관 {inst_net/1e8:.0f}억")

    return " | ".join(parts) if parts else "수급 중립"
