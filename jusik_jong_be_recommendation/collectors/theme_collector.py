"""
테마/섹터 수집기 - 네이버 금융 테마 페이지
"""
import random
import time
from typing import Optional
import requests
from bs4 import BeautifulSoup
from collectors.base_collector import BaseCollector
from utils.cache import Cache
import config


class ThemeCollector(BaseCollector):
    CACHE_KEY = "themes"

    def __init__(self, cache: Cache):
        super().__init__(cache)
        self._session = requests.Session()

    def collect(self) -> Optional[dict]:
        cached = self._cache.get(self.CACHE_KEY)
        if cached is not None:
            self._logger.info("테마: 캐시 사용")
            return cached

        result = self._fetch_with_retry(self._fetch)
        if result:
            self._cache.set(self.CACHE_KEY, result)
        return result

    def _fetch(self) -> dict:
        hot_themes = []
        top_theme_tickers = set()
        ticker_to_themes: dict[str, list[str]] = {}

        try:
            headers = {
                "User-Agent": random.choice(config.HTTP_USER_AGENTS),
                "Referer": "https://finance.naver.com/",
            }
            resp = self._session.get(
                config.NAVER_THEME_URL,
                headers=headers,
                timeout=config.HTTP_TIMEOUT
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # 테마 테이블 파싱
            theme_rows = soup.select("table.type_1 tr, #contentarea table tr")
            if not theme_rows:
                theme_rows = soup.select("tr")

            for row in theme_rows:
                cells = row.select("td")
                if len(cells) < 2:
                    continue

                # 테마명 추출
                theme_link = row.select_one("a[href*='theme']")
                if not theme_link:
                    theme_link = cells[0].select_one("a")
                if not theme_link:
                    continue

                theme_name = theme_link.get_text(strip=True)
                if not theme_name:
                    continue

                # 테마 등락률 추출
                change_pct = 0.0
                for cell in cells[1:4]:
                    text = cell.get_text(strip=True).replace("%", "").replace(",", "")
                    try:
                        change_pct = float(text)
                        break
                    except ValueError:
                        continue

                # 테마 페이지에서 구성 종목 조회 (상위 테마만)
                theme_url = theme_link.get("href", "")
                tickers = []
                if change_pct > 0.5 and theme_url:  # 상승 테마만 종목 조회
                    tickers = self._fetch_theme_stocks(theme_url)
                    for t in tickers:
                        top_theme_tickers.add(t)
                        if t not in ticker_to_themes:
                            ticker_to_themes[t] = []
                        ticker_to_themes[t].append(theme_name)

                hot_themes.append({
                    "name":       theme_name,
                    "change_pct": change_pct,
                    "tickers":    tickers,
                })

            # 등락률 기준 정렬
            hot_themes.sort(key=lambda x: x["change_pct"], reverse=True)
            time.sleep(config.HTTP_REQUEST_DELAY)

        except Exception as e:
            self._logger.warning(f"테마 수집 실패: {e}")

        # 백업: KRX 업종 지수 기반 테마
        if not hot_themes:
            hot_themes = self._fetch_krx_sector_themes()
            for theme in hot_themes:
                for t in theme.get("tickers", []):
                    top_theme_tickers.add(t)

        self._logger.info(f"테마 수집: {len(hot_themes)}개, 테마 종목: {len(top_theme_tickers)}개")

        return {
            "hot_themes":        hot_themes[:20],  # 상위 20개
            "top_theme_tickers": top_theme_tickers,
            "ticker_to_themes":  ticker_to_themes,
        }

    def _fetch_theme_stocks(self, theme_url: str) -> list[str]:
        """테마 구성 종목 코드 추출"""
        tickers = []
        try:
            if not theme_url.startswith("http"):
                theme_url = config.NAVER_FINANCE_BASE + theme_url

            headers = {"User-Agent": random.choice(config.HTTP_USER_AGENTS)}
            resp = self._session.get(theme_url, headers=headers, timeout=config.HTTP_TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # 종목 코드 추출 (네이버 금융 종목 링크 패턴)
            for link in soup.select("a[href*='code=']")[:15]:
                href = link.get("href", "")
                if "code=" in href:
                    code = href.split("code=")[-1].split("&")[0].strip()
                    if code.isdigit() and len(code) == 6:
                        tickers.append(code)
            time.sleep(0.5)
        except Exception:
            pass
        return list(set(tickers))

    def _fetch_krx_sector_themes(self) -> list[dict]:
        """KRX 업종 지수 기반 테마 (백업)"""
        themes = []
        try:
            from pykrx import stock
            from utils.time_utils import today_str
            today = today_str()

            # 주요 업종 지수 코드
            sector_codes = {
                "반도체":   "1028",
                "2차전지":  "1150",
                "바이오":   "1003",
                "IT":       "1008",
                "자동차":   "1013",
                "화학":     "1010",
                "철강":     "1016",
                "금융":     "1032",
            }

            for name, code in sector_codes.items():
                try:
                    from datetime import datetime, timedelta
                    start = (datetime.strptime(today, "%Y%m%d") - timedelta(days=5)).strftime("%Y%m%d")
                    df = stock.get_index_ohlcv(start, today, code)
                    if df is not None and not df.empty and len(df) >= 2:
                        latest = float(df.iloc[-1]["종가"])
                        prev   = float(df.iloc[-2]["종가"])
                        pct    = (latest - prev) / prev * 100
                        themes.append({
                            "name":       name,
                            "change_pct": round(pct, 2),
                            "tickers":    [],
                        })
                except Exception:
                    continue

            themes.sort(key=lambda x: x["change_pct"], reverse=True)
        except Exception as e:
            self._logger.warning(f"KRX 업종 테마 수집 실패: {e}")
        return themes
