"""
뉴스/재료 스코어링
- 1차: Claude API 배치 분석 (정확도 우선)
- 폴백: 키워드 매칭 (API 실패 시)
"""
import os
import json
from typing import Optional
from dotenv import load_dotenv
from utils.logger import get_logger

load_dotenv()
logger = get_logger("NewsScorer")

# Claude API 클라이언트 (지연 초기화)
_client = None


def _get_client():
    global _client
    if _client is None:
        try:
            import anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                _client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            pass
    return _client


# ─────────────────────────────────────────────
#  Claude API 배치 감성 분석
# ─────────────────────────────────────────────

def analyze_sentiment_batch(titles: list[str]) -> list[str]:
    """
    기사 제목 목록을 Claude에게 한 번에 분석 요청.
    Returns: 각 제목에 대한 "positive" / "negative" / "neutral" 리스트
    """
    client = _get_client()
    if not client or not titles:
        return [_keyword_sentiment(t) for t in titles]

    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(titles))

    prompt = f"""당신은 한국 주식시장 뉴스 분석 전문가입니다.
아래 뉴스 제목들이 주가에 미치는 영향을 분석해주세요.

판단 기준:
- positive: 실적 개선, 수주/계약, 신제품, 규제 완화, 투자 유치, 외국인 매수, 신고가, 흑자전환 등 주가 상승 기대
- negative: 실적 악화, 소송/조사, 횡령/배임, 거래정지, 상장폐지, 공급망 이슈, 매도 리포트, 주가 하락 우려
- neutral: 단순 현황 보도, 인사/조직 변경, 중립적 분석, 영향 불분명

중요: 부정어("없다", "아니다", "부인")가 포함된 경우 맥락을 고려해 판단하세요.
예) "적자 아니다" → positive, "성장 둔화 우려 없어" → neutral

뉴스 제목 목록:
{numbered}

반드시 아래 JSON 형식으로만 응답하세요 (설명 없이):
{{"results": ["positive", "neutral", "negative", ...]}}

각 번호에 대응하는 판단을 순서대로 배열에 담아주세요."""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        # 마크다운 코드블록 제거
        if "```" in text:
            text = text.split("```")[-2] if text.count("```") >= 2 else text
            text = text.replace("json", "").strip()
        # JSON 파싱
        data = json.loads(text)
        results = data.get("results", [])

        # 길이 보정
        while len(results) < len(titles):
            results.append("neutral")

        valid = {"positive", "negative", "neutral"}
        return [r if r in valid else "neutral" for r in results[:len(titles)]]

    except Exception as e:
        logger.warning(f"Claude 감성 분석 실패, 키워드 방식으로 폴백: {e}")
        return [_keyword_sentiment(t) for t in titles]


# ─────────────────────────────────────────────
#  키워드 폴백
# ─────────────────────────────────────────────

POSITIVE_KW = [
    "급등", "상승", "돌파", "신고가", "수주", "계약", "호실적", "흑자",
    "어닝서프라이즈", "흑자전환", "임상성공", "FDA", "특허", "수출증가",
    "영업이익", "매출증가", "대규모", "최대", "신제품", "인수", "합병",
    "투자유치", "배당확대", "자사주", "소각", "강세", "매수", "성장",
]
NEGATIVE_KW = [
    "급락", "하락", "손실", "적자", "리콜", "소송", "조사", "감사의견",
    "횡령", "배임", "불성실공시", "거래정지", "상장폐지", "부도",
    "파산", "매도", "경고", "제재", "검찰", "압수수색", "영업손실",
]
NEGATION_KW = ["없다", "아니다", "부인", "반박", "해소", "우려아냐", "않다", "않아"]


def _keyword_sentiment(text: str) -> str:
    """부정어 처리 포함 키워드 기반 감성 분석"""
    has_negation = any(kw in text for kw in NEGATION_KW)

    pos_score = sum(1 for kw in POSITIVE_KW if kw in text)
    neg_score = sum(1 for kw in NEGATIVE_KW if kw in text)

    if has_negation:
        # 부정어 있으면 neg→positive, pos→neutral로 반전
        if neg_score > 0 and pos_score == 0:
            return "positive"
        return "neutral"

    if neg_score > 0:
        return "negative"
    if pos_score >= 1:
        return "positive"
    return "neutral"


# ─────────────────────────────────────────────
#  스코어링 메인 함수
# ─────────────────────────────────────────────

def score_news(
    ticker: str,
    stock_news: list[dict],
    market_news: Optional[dict],
) -> float:
    """
    뉴스 감성 스코어 [0.0 ~ 1.0]
    종목별 뉴스가 있으면 Claude API로 분석, 없으면 시장 뉴스 감성 활용
    """
    if stock_news:
        return _score_articles(stock_news)

    if market_news:
        positive = market_news.get("positive", 0)
        negative = market_news.get("negative", 0)
        total    = max(1, positive + negative)
        ratio    = (positive - negative) / total
        return round((ratio + 1) / 2 * 0.6 + 0.2, 3)

    return 0.5


def _score_articles(articles: list[dict]) -> float:
    if not articles:
        return 0.5

    pos = sum(1 for a in articles if a.get("sentiment") == "positive")
    neg = sum(1 for a in articles if a.get("sentiment") == "negative")
    total = max(1, len(articles))

    net_ratio = (pos - neg) / total

    if neg > 0:
        score = 0.5 + net_ratio * 0.3
    else:
        score = 0.5 + net_ratio * 0.5

    return round(max(0.0, min(1.0, score)), 3)


def get_news_summary(ticker: str, stock_news: list[dict]) -> str:
    """뉴스 요약 (추천 근거용)"""
    if not stock_news:
        return ""
    positive_titles = [a["title"] for a in stock_news if a.get("sentiment") == "positive"]
    if positive_titles:
        return positive_titles[0][:50]
    return ""
