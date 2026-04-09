"""
미국 선물 지수 수집기 (yfinance)
S&P500 / NASDAQ / DOW / VIX
"""
from typing import Optional
import yfinance as yf
import pandas as pd
from collectors.base_collector import BaseCollector
from utils.cache import Cache
import config


class USFuturesCollector(BaseCollector):
    CACHE_KEY = "us_futures"

    def __init__(self, cache: Cache):
        super().__init__(cache)

    def collect(self) -> Optional[dict]:
        cached = self._cache.get(self.CACHE_KEY)
        if cached is not None:
            self._logger.info("미국 선물: 캐시 사용")
            return cached

        result = self._fetch_with_retry(self._fetch)
        if result:
            self._cache.set(self.CACHE_KEY, result)
        return result

    def _fetch(self) -> Optional[dict]:
        data = {}

        # VIX 조회
        try:
            vix_hist = yf.Ticker(config.VIX_TICKER).history(period="2d", interval="1h")
            vix = float(vix_hist["Close"].iloc[-1]) if not vix_hist.empty else 20.0
        except Exception:
            vix = 20.0

        changes = {}
        for name, ticker in config.US_FUTURES_TICKERS.items():
            try:
                hist = yf.Ticker(ticker).history(period="5d", interval="1h")
                if hist.empty:
                    changes[name] = 0.0
                    continue
                # 직전 종가 대비 현재 변화율
                prev_close = hist["Close"].iloc[-24] if len(hist) >= 24 else hist["Close"].iloc[0]
                current    = hist["Close"].iloc[-1]
                pct = (current - prev_close) / prev_close * 100
                changes[name] = round(pct, 2)
            except Exception as e:
                self._logger.warning(f"선물 {ticker} 조회 실패: {e}")
                changes[name] = 0.0

        avg_change = sum(changes.values()) / len(changes)

        # VIX에 따른 감성 판단
        if vix > 35:
            sentiment = "extreme_fear"
        elif vix > 25:
            sentiment = "fear"
        elif avg_change > 0.3:
            sentiment = "risk_on"
        elif avg_change < -0.3:
            sentiment = "risk_off"
        else:
            sentiment = "neutral"

        result = {
            "sp500_pct":    changes.get("sp500", 0.0),
            "nasdaq_pct":   changes.get("nasdaq", 0.0),
            "dow_pct":      changes.get("dow", 0.0),
            "vix":          round(vix, 2),
            "avg_change":   round(avg_change, 2),
            "sentiment":    sentiment,
        }

        self._logger.info(
            f"미국 선물: S&P {result['sp500_pct']:+.2f}% | "
            f"NASDAQ {result['nasdaq_pct']:+.2f}% | "
            f"VIX {result['vix']:.1f} | {sentiment}"
        )
        return result
