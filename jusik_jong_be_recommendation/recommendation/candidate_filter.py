"""
후보 종목 필터링
거래 유니버스에서 투자 적합 종목만 추출
"""
from typing import Optional
from utils.logger import get_logger
import config

logger = get_logger("CandidateFilter")


# 우선주 / ETF 제외를 위한 패턴
PREFERRED_SUFFIXES = ("우", "우B", "우C", "1우", "2우", "3우")

# 알려진 ETF 코드 범위 (069500~, 102110~ 등 - 실제로는 종목명으로 판별)
ETF_NAME_KEYWORDS = ["ETF", "KODEX", "TIGER", "KBSTAR", "KOSEF", "ACE", "HANARO", "RISE", "SOL"]


def is_etf_or_preferred(ticker: str, name: str) -> bool:
    """ETF, 우선주 여부 확인"""
    if config.EXCLUDE_ETF:
        name_upper = name.upper()
        if any(kw in name_upper for kw in ETF_NAME_KEYWORDS):
            return True

    if config.EXCLUDE_PREFERRED:
        if any(name.endswith(suf) for suf in PREFERRED_SUFFIXES):
            return True

    return False


def apply_hard_filters(
    tickers: list[str],
    stock_data: dict,
) -> list[str]:
    """
    하드 필터 적용

    제외 조건:
    - 시가총액 < 500억
    - 거래대금 < 30억
    - 주가 < 500원
    - 종가 = 0 (데이터 없음)
    - 우선주, ETF
    """
    filtered = []
    excluded_reasons: dict[str, str] = {}

    for ticker in tickers:
        info = stock_data.get(ticker, {})

        close      = info.get("close", 0)
        tv         = info.get("trading_value", 0)
        market_cap = info.get("market_cap", 0)
        name       = info.get("name", "")

        # 기본 데이터 없음
        if close <= 0:
            excluded_reasons[ticker] = "데이터없음"
            continue

        # 주가 최소 기준
        if close < config.MIN_PRICE_KRW:
            excluded_reasons[ticker] = f"주가낮음({close}원)"
            continue

        # 거래대금 기준
        if tv < config.MIN_DAILY_VOLUME_KRW:
            excluded_reasons[ticker] = f"거래대금부족({tv/1e8:.0f}억)"
            continue

        # 시가총액 기준 (데이터 있을 때만)
        if market_cap > 0 and market_cap < config.MIN_MARKET_CAP_KRW:
            excluded_reasons[ticker] = f"시총부족({market_cap/1e8:.0f}억)"
            continue

        # ETF/우선주 체크 (stock_data에 포함된 종목명 사용)
        if is_etf_or_preferred(ticker, name):
            excluded_reasons[ticker] = f"ETF/우선주({name})"
            continue

        filtered.append(ticker)

    logger.info(
        f"하드 필터: {len(tickers)}개 → {len(filtered)}개 "
        f"(제외: {len(excluded_reasons)}개)"
    )
    return filtered


def build_candidate_pool(
    stock_data: dict,
    volume_data: Optional[dict],
    theme_data: Optional[dict],
    min_foreign_net: int = 500_000_000,    # 외국인 순매수 5억 이상
    min_inst_net: int = 500_000_000,       # 기관 순매수 5억 이상
) -> list[str]:
    """
    후보 풀 구성

    Source A: 거래대금 상위 50
    Source B: 상승 테마 구성 종목
    Source C: 외국인 또는 기관 대량 순매수 종목
    """
    candidate_set = set()

    # Source A: 거래대금 상위
    if volume_data:
        candidate_set.update(volume_data.get("top_tickers", set()))

    # Source B: 테마 종목
    if theme_data:
        candidate_set.update(theme_data.get("top_theme_tickers", set()))

    # Source C: 수급 상위
    for ticker, info in stock_data.items():
        foreign_net = info.get("foreign_net", 0)
        inst_net    = info.get("inst_net", 0)
        if foreign_net >= min_foreign_net or inst_net >= min_inst_net:
            candidate_set.add(ticker)

    logger.info(f"후보 풀 구성: {len(candidate_set)}개")
    return list(candidate_set)


def get_candidates(
    stock_data: dict,
    volume_data: Optional[dict],
    theme_data: Optional[dict],
) -> list[str]:
    """
    최종 후보 종목 리스트 반환
    (풀 구성 + 하드 필터 적용)
    """
    pool = build_candidate_pool(stock_data, volume_data, theme_data)
    candidates = apply_hard_filters(pool, stock_data)
    return candidates
