"""
복합 스코어 계산기
각 차원의 스코어를 가중 합산하여 최종 점수 생성
"""
from typing import Optional
from analysis.market_sentiment import score_market_sentiment, score_us_futures
from analysis.supply_demand import score_supply_demand, get_supply_demand_summary
from analysis.momentum import score_momentum, score_volume_rank
from analysis.news_scorer import score_news, get_news_summary
from analysis.theme_scorer import score_theme
import config


def compute_composite_score(
    ticker: str,
    stock_data: dict,
    market_data: Optional[dict],
    futures_data: Optional[dict],
    volume_data: Optional[dict],
    theme_data: Optional[dict],
    stock_news: list[dict],
    market_news: Optional[dict],
) -> dict:
    """
    단일 종목 복합 스코어 계산

    Returns:
        {
            "ticker": str,
            "score": float,           # 최종 점수 [0~1]
            "scores": dict,           # 차원별 점수
            "theme": str,             # 속한 테마
            "supply_summary": str,    # 수급 요약
            "news_headline": str,     # 뉴스 헤드라인
        }
    """
    weights = config.WEIGHTS.copy()
    scores  = {}

    # 1. 시황 스코어
    scores["market_sentiment"] = score_market_sentiment(market_data)

    # 2. 미국 선물 스코어
    scores["us_futures"] = score_us_futures(futures_data)

    # 3. 외국인/기관 수급 스코어
    market_cap = stock_data.get(ticker, {}).get("market_cap", 0)
    scores["supply_demand"] = score_supply_demand(ticker, stock_data, market_cap)

    # 4. 모멘텀 스코어
    scores["momentum"] = score_momentum(ticker, stock_data)

    # 5. 뉴스 스코어
    scores["news_catalyst"] = score_news(ticker, stock_news, market_news)

    # 6. 테마 스코어
    theme_score, theme_name = score_theme(ticker, theme_data)
    scores["theme_alignment"] = theme_score

    # 7. 거래대금 순위 스코어
    scores["volume_rank"] = score_volume_rank(ticker, volume_data)

    # 가중 합산 (누락된 차원은 가중치 재분배)
    total_weight = 0.0
    weighted_sum = 0.0

    for dim, w in weights.items():
        s = scores.get(dim)
        if s is not None:
            weighted_sum += w * s
            total_weight += w

    if total_weight > 0:
        final_score = weighted_sum / total_weight
    else:
        final_score = 0.5

    # 추천 근거 요약
    supply_summary = get_supply_demand_summary(ticker, stock_data)
    news_headline  = get_news_summary(ticker, stock_news)

    return {
        "ticker":          ticker,
        "score":           round(final_score, 4),
        "scores":          scores,
        "theme":           theme_name,
        "supply_summary":  supply_summary,
        "news_headline":   news_headline,
    }


def score_all_candidates(
    candidates: list[str],
    stock_data: dict,
    market_data: Optional[dict],
    futures_data: Optional[dict],
    volume_data: Optional[dict],
    theme_data: Optional[dict],
    news_collector,
    market_news: Optional[dict],
) -> list[dict]:
    """
    후보 종목 전체 스코어링

    Returns: 스코어 내림차순 정렬된 리스트
    """
    results = []

    for ticker in candidates:
        # 종목별 뉴스 수집 (상위 후보만, 개수 제한으로 속도 관리)
        stock_news = []
        if news_collector and len(results) < 30:  # 상위 30개만 뉴스 조회
            stock_news = news_collector.collect_stock_news(ticker)

        result = compute_composite_score(
            ticker=ticker,
            stock_data=stock_data,
            market_data=market_data,
            futures_data=futures_data,
            volume_data=volume_data,
            theme_data=theme_data,
            stock_news=stock_news,
            market_news=market_news,
        )

        # 종목 기본 정보 추가
        info = stock_data.get(ticker, {})
        result.update({
            "name":          info.get("name") or get_stock_name(ticker),
            "market":        info.get("market", ""),
            "close":         info.get("close", 0),
            "open":          info.get("open", 0),
            "high":          info.get("high", 0),
            "low":           info.get("low", 0),
            "trading_value": info.get("trading_value", 0),
            "foreign_net":   info.get("foreign_net", 0),
            "inst_net":      info.get("inst_net", 0),
            "market_cap":    info.get("market_cap", 0),
        })

        results.append(result)

    # 스코어 내림차순 정렬
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def get_stock_name(ticker: str) -> str:
    """종목명 조회 (캐시된 stock_data에서 우선 조회)"""
    return ticker  # 실제 이름은 stock_data에 포함되어 있음
