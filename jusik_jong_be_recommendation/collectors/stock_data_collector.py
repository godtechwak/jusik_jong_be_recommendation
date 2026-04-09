"""
개별 종목 OHLCV + 외국인/기관 수급 수집기
- OHLCV: FinanceDataReader (StockListing)
- 수급: 네이버 금융 iframe 스크래핑
"""
import random
import time
from typing import Optional
import requests
from bs4 import BeautifulSoup
import FinanceDataReader as fdr
from collectors.base_collector import BaseCollector
from utils.cache import Cache
import config


SUPPLY_DEMAND_URLS = {
    "foreign_buy_kospi":  "https://finance.naver.com/sise/sise_deal_rank_iframe.naver?sosok=01&investor_gubun=9000&type=buy",
    "foreign_sell_kospi": "https://finance.naver.com/sise/sise_deal_rank_iframe.naver?sosok=01&investor_gubun=9000&type=sell",
    "inst_buy_kospi":     "https://finance.naver.com/sise/sise_deal_rank_iframe.naver?sosok=01&investor_gubun=1000&type=buy",
    "inst_sell_kospi":    "https://finance.naver.com/sise/sise_deal_rank_iframe.naver?sosok=01&investor_gubun=1000&type=sell",
    "foreign_buy_kosdaq": "https://finance.naver.com/sise/sise_deal_rank_iframe.naver?sosok=02&investor_gubun=9000&type=buy",
    "foreign_sell_kosdaq":"https://finance.naver.com/sise/sise_deal_rank_iframe.naver?sosok=02&investor_gubun=9000&type=sell",
    "inst_buy_kosdaq":    "https://finance.naver.com/sise/sise_deal_rank_iframe.naver?sosok=02&investor_gubun=1000&type=buy",
    "inst_sell_kosdaq":   "https://finance.naver.com/sise/sise_deal_rank_iframe.naver?sosok=02&investor_gubun=1000&type=sell",
}


