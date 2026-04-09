"""
최종 추천 종목 선정
"""
from typing import Optional
from recommendation.target_calculator import calculate_targets, calculate_rr_ratio
from utils.logger import get_logger
import config

logger = get_logger("Recommender")


def apply_theme_diversity(
    scored: list[dict],
    max_per_theme: int = config.MAX_PER_THEME,
) -> list[dict]:
    """
    동일 테마 종목 집중도 제한
    같은 테마는 최대 max_per_theme 개까지만 허용
    """
    theme_counts: dict[str, int] = {}
    result = []

    for rec in scored:
        theme = rec.get("theme", "일반")
        count = theme_counts.get(theme, 0)

        if theme in ("N/A", "일반", "일반주"):
            # 테마 미분류는 별도 제한 없음
            result.append(rec)
            continue

        if count < max_per_theme:
            result.append(rec)
            theme_counts[theme] = count + 1

    return result


def build_recommendation_reason(rec: dict) -> str:
    """추천 근거 문자열 생성"""
    parts = []

    scores = rec.get("scores", {})

    # 수급 근거
    supply = rec.get("supply_summary", "")
    if supply:
        parts.append(supply)

    # 테마 근거
    theme = rec.get("theme", "")
    if theme and theme not in ("N/A", "일반"):
        theme_score = scores.get("theme_alignment", 0)
        if theme_score >= 0.6:
            parts.append(f"{theme} 테마 강세")

    # 뉴스 근거
    news = rec.get("news_headline", "")
    if news:
        parts.append(news)

    # 모멘텀 근거
    close   = rec.get("close", 0)
    open_p  = rec.get("open", 0)
    if close > 0 and open_p > 0:
        chg = (close - open_p) / open_p * 100
        if chg >= 1.0:
            parts.append(f"당일 +{chg:.1f}% 강세")
        elif chg <= -1.0:
            parts.append(f"당일 {chg:.1f}% (저가 매수 관점)")

    # 거래대금 근거
    tv = rec.get("trading_value", 0)
    if tv >= 100_000_000_000:  # 1000억 이상
        parts.append(f"거래대금 {tv/1e8:.0f}억 (대형 거래)")
    elif tv >= 30_000_000_000:  # 300억 이상
        parts.append(f"거래대금 {tv/1e8:.0f}억")

    if not parts:
        parts.append("복합 기술적 신호")

    return " | ".join(parts)


def generate_recommendations(
    scored_candidates: list[dict],
    market_data: Optional[dict],
    n: int = config.MAX_RECOMMENDATIONS,
) -> list[dict]:
    """
    최종 추천 종목 생성

    Args:
        scored_candidates: 스코어링된 후보 목록 (내림차순)
        market_data: 시장 지수 데이터
        n: 추천 개수

    Returns:
        최종 추천 목록
    """
    if not scored_candidates:
        logger.warning("추천할 후보 종목이 없습니다")
        return []

    # 시장 킬스위치 확인
    market_bias = (market_data or {}).get("market_bias", "neutral")
    avg_score = sum(r["score"] for r in scored_candidates[:10]) / min(10, len(scored_candidates))

    if market_bias == "crash":
        logger.warning("시장 급락으로 추천을 중단합니다")
        return []

    if market_bias == "bearish" and avg_score < 0.45:
        logger.warning("약세장 + 낮은 평균 스코어로 추천 보류")
        return []

    # 테마 다양성 필터
    diversity_filtered = apply_theme_diversity(scored_candidates)

    # 상위 N개 선택
    top_n = diversity_filtered[:n]

    # 목표가/손절가 계산 + 추천 근거 생성
    final_recs = []
    for rec in top_n:
        target, stop = calculate_targets(rec)
        close = rec.get("close", 0)

        if close <= 0 or target <= 0 or stop <= 0:
            continue

        rr_ratio = calculate_rr_ratio(close, target, stop)

        # 손익비 미달 종목 제외
        if rr_ratio < config.MIN_RR_RATIO:
            logger.debug(f"{rec['ticker']} 손익비 미달: {rr_ratio}")
            continue

        rec["target_price"] = target
        rec["stop_price"]   = stop
        rec["rr_ratio"]     = rr_ratio
        rec["reason"]       = build_recommendation_reason(rec)

        final_recs.append(rec)

        if len(final_recs) >= n:
            break

    logger.info(f"최종 추천: {len(final_recs)}종목")
    return final_recs
