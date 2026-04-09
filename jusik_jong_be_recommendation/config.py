"""
중앙 설정 파일 - 모든 가중치, 임계값, 상수 정의
"""

# ─────────────────────────────────────────────
#  스코어링 가중치 (합계 = 1.0)
# ─────────────────────────────────────────────
WEIGHTS = {
    "market_sentiment": 0.15,   # 시황 (KOSPI/KOSDAQ 방향)
    "us_futures":       0.10,   # 미국 선물 지수
    "supply_demand":    0.25,   # 외국인/기관 순매수 (가장 중요)
    "momentum":         0.20,   # 가격/거래대금 모멘텀
    "news_catalyst":    0.15,   # 재료/뉴스
    "theme_alignment":  0.10,   # 테마
    "volume_rank":      0.05,   # 거래대금 순위
}

# ─────────────────────────────────────────────
#  종목 필터링 기준
# ─────────────────────────────────────────────
MIN_MARKET_CAP_KRW      = 50_000_000_000   # 최소 시가총액 500억
MIN_DAILY_VOLUME_KRW    = 3_000_000_000    # 최소 일 거래대금 30억
MIN_PRICE_KRW           = 500              # 최소 주가 500원 (동전주 제외)
EXCLUDE_ETF             = True
EXCLUDE_SPAC            = True
EXCLUDE_PREFERRED       = True             # 우선주 제외

# ─────────────────────────────────────────────
#  목표가/손절가 기본값
# ─────────────────────────────────────────────
DEFAULT_TARGET_RATIO    = 0.03             # 기본 목표 +3%
DEFAULT_STOP_RATIO      = 0.015            # 기본 손절 -1.5%
MIN_RR_RATIO            = 1.5             # 최소 손익비 1:1.5

# ─────────────────────────────────────────────
#  시장 운영 시간 (KST)
# ─────────────────────────────────────────────
MARKET_OPEN_HOUR        = 9
MARKET_OPEN_MINUTE      = 0
MARKET_CLOSE_HOUR       = 15
MARKET_CLOSE_MINUTE     = 30
OPTIMAL_RUN_HOUR_START  = 14              # 최적 실행 시간 14:30 ~ 15:10
OPTIMAL_RUN_MIN_START   = 30
OPTIMAL_RUN_HOUR_END    = 15
OPTIMAL_RUN_MIN_END     = 10

# ─────────────────────────────────────────────
#  데이터 캐시 설정
# ─────────────────────────────────────────────
CACHE_TTL_SECONDS       = 600             # 10분 캐시
PYKRX_DELAY_MINUTES     = 15             # pykrx 지연 시간 (분)

# ─────────────────────────────────────────────
#  미국 선물 티커
# ─────────────────────────────────────────────
US_FUTURES_TICKERS = {
    "sp500":  "ES=F",
    "nasdaq": "NQ=F",
    "dow":    "YM=F",
}
VIX_TICKER = "^VIX"

# ─────────────────────────────────────────────
#  KRX 지수 코드
# ─────────────────────────────────────────────
KOSPI_INDEX_CODE    = "1001"
KOSDAQ_INDEX_CODE   = "2001"

# ─────────────────────────────────────────────
#  시황 킬스위치 임계값
# ─────────────────────────────────────────────
MARKET_CRASH_THRESHOLD  = -2.0            # KOSPI -2% 이하면 추천 중단
MARKET_BEARISH_THRESHOLD = -0.5           # -0.5% 이하: 약세장

# ─────────────────────────────────────────────
#  뉴스 감성 분석 키워드
# ─────────────────────────────────────────────
POSITIVE_KEYWORDS = [
    "급등", "상승", "돌파", "신고가", "수주", "계약", "호실적", "흑자",
    "어닝서프라이즈", "흑자전환", "임상성공", "FDA", "특허", "수출증가",
    "영업이익", "매출증가", "대규모", "최대", "신제품", "인수", "합병",
    "투자유치", "IPO", "상장", "배당확대", "자사주", "소각", "호재",
    "모멘텀", "급상승", "강세", "매수", "시장점유율", "성장"
]
NEGATIVE_KEYWORDS = [
    "급락", "하락", "손실", "적자", "리콜", "소송", "조사", "감사의견",
    "횡령", "배임", "불성실공시", "거래정지", "상장폐지", "부도",
    "파산", "매도", "실망", "쇼크", "최저", "하한가", "경고", "제재",
    "집단소송", "검찰", "압수수색", "영업손실", "당기순손실"
]

# ─────────────────────────────────────────────
#  추천 결과 설정
# ─────────────────────────────────────────────
MAX_RECOMMENDATIONS     = 5              # 최대 추천 종목 수
MAX_PER_THEME           = 2             # 동일 테마 최대 종목 수

# ─────────────────────────────────────────────
#  네이버 금융 URL
# ─────────────────────────────────────────────
NAVER_FINANCE_BASE      = "https://finance.naver.com"
NAVER_MARKET_NEWS_URL   = "https://finance.naver.com/news/mainnews.naver"
NAVER_THEME_URL         = "https://finance.naver.com/sise/theme.naver"
NAVER_STOCK_NEWS_URL    = "https://finance.naver.com/item/news_news.naver"

# HTTP 요청 헤더 (User-Agent 로테이션)
HTTP_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
]
HTTP_TIMEOUT            = 10            # 초
HTTP_REQUEST_DELAY      = 2.0           # 요청 간 딜레이 (초)

# ─────────────────────────────────────────────
#  출력 설정
# ─────────────────────────────────────────────
OUTPUT_DIR              = "output/reports"