class StockDataCollector(BaseCollector):
    CACHE_KEY_KOSPI  = "fdr_kospi_listing"
    CACHE_KEY_KOSDAQ = "fdr_kosdaq_listing"
    CACHE_KEY_SUPPLY = "supply_demand"

    def __init__(self, cache: Cache):
        super().__init__(cache)
        self._session = requests.Session()

    def collect(self) -> Optional[dict]:
        """KOSPI + KOSDAQ 전종목 데이터 수집"""
        result = {"kospi": {}, "kosdaq": {}, "combined": {}}

        kospi  = self._collect_listing("KOSPI")
        kosdaq = self._collect_listing("KOSDAQ")

        if kospi:
            result["kospi"] = kospi
            result["combined"].update(kospi)
        if kosdaq:
            result["kosdaq"] = kosdaq
            result["combined"].update(kosdaq)

        if not result["combined"]:
            return None

        # 수급 데이터 합치기
        supply = self._collect_supply_demand()
        if supply:
            for ticker, info in result["combined"].items():
                info["foreign_net"] = supply.get("foreign_net", {}).get(ticker, 0)
                info["inst_net"]    = supply.get("inst_net", {}).get(ticker, 0)

        self._logger.info(f"종목 데이터 수집 완료: {len(result['combined'])}개")
        return result

    def _collect_listing(self, market: str) -> Optional[dict]:
        cache_key = self.CACHE_KEY_KOSPI if market == "KOSPI" else self.CACHE_KEY_KOSDAQ
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._logger.info(f"{market} 종목 데이터: 캐시 사용")
            return cached

        result = self._fetch_with_retry(self._fetch_listing, market)
        if result:
            self._cache.set(cache_key, result)
        return result

    def _fetch_listing(self, market: str) -> Optional[dict]:
        try:
            df = fdr.StockListing(market)
            if df is None or df.empty:
                return None

            result = {}
            for _, row in df.iterrows():
                ticker = str(row.get("Code", "")).strip().zfill(6)
                if not ticker or len(ticker) != 6:
                    continue

                close  = self._to_int(row.get("Close", 0))
                open_  = self._to_int(row.get("Open", 0))
                high   = self._to_int(row.get("High", 0))
                low    = self._to_int(row.get("Low", 0))
                volume = self._to_int(row.get("Volume", 0))
                amount = self._to_int(row.get("Amount", 0))
                marcap = self._to_int(row.get("Marcap", 0))

                result[ticker] = {
                    "ticker":        ticker,
                    "name":          str(row.get("Name", "")),
                    "market":        market,
                    "close":         close,
                    "open":          open_ if open_ > 0 else close,
                    "high":          high  if high  > 0 else close,
                    "low":           low   if low   > 0 else close,
                    "volume":        volume,
                    "trading_value": amount,
                    "market_cap":    marcap,
                    "foreign_net":   0,
                    "inst_net":      0,
                }

            self._logger.info(f"{market} 종목 {len(result)}개 로드")
            return result
        except Exception as e:
            self._logger.warning(f"{market} StockListing 조회 실패: {e}")
            return None

    def _collect_supply_demand(self) -> Optional[dict]:
        cached = self._cache.get(self.CACHE_KEY_SUPPLY)
        if cached is not None:
            return cached

        result = self._fetch_with_retry(self._fetch_supply_demand)
        if result:
            self._cache.set(self.CACHE_KEY_SUPPLY, result)
        return result

    def _fetch_supply_demand(self) -> dict:
        """네이버 금융 외국인/기관 순매수 상위 스크래핑"""
        foreign_buy:  dict[str, int] = {}
        foreign_sell: dict[str, int] = {}
        inst_buy:     dict[str, int] = {}
        inst_sell:    dict[str, int] = {}

        for key, url in SUPPLY_DEMAND_URLS.items():
            try:
                headers = {
                    "User-Agent": random.choice(config.HTTP_USER_AGENTS),
                    "Referer": "https://finance.naver.com/sise/sise_deal_rank.naver",
                }
                r = self._session.get(url, headers=headers, timeout=config.HTTP_TIMEOUT)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "lxml")
                table = soup.select_one("table")
                if not table:
                    continue

                for row in table.select("tr"):
                    cells = row.select("td")
                    if len(cells) < 3:
                        continue
                    # 종목 코드 추출 (href에서)
                    link = cells[0].select_one("a[href*='code=']")
                    if not link:
                        continue
                    code = link["href"].split("code=")[-1][:6]
                    if not code.isdigit():
                        continue

                    # 금액 (만원 단위) → 원 단위 변환
                    amount_str = cells[2].get_text(strip=True).replace(",", "")
                    try:
                        amount = int(amount_str) * 10_000  # 만원 → 원
                    except ValueError:
                        continue

                    if "foreign_buy" in key:
                        foreign_buy[code] = amount
                    elif "foreign_sell" in key:
                        foreign_sell[code] = amount
                    elif "inst_buy" in key:
                        inst_buy[code] = amount
                    elif "inst_sell" in key:
                        inst_sell[code] = amount

                time.sleep(0.5)
            except Exception as e:
                self._logger.debug(f"수급 조회 실패 ({key}): {e}")

        # 순매수 = 매수 - 매도
        foreign_net: dict[str, int] = {}
        inst_net:    dict[str, int] = {}

        all_tickers = set(foreign_buy) | set(foreign_sell)
        for t in all_tickers:
            foreign_net[t] = foreign_buy.get(t, 0) - foreign_sell.get(t, 0)

        all_tickers = set(inst_buy) | set(inst_sell)
        for t in all_tickers:
            inst_net[t] = inst_buy.get(t, 0) - inst_sell.get(t, 0)

        self._logger.info(
            f"수급 데이터: 외국인 {len(foreign_net)}개, 기관 {len(inst_net)}개"
        )
        return {"foreign_net": foreign_net, "inst_net": inst_net}

    @staticmethod
    def _to_int(val) -> int:
        try:
            return int(float(str(val).replace(",", "")))
        except (ValueError, TypeError):
            return 0
