"""
목표가 / 손절가 계산기
"""
import config


def calculate_targets(rec: dict) -> tuple[int, int]:
    """
    목표가, 손절가 계산

    Returns: (target_price, stop_price) - 원 단위
    """
    close   = rec.get("close", 0)
    high    = rec.get("high", 0)
    low     = rec.get("low", 0)

    if close <= 0:
        return 0, 0

    # ── 목표가 ──────────────────────────────────
    # 방법 1: 당일 고가 돌파 기대 + 기본 비율
    if high > close:
        # 이미 고가권, 기본 비율 적용
        target = close * (1 + config.DEFAULT_TARGET_RATIO)
    else:
        # 당일 고가를 저항으로 설정하되, 최소 +1% 보장
        target = max(high * 1.005, close * 1.01)

    # 최소 목표: 현재가 +1.5%
    target = max(target, close * 1.015)
    # 최대 목표: 현재가 +5%
    target = min(target, close * 1.05)

    # 100원 단위 반올림
    target = _round_price(target)

    # ── 손절가 ──────────────────────────────────
    # 당일 저가 하방 1%를 손절로 설정
    if low > 0 and low < close:
        stop = low * 0.99
    else:
        stop = close * (1 - config.DEFAULT_STOP_RATIO)

    # 손절: 현재가 -3% 이상 내려가지 않도록 하한 설정
    stop = max(stop, close * 0.97)
    stop = _round_price(stop)

    # ── 손익비 검증 ──────────────────────────────
    gain = target - close
    loss = close - stop

    if loss > 0 and gain / loss < config.MIN_RR_RATIO:
        # 손익비 미달 시 목표가 조정
        target = int(close + loss * config.MIN_RR_RATIO)
        target = _round_price(target)

    return int(target), int(stop)


def calculate_rr_ratio(close: int, target: int, stop: int) -> float:
    """손익비 계산"""
    gain = target - close
    loss = close - stop
    if loss <= 0:
        return 0.0
    return round(gain / loss, 2)


def _round_price(price: float) -> int:
    """호가 단위에 맞게 반올림"""
    if price >= 500_000:
        unit = 1_000
    elif price >= 100_000:
        unit = 500
    elif price >= 50_000:
        unit = 100
    elif price >= 10_000:
        unit = 50
    elif price >= 5_000:
        unit = 10
    elif price >= 1_000:
        unit = 5
    else:
        unit = 1
    return int(round(price / unit) * unit)
