"""
테마 스코어링
"""
from typing import Optional


def score_theme(ticker: str, theme_data: Optional[dict]) -> tuple[float, str]:
    """
    테마 정렬 스코어 [0.0 ~ 1.0] + 테마명 반환

    상승 테마에 속한 종목일수록 높은 점수
    """
    if not theme_data:
        return 0.3, "N/A"

    top_theme_tickers = theme_data.get("top_theme_tickers", set())
    ticker_to_themes  = theme_data.get("ticker_to_themes", {})
    hot_themes        = theme_data.get("hot_themes", [])

    if ticker not in top_theme_tickers:
        return 0.2, "일반"

    # 해당 종목이 속한 테마들
    my_themes = ticker_to_themes.get(ticker, [])

    if not my_themes:
        return 0.4, "테마주"

    # 가장 강한 테마 찾기
    best_theme_name   = my_themes[0]
    best_theme_change = 0.0

    for theme in hot_themes:
        if theme["name"] in my_themes:
            if theme["change_pct"] > best_theme_change:
                best_theme_change = theme["change_pct"]
                best_theme_name   = theme["name"]

    # 테마 등락률 기반 스코어
    if best_theme_change >= 3.0:
        score = 1.0
    elif best_theme_change >= 2.0:
        score = 0.9
    elif best_theme_change >= 1.0:
        score = 0.75
    elif best_theme_change >= 0.5:
        score = 0.60
    elif best_theme_change >= 0:
        score = 0.45
    else:
        score = 0.25

    return round(score, 3), best_theme_name
