"""
KOSPI / KOSDAQ 지수 수집기
- FinanceDataReader + 네이버 금융 스크래핑
"""
from typing import Optional
import random
import requests
from bs4 import BeautifulSoup
import FinanceDataReader as fdr
from collectors.base_collector import BaseCollector
from utils.cache import Cache
import config


class MarketIndexCollector(BaseCollector):
    CACHE_KEY = "market_index"

    def __init__(self, cache: Cache):
        super().__init__(cache)
        self._session = requests.Session()

    def collect(self) -> Optional[dict]:
        cached = self._cache.get(self.CACHE_KEY)
        if cached is not None:
            self._logger.info("시장 지수: 캐시 사용")
            return cached

        result = self._fetch_with_retry(self._fetch)
        if result:
            self._cache.set(self.CACHE_KEY, result)
        return result

    def _fetch(self) -> dict:
        result = {}

        # 네이버 금융 지수 스크래핑 (실시간성 우선)
        naver_data = self._fetch_from_naver()
        if naver_data:
            result.update(naver_data)
        else:
            # 백업: FinanceDataReader
            fdr_data = self._fetch_from_fdr()
            result.update(fdr_data)

        # 시장 방향 판단
        kospi_chg  = result.get("kospi", {}).get("change_pct", 0)
        kosdaq_chg = result.get("kosdaq", {}).get("change_pct", 0)

        if kospi_chg <= config.MARKET_CRASH_THRESHOLD:
            market_bias = "crash"
        elif kospi_chg <= config.MARKET_BEARISH_THRESHOLD and kosdaq_chg <= config.MARKET_BEARISH_THRESHOLD:
            market_bias = "bearish"
        elif kospi_chg >= 0.5 and kosdaq_chg >= 0.5:
            market_bias = "bullish"
        elif kospi_chg >= 0 or kosdaq_chg >= 0:
            market_bias = "neutral"
        else:
            market_bias = "bearish"

        result["market_bias"] = market_bias

        self._logger.info(
            f"시장 지수: KOSPI {kospi_chg:+.2f}% | KOSDAQ {kosdaq_chg:+.2f}% | {market_bias}"
        )
        return result

    def _fetch_from_naver(self) -> Optional[dict]:
        """네이버 금융 지수 일별 시세 페이지 (정확한 등락률 포함)"""
        result = {}
        index_map = [("KOSPI", "kospi"), ("KOSDAQ", "kosdaq")]

        for code, name in index_map:
            try:
                headers = {
                    "User-Agent": random.choice(config.HTTP_USER_AGENTS),
                    "Referer": "https://finance.naver.com/",
                }
                url = f"https://finance.naver.com/sise/sise_index_day.naver?code={code}"
                r = self._session.get(url, headers=headers, timeout=config.HTTP_TIMEOUT)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "lxml")

                table = soup.select_one("table.type_1")
                if not table:
                    continue

                rows = [row for row in table.select("tr") if row.select("td")]
                if not rows:
                    continue

                # 가장 최근 행
                latest_row = rows[0]
                cells = [c.get_text(strip=True) for c in latest_row.select("td")]
                # 컬럼: 날짜, 체결가, 전일비, 등락률, 거래량, 거래대금
                if len(cells) < 4:
                    continue

                close_str  = cells[1].replace(",", "")
                change_str = cells[3].replace("%", "").replace("+", "").strip()

                current    = float(close_str)
                change_pct = float(change_str)

                # 전전일 대비 5일 추세
                trend_5d = 0.0
                if len(rows) >= 6:
                    old_cells = [c.get_text(strip=True) for c in rows[5].select("td")]
                    if len(old_cells) >= 2:
                        old_close = float(old_cells[1].replace(",", ""))
                        if old_close > 0:
                            trend_5d = (current - old_close) / old_close * 100

                result[name] = {
                    "current":    round(current, 2),
                    "change_pct": round(change_pct, 2),
                    "trend_5d":   round(trend_5d, 2),
                    "open":       current,
                    "high":       current,
                    "low":        current,
                    "prev_close": round(current / (1 + change_pct / 100), 2) if change_pct != -100 else current,
                }
            except Exception as e:
                self._logger.debug(f"{code} 네이버 지수 조회 실패: {e}")

        return result if result else None

    def _fetch_from_fdr(self) -> dict:
        """FinanceDataReader 지수 데이터 (백업)"""
        from datetime import datetime, timedelta
        result = {}

        indices = {"kospi": "KS11", "kosdaq": "KQ11"}

        for name, code in indices.items():
            try:
                end   = datetime.now().strftime("%Y-%m-%d")
                start = (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d")
                df = fdr.DataReader(code, start, end)

                if df is None or df.empty or len(df) < 2:
                    result[name] = self._empty_index()
                    continue

                latest = df.iloc[-1]
                prev   = df.iloc[-2]

                close      = float(latest["Close"])
                prev_close = float(prev["Close"])
                change_pct = (close - prev_close) / prev_close * 100

                ref_5d = float(df.iloc[-6]["Close"]) if len(df) >= 6 else float(df.iloc[0]["Close"])
                trend_5d = (close - ref_5d) / ref_5d * 100

                result[name] = {
                    "current":    round(close, 2),
                    "prev_close": round(prev_close, 2),
                    "change_pct": round(change_pct, 2),
                    "trend_5d":   round(trend_5d, 2),
                    "open":       float(latest.get("Open", close)),
                    "high":       float(latest.get("High", close)),
                    "low":        float(latest.get("Low", close)),
                }
            except Exception as e:
                self._logger.warning(f"{name} FDR 지수 조회 실패: {e}")
                result[name] = self._empty_index()

        return result

    @staticmethod
    def _empty_index() -> dict:
        return {
            "current": 0.0,
            "prev_close": 0.0,
            "change_pct": 0.0,
            "trend_5d": 0.0,
            "open": 0.0,
            "high": 0.0,
            "low": 0.0,
        }
