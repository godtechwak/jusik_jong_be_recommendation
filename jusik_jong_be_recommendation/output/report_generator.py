"""
마크다운 리포트 저장
"""
import os
from datetime import datetime
from typing import Optional
import pytz
import config

KST = pytz.timezone("Asia/Seoul")


def save_report(
    recs: list[dict],
    market_data: Optional[dict],
    futures_data: Optional[dict],
) -> str:
    """추천 리포트를 마크다운 파일로 저장. 파일 경로 반환"""
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    now      = datetime.now(KST)
    filename = now.strftime("%Y%m%d_%H%M") + "_recommendation.md"
    filepath = os.path.join(config.OUTPUT_DIR, filename)

    content = _build_markdown(recs, market_data, futures_data, now)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filepath


def _build_markdown(
    recs: list[dict],
    market_data: Optional[dict],
    futures_data: Optional[dict],
    now: datetime,
) -> str:
    lines = []
    lines.append(f"# 종가 베팅 추천 리포트")
    lines.append(f"**생성일시**: {now.strftime('%Y-%m-%d %H:%M:%S KST')}")
    lines.append("")

    # 시황 섹션
    lines.append("## 시장 현황")

    kospi_val  = (market_data or {}).get("kospi", {}).get("current", 0)
    kospi_chg  = (market_data or {}).get("kospi", {}).get("change_pct", 0)
    kosdaq_val = (market_data or {}).get("kosdaq", {}).get("current", 0)
    kosdaq_chg = (market_data or {}).get("kosdaq", {}).get("change_pct", 0)
    bias       = (market_data or {}).get("market_bias", "N/A")

    sp500  = (futures_data or {}).get("sp500_pct",  0)
    nasdaq = (futures_data or {}).get("nasdaq_pct", 0)
    dow    = (futures_data or {}).get("dow_pct",    0)
    vix    = (futures_data or {}).get("vix",        0)
    us_s   = (futures_data or {}).get("sentiment",  "N/A")

    lines.append(f"| 지표 | 값 |")
    lines.append(f"|------|-----|")
    lines.append(f"| KOSPI  | {kospi_val:,.2f} ({kospi_chg:+.2f}%) |")
    lines.append(f"| KOSDAQ | {kosdaq_val:,.2f} ({kosdaq_chg:+.2f}%) |")
    lines.append(f"| 시장 방향 | {bias} |")
    lines.append(f"| S&P500 선물 | {sp500:+.2f}% |")
    lines.append(f"| NASDAQ 선물 | {nasdaq:+.2f}% |")
    lines.append(f"| DOW 선물 | {dow:+.2f}% |")
    lines.append(f"| VIX | {vix:.1f} |")
    lines.append(f"| 미국 선물 감성 | {us_s} |")
    lines.append("")

    # 추천 종목 섹션
    lines.append("## 추천 종목")
    lines.append("")

    if not recs:
        lines.append("> 시장 상황이 종가 베팅에 적합하지 않아 추천 종목이 없습니다.")
    else:
        lines.append("| 순위 | 코드 | 종목명 | 점수 | 테마 | 현재가 | 목표가 | 손절가 | 손익비 |")
        lines.append("|------|------|--------|------|------|--------|--------|--------|--------|")

        for i, rec in enumerate(recs, 1):
            close  = rec.get("close", 0)
            target = rec.get("target_price", 0)
            stop   = rec.get("stop_price", 0)
            rr     = rec.get("rr_ratio", 0)

            lines.append(
                f"| {i} | {rec.get('ticker','')} | {rec.get('name','')} "
                f"| {rec.get('score',0):.3f} | {rec.get('theme','')} "
                f"| {close:,} | {target:,} | {stop:,} | 1:{rr:.1f} |"
            )

        lines.append("")
        lines.append("### 추천 근거 상세")
        lines.append("")

        for i, rec in enumerate(recs, 1):
            lines.append(f"#### {i}. {rec.get('name','')} ({rec.get('ticker','')})")
            lines.append(f"- **추천 근거**: {rec.get('reason','')}")

            scores = rec.get("scores", {})
            score_parts = [f"{k}: {v:.3f}" for k, v in scores.items() if v is not None]
            lines.append(f"- **세부 점수**: {', '.join(score_parts)}")

            foreign = rec.get("foreign_net", 0)
            inst    = rec.get("inst_net", 0)
            tv      = rec.get("trading_value", 0)
            lines.append(f"- **수급**: 외국인 {foreign/1e8:+.0f}억, 기관 {inst/1e8:+.0f}억")
            lines.append(f"- **거래대금**: {tv/1e8:.0f}억원")
            lines.append("")

    lines.append("---")
    lines.append(f"*본 추천은 자동화된 알고리즘에 의해 생성되었으며, 투자 손실에 대한 책임을 지지 않습니다.*")

    return "\n".join(lines)
