"""
NXT (넥스트레이드) 거래 가능 종목 필터

넥스트레이드는 KOSPI200 + KOSDAQ150 편입 종목 + 일부 추가 지정종목으로 구성.
공개 API가 없으므로 아래 우선순위로 판별:
  1. 네이버 금융 NXT 거래량 데이터 (장중)
  2. 시가총액 + 거래대금 기준 근사 (KOSPI 상위 200 + KOSDAQ 상위 150)
"""
from typing import Optional
import requests
from bs4 import BeautifulSoup
import FinanceDataReader as fdr
from utils.cache import Cache
from utils.logger import get_logger

logger = get_logger("NXTFilter")

# NXT 거래 가능 종목 수 기준 (근사)
NXT_KOSPI_TOP_N  = 200
NXT_KOSDAQ_TOP_N = 150

_nxt_ticker_cache: Optional[set] = None


def get_nxt_eligible_tickers(cache: Optional[Cache] = None) -> set[str]:
    """
    NXT 거래 가능 종목 티커 집합 반환.
    시가총액 기준 KOSPI 상위 200 + KOSDAQ 상위 150.
    """
    global _nxt_ticker_cache

    cache_key = "nxt_eligible_tickers"
    if cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    if _nxt_ticker_cache is not None:
        return _nxt_ticker_cache

    tickers = set()

    # 1차: 네이버 금융 NXT 시세 페이지 시도
    nxt_from_naver = _fetch_nxt_from_naver()
    if nxt_from_naver:
        tickers = nxt_from_naver
        logger.info(f"NXT 종목 (네이버): {len(tickers)}개")
    else:
        # 2차: 시가총액 기준 근사
        tickers = _approx_nxt_by_marcap()
        logger.info(f"NXT 종목 (시총 근사): {len(tickers)}개")

    if cache:
        cache.set(cache_key, tickers)
    _nxt_ticker_cache = tickers
    return tickers


def _fetch_nxt_from_naver() -> Optional[set[str]]:
    """네이버 금융 NXT 거래상위 페이지에서 종목 수집"""
    tickers = set()
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://finance.naver.com/",
        }
        # NXT 거래상위 (KRX와 별도로 nxt_ 접두사)
        url = "https://finance.naver.com/sise/nxt_sise_quant.naver"
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.text, "lxml")
        table = soup.select_one("table.type_2")
        if not table:
            return None

        for row in table.select("tr"):
            link = row.select_one("a[href*='code=']")
            if link:
                code = link["href"].split("code=")[-1][:6]
                if code.isdigit() and len(code) == 6:
                    tickers.add(code)

        # 여러 페이지 수집 (최대 5페이지)
        for page in range(2, 6):
            r = requests.get(f"{url}?page={page}", headers=headers, timeout=8)
            if r.status_code != 200:
                break
            soup = BeautifulSoup(r.text, "lxml")
            table = soup.select_one("table.type_2")
            if not table:
                break
            new_codes = set()
            for row in table.select("tr"):
                link = row.select_one("a[href*='code=']")
                if link:
                    code = link["href"].split("code=")[-1][:6]
                    if code.isdigit() and len(code) == 6:
                        new_codes.add(code)
            if not new_codes:
                break
            tickers.update(new_codes)

        return tickers if len(tickers) >= 50 else None
    except Exception as e:
        logger.debug(f"NXT 네이버 조회 실패: {e}")
        return None


def _approx_nxt_by_marcap() -> set[str]:
    """시가총액 기준으로 NXT 지정종목 근사"""
    tickers = set()
    try:
        for market, top_n in [("KOSPI", NXT_KOSPI_TOP_N), ("KOSDAQ", NXT_KOSDAQ_TOP_N)]:
            df = fdr.StockListing(market)
            if df is None or df.empty:
                continue
            if "Marcap" not in df.columns:
                continue
            df_sorted = df.sort_values("Marcap", ascending=False).head(top_n)
            for _, row in df_sorted.iterrows():
                code = str(row.get("Code", "")).zfill(6)
                if code and len(code) == 6:
                    tickers.add(code)
    except Exception as e:
        logger.warning(f"시총 기준 NXT 근사 실패: {e}")
    return tickers


def filter_nxt_candidates(
    candidates: list[str],
    cache: Optional[Cache] = None,
) -> list[str]:
    """후보 종목에서 NXT 거래 가능 종목만 반환"""
    nxt_tickers = get_nxt_eligible_tickers(cache)
    filtered = [t for t in candidates if t in nxt_tickers]
    logger.info(f"NXT 필터: {len(candidates)}개 → {len(filtered)}개")
    return filtered
