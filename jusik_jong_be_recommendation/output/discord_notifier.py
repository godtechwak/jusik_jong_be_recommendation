"""
Discord 웹훅 알림 모듈
"""
import os
import json
import requests
from datetime import datetime
from typing import Optional
import pytz
from dotenv import load_dotenv
from utils.logger import get_logger

load_dotenv()
logger = get_logger("DiscordNotifier")
KST = pytz.timezone("Asia/Seoul")

SESSION_LABELS = {
    "krx": "📈 정규거래소 (KRX) 종가 베팅",
    "nxt": "🌙 넥스트레이드 (NXT) 종가 베팅",
}

SESSION_COLORS = {
    "krx": 0x2ECC71,   # 초록
    "nxt": 0x9B59B6,   # 보라
}

MARKET_BIAS_EMOJI = {
    "bullish": "🟢",
    "neutral": "🟡",
    "bearish": "🔴",
    "crash":   "💥",
}

US_SENTIMENT_EMOJI = {
    "risk_on":      "🚀",
    "neutral":      "😐",
    "risk_off":     "⚠️",
    "fear":         "😨",
    "extreme_fear": "🆘",
}


def send_recommendations(
    recs: list[dict],
    market_data: Optional[dict],
    futures_data: Optional[dict],
    session: str = "krx",
    webhook_url: Optional[str] = None,
) -> bool:
    """
    추천 종목을 Discord 웹훅으로 전송.
    Returns: 성공 여부
    """
    url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
    if not url:
        logger.warning("DISCORD_WEBHOOK_URL이 설정되지 않아 Discord 전송 생략")
        return False

    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    embeds = []

    # ── 헤더 embed ─────────────────────────────────
    embeds.append(_build_header_embed(market_data, futures_data, session, now))

    # ── 추천 없을 때 ──────────────────────────────
    if not recs:
        embeds.append({
            "description": "⛔ **추천 종목 없음**\n현재 시장 상황이 종가 베팅에 적합하지 않습니다.",
            "color": 0xE74C3C,
        })
    else:
        # ── 종목별 embed ────────────────────────────
        for i, rec in enumerate(recs, 1):
            embeds.append(_build_stock_embed(rec, i, session))

    payload = {
        "username": "종베봇 🤖",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/2830/2830284.png",
        "embeds": embeds[:10],  # Discord 최대 10개
    }

    try:
        resp = requests.post(
            url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code in (200, 204):
            logger.info(f"Discord 전송 성공 ({session})")
            return True
        else:
            logger.error(f"Discord 전송 실패: {resp.status_code} {resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"Discord 전송 오류: {e}")
        return False


def _build_header_embed(
    market_data: Optional[dict],
    futures_data: Optional[dict],
    session: str,
    now: str,
) -> dict:
    kospi_val  = (market_data or {}).get("kospi", {}).get("current", 0)
    kospi_chg  = (market_data or {}).get("kospi", {}).get("change_pct", 0)
    kosdaq_val = (market_data or {}).get("kosdaq", {}).get("current", 0)
    kosdaq_chg = (market_data or {}).get("kosdaq", {}).get("change_pct", 0)
    bias       = (market_data or {}).get("market_bias", "neutral")

    sp500  = (futures_data or {}).get("sp500_pct",  0)
    nasdaq = (futures_data or {}).get("nasdaq_pct", 0)
    vix    = (futures_data or {}).get("vix", 0)
    us_s   = (futures_data or {}).get("sentiment", "neutral")

    bias_emoji = MARKET_BIAS_EMOJI.get(bias, "🟡")
    us_emoji   = US_SENTIMENT_EMOJI.get(us_s, "😐")

    kospi_arrow  = "▲" if kospi_chg  >= 0 else "▼"
    kosdaq_arrow = "▲" if kosdaq_chg >= 0 else "▼"
    sp500_arrow  = "▲" if sp500  >= 0 else "▼"
    nas_arrow    = "▲" if nasdaq >= 0 else "▼"

    fields = [
        {
            "name": f"{bias_emoji} KOSPI",
            "value": f"`{kospi_val:,.2f}` {kospi_arrow} `{kospi_chg:+.2f}%`",
            "inline": True,
        },
        {
            "name": f"{bias_emoji} KOSDAQ",
            "value": f"`{kosdaq_val:,.2f}` {kosdaq_arrow} `{kosdaq_chg:+.2f}%`",
            "inline": True,
        },
        {"name": "\u200b", "value": "\u200b", "inline": True},
        {
            "name": f"{us_emoji} S&P500 선물",
            "value": f"{sp500_arrow} `{sp500:+.2f}%`",
            "inline": True,
        },
        {
            "name": f"{us_emoji} NASDAQ 선물",
            "value": f"{nas_arrow} `{nasdaq:+.2f}%`",
            "inline": True,
        },
        {
            "name": "😰 VIX",
            "value": f"`{vix:.1f}`",
            "inline": True,
        },
    ]

    return {
        "title": SESSION_LABELS.get(session, "종가 베팅 추천"),
        "description": f"⏱ {now}",
        "color": SESSION_COLORS.get(session, 0x2ECC71),
        "fields": fields,
    }


def _build_stock_embed(rec: dict, rank: int, session: str) -> dict:
    ticker = rec.get("ticker", "")
    name   = rec.get("name", ticker)
    score  = rec.get("score", 0)
    theme  = rec.get("theme", "")
    close  = rec.get("close", 0)
    target = rec.get("target_price", 0)
    stop   = rec.get("stop_price", 0)
    rr     = rec.get("rr_ratio", 0)
    reason = rec.get("reason", "")

    target_pct = (target - close) / close * 100 if close > 0 else 0
    stop_pct   = (stop   - close) / close * 100 if close > 0 else 0

    # 점수에 따른 색상
    if score >= 0.75:
        color = 0x1ABC9C   # 청록
    elif score >= 0.60:
        color = 0x2ECC71   # 초록
    elif score >= 0.50:
        color = 0xF39C12   # 주황
    else:
        color = 0xE74C3C   # 빨강

    rank_emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][rank - 1] if rank <= 5 else f"{rank}."

    fields = [
        {
            "name": "🏷 테마",
            "value": f"`{theme}`" if theme else "`-`",
            "inline": True,
        },
        {
            "name": "📊 종합점수",
            "value": f"`{score:.3f}`",
            "inline": True,
        },
        {
            "name": "💹 현재가",
            "value": f"`{close:,}원`",
            "inline": True,
        },
        {
            "name": "🎯 목표가",
            "value": f"`{target:,}원` `({target_pct:+.1f}%)`",
            "inline": True,
        },
        {
            "name": "🛑 손절가",
            "value": f"`{stop:,}원` `({stop_pct:+.1f}%)`",
            "inline": True,
        },
        {
            "name": "⚖️ 손익비",
            "value": f"`1 : {rr:.1f}`",
            "inline": True,
        },
        {
            "name": "📝 추천 근거",
            "value": reason[:200] if reason else "-",
            "inline": False,
        },
    ]

    naver_url = f"https://finance.naver.com/item/main.naver?code={ticker}"

    return {
        "title": f"{rank_emoji} [{ticker}] {name}",
        "url": naver_url,
        "color": color,
        "fields": fields,
    }
