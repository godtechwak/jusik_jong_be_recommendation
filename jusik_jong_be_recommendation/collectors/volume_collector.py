"""
거래대금 상위 종목 수집기
- FinanceDataReader StockListing 결과 활용
"""
from typing import Optional
from collectors.base_collector import BaseCollector
from utils.cache import Cache
import config


class VolumeCollector(BaseCollector):
    CACHE_KEY = "volume_top"
    TOP_N = 50

    def __init__(self, cache: Cache):
        super().__init__(cache)

    def collect(self) -> Optional[dict]:
        cached = self._cache.get(self.CACHE_KEY)
        if cached is not None:
            self._logger.info("거래대금 상위: 캐시 사용")
            return cached

        result = self._fetch_with_retry(self._fetch)
        if result:
            self._cache.set(self.CACHE_KEY, result)
        return result

    def _fetch(self) -> dict:
        import FinanceDataReader as fdr

        result = {"kospi_top": [], "kosdaq_top": [], "top_tickers": set()}

        for market in ["KOSPI", "KOSDAQ"]:
            market_key = market.lower()
            try:
                df = fdr.StockListing(market)
                if df is None or df.empty:
                    continue

                # 거래대금 기준 정렬 (Amount 컬럼)
                if "Amount" not in df.columns:
                    continue

                df = df[df["Amount"] >= config.MIN_DAILY_VOLUME_KRW].copy()
                df_sorted = df.sort_values("Amount", ascending=False).head(self.TOP_N)

                top_list = []
                for _, row in df_sorted.iterrows():
                    ticker = str(row.get("Code", "")).zfill(6)
                    amount = int(float(str(row.get("Amount", 0)).replace(",", "")))
                    if ticker and len(ticker) == 6:
                        top_list.append((ticker, amount))
                        result["top_tickers"].add(ticker)

                result[f"{market_key}_top"] = top_list
            except Exception as e:
                self._logger.warning(f"{market} 거래대금 조회 실패: {e}")

        self._logger.info(
            f"거래대금 상위: KOSPI {len(result['kospi_top'])}개, "
            f"KOSDAQ {len(result['kosdaq_top'])}개"
        )
        return result
