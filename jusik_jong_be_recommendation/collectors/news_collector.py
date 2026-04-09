"""
뉴스/재료 수집기 - 네이버 금융 스크래핑
감성 분석: Claude API (폴백: 키워드 매칭)
"""
import random
import time
from datetime import datetime
from typing import Optional
import requests
from bs4 import BeautifulSoup
import pytz
from collectors.base_collector import BaseCollector
from utils.cache import Cache
from analysis.news_scorer import analyze_sentiment_batch
import config

KST = pytz.timezone("Asia/Seoul")


class NewsCollector(BaseCollector):
    CACHE_KEY_MARKET = "news_market"
    CACHE_KEY_STOCK  = "news_stock_{ticker}"

    def __init__(self, cache: Cache):
        super().__init__(cache)
        self._session = requests.Session()
        self._session.headers.update(self._random_headers())

    def collect(self) -> Optional[dict]:
        """시장 전체 뉴스 수집"""
        cached = self._cache.get(self.CACHE_KEY_MARKET)
        if cached is not None:
            self._logger.info("시장 뉴스: 캐시 사용")
            return cached

        result = self._fetch_with_retry(self._fetch_market_news)
        if result is not None:
            self._cache.set(self.CACHE_KEY_MARKET, result)
        return result

    def collect_stock_news(self, ticker: str) -> list[dict]:
        """개별 종목 뉴스 수집"""
        cache_key = self.CACHE_KEY_STOCK.format(ticker=ticker)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        result = self._fetch_with_retry(self._fetch_stock_news, ticker) or []
        self._cache.set(cache_key, result)
        return result

    def _fetch_market_news(self) -> dict:
        raw_articles = []
        try:
            self._session.headers.update(self._random_headers())
            resp = self._session.get(
                config.NAVER_MARKET_NEWS_URL,
                timeout=config.HTTP_TIMEOUT
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            news_items = soup.select("ul.newsList li, div.mainNewsList li, .articleSubject")
            if not news_items:
                news_items = soup.select("li")

            for item in news_items[:30]:
                title_tag = item.select_one("a")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                if len(title) < 5:
                    continue
                raw_articles.append({
                    "title": title,
                    "url":   title_tag.get("href", ""),
                })

            time.sleep(config.HTTP_REQUEST_DELAY)
        except Exception as e:
            self._logger.warning(f"시장 뉴스 수집 실패: {e}")

        # 이슈 뉴스 추가
        raw_articles.extend(self._fetch_issue_news_raw())

        # Claude API 배치 감성 분석
        articles = self._apply_sentiment(raw_articles)

        self._logger.info(f"시장 뉴스 수집: {len(articles)}건")
        return {
            "articles":     articles,
            "positive":     sum(1 for a in articles if a["sentiment"] == "positive"),
            "negative":     sum(1 for a in articles if a["sentiment"] == "negative"),
            "collected_at": datetime.now(KST).isoformat(),
        }

    def _fetch_issue_news_raw(self) -> list[dict]:
        """네이버 금융 이슈 뉴스 (raw, 감성 분석 전)"""
        raw = []
        try:
            url = "https://finance.naver.com/news/news_list.naver?mode=LSS3D&section0=101&section1=258"
            self._session.headers.update(self._random_headers())
            resp = self._session.get(url, timeout=config.HTTP_TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            for item in soup.select(".articleSubject a, .articleCont a")[:20]:
                title = item.get_text(strip=True)
                if len(title) < 5:
                    continue
                raw.append({"title": title, "url": item.get("href", "")})
            time.sleep(config.HTTP_REQUEST_DELAY)
        except Exception as e:
            self._logger.debug(f"이슈 뉴스 수집 실패: {e}")
        return raw

    def _fetch_stock_news(self, ticker: str) -> list[dict]:
        """개별 종목 뉴스 (Claude API 감성 분석 포함)"""
        raw = []
        try:
            params = {"code": ticker, "page": 1}
            self._session.headers.update(self._random_headers())
            resp = self._session.get(
                config.NAVER_STOCK_NEWS_URL,
                params=params,
                timeout=config.HTTP_TIMEOUT
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            for item in soup.select(".title a, .articleSubject a")[:10]:
                title = item.get_text(strip=True)
                if len(title) < 5:
                    continue
                raw.append({"title": title, "url": item.get("href", "")})
            time.sleep(config.HTTP_REQUEST_DELAY * 0.5)
        except Exception as e:
            self._logger.debug(f"종목 {ticker} 뉴스 수집 실패: {e}")

        return self._apply_sentiment(raw)

    def _apply_sentiment(self, raw_articles: list[dict]) -> list[dict]:
        """raw 기사 목록에 Claude API 감성 분석 결과를 붙임"""
        if not raw_articles:
            return []

        titles = [a["title"] for a in raw_articles]
        sentiments = analyze_sentiment_batch(titles)

        articles = []
        for article, sentiment in zip(raw_articles, sentiments):
            articles.append({
                "title":     article["title"],
                "url":       article["url"],
                "sentiment": sentiment,
                "timestamp": datetime.now(KST).isoformat(),
            })
        return articles

    @staticmethod
    def _random_headers() -> dict:
        return {
            "User-Agent": random.choice(config.HTTP_USER_AGENTS),
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://finance.naver.com/",
        }
