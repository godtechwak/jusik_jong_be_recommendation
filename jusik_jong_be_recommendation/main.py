"""
종가 베팅 추천 시스템 - 메인 오케스트레이터

실행 방법:
    python main.py                        # 일반 실행 (장중 시간 체크)
    python main.py --force                # 장 외 시간도 강제 실행
    python main.py --session nxt          # NXT 거래 종목만 추천 (기본: krx)
    python main.py --discord              # Discord 웹훅으로 결과 전송
    python main.py --debug                # 디버그 모드
    python main.py --top N                # 추천 종목 수 지정 (기본 5)
    python main.py --no-save              # 리포트 저장 생략
"""
import sys
import argparse
import concurrent.futures
from datetime import datetime
import pytz

from utils.cache import get_cache
from utils.logger import get_logger
from utils.time_utils import is_market_open, is_optimal_run_time, minutes_to_close

from collectors.us_futures_collector import USFuturesCollector
from collectors.market_index_collector import MarketIndexCollector
from collectors.stock_data_collector import StockDataCollector
from collectors.volume_collector import VolumeCollector
from collectors.news_collector import NewsCollector
from collectors.theme_collector import ThemeCollector
from collectors.nxt_filter import filter_nxt_candidates

from analysis.market_sentiment import is_market_killswitch
from analysis.composite_scorer import score_all_candidates

from recommendation.candidate_filter import get_candidates
from recommendation.recommender import generate_recommendations

from output.formatter import (
    print_header,
    print_recommendations,
    print_reasons,
    print_warning,
    print_info,
)
from output.report_generator import save_report
from output.discord_notifier import send_recommendations

import config

KST = pytz.timezone("Asia/Seoul")
logger = get_logger("Main")


def parse_args():
    parser = argparse.ArgumentParser(description="종가 베팅 추천 시스템")
    parser.add_argument("--force",   action="store_true", help="장 외 시간 강제 실행")
    parser.add_argument("--debug",   action="store_true", help="디버그 모드")
    parser.add_argument("--top",     type=int, default=config.MAX_RECOMMENDATIONS,
                        help=f"추천 종목 수 (기본: {config.MAX_RECOMMENDATIONS})")
    parser.add_argument("--no-save", action="store_true", help="리포트 저장 생략")
    parser.add_argument("--session", choices=["krx", "nxt"], default="krx",
                        help="거래 세션 (krx: 정규거래소 15:10, nxt: 넥스트레이드 19:40)")
    parser.add_argument("--discord", action="store_true", help="Discord 웹훅으로 결과 전송")
    return parser.parse_args()


def check_market_time(force: bool, session: str) -> bool:
    """시장 시간 확인"""
    if force:
        print_warning("강제 실행 모드 - 장 외 시간 실행")
        return True

    if session == "nxt":
        # NXT 세션: 16:00~20:00 장외거래, 19:40 실행 기준
        now_t = datetime.now(KST).time()
        from datetime import time as dtime
        if not (dtime(16, 0) <= now_t <= dtime(20, 10)):
            print_warning(
                f"NXT 세션 실행 권장 시간대(16:00~20:00)가 아닙니다. "
                f"--force 옵션으로 강제 실행 가능합니다."
            )
            return False
        return True

    # KRX 정규 세션
    if not is_market_open():
        now = datetime.now(KST).strftime("%H:%M")
        print_warning(
            f"현재 시각 {now} KST는 장중이 아닙니다. "
            f"장중 시간 (09:00~15:30)에 실행하거나 --force 옵션을 사용하세요."
        )
        return False

    remaining = minutes_to_close()
    if not is_optimal_run_time():
        print_warning(
            f"현재는 최적 실행 시간대(14:30~15:10)가 아닙니다. "
            f"마감까지 {remaining}분 남았습니다. 계속 진행합니다..."
        )
    else:
        print_info(f"최적 실행 시간대 - 마감까지 {remaining}분 남음")

    return True


def collect_macro_data(cache) -> tuple:
    """Phase 2: 매크로 데이터 병렬 수집"""
    logger.info("=== Phase 2: 매크로 데이터 수집 시작 ===")

    us_collector    = USFuturesCollector(cache)
    index_collector = MarketIndexCollector(cache)
    news_collector  = NewsCollector(cache)
    theme_collector = ThemeCollector(cache)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures_future = executor.submit(us_collector.collect)
        index_future   = executor.submit(index_collector.collect)
        news_future    = executor.submit(news_collector.collect)
        theme_future   = executor.submit(theme_collector.collect)

        futures_data = futures_future.result()
        market_data  = index_future.result()
        market_news  = news_future.result()
        theme_data   = theme_future.result()

    if futures_data is None:
        print_warning("미국 선물 데이터 수집 실패 - 해당 차원 스코어 제외")
    if market_data is None:
        print_warning("시장 지수 데이터 수집 실패")
    if market_news is None:
        print_warning("시장 뉴스 수집 실패 - 뉴스 차원 스코어 제외")
    if theme_data is None:
        print_warning("테마 데이터 수집 실패 - 테마 차원 스코어 제외")

    return futures_data, market_data, market_news, theme_data, news_collector


def collect_stock_data(cache) -> tuple:
    """Phase 3: 종목 데이터 수집"""
    logger.info("=== Phase 3: 종목 데이터 수집 시작 ===")

    stock_collector  = StockDataCollector(cache)
    volume_collector = VolumeCollector(cache)

    stock_result = stock_collector.collect()
    volume_data  = volume_collector.collect()

    if stock_result is None:
        logger.error("종목 데이터 수집 실패 - 프로그램을 종료합니다")
        return None, None

    stock_data = stock_result.get("combined", {})
    return stock_data, volume_data


def run(args) -> int:
    """메인 실행 로직. 반환값: 추천 종목 수"""
    cache   = get_cache()
    session = args.session

    print_info(
        f"종가 베팅 추천 시스템 시작 | 세션: {session.upper()} | "
        f"{datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST')}"
    )

    # Phase 1: 시간 확인
    if not check_market_time(args.force, session):
        return 0

    # Phase 2: 매크로 데이터 수집
    futures_data, market_data, market_news, theme_data, news_collector = collect_macro_data(cache)

    print_header(market_data, futures_data)

    # 킬스위치 확인
    should_stop, reason = is_market_killswitch(market_data)
    if should_stop:
        print_warning(f"시장 킬스위치 발동: {reason}")
        if args.discord:
            send_recommendations([], market_data, futures_data, session=session)
        return 0

    # Phase 3: 종목 데이터 수집
    stock_data, volume_data = collect_stock_data(cache)
    if stock_data is None:
        return 0

    print_info(f"종목 데이터: {len(stock_data)}개 종목")

    # Phase 4: 후보 필터링
    logger.info("=== Phase 4: 후보 종목 필터링 ===")
    candidates = get_candidates(stock_data, volume_data, theme_data)

    if not candidates:
        print_warning("후보 종목이 없습니다")
        return 0

    # NXT 세션: NXT 거래 가능 종목만 추가 필터링
    if session == "nxt":
        logger.info("=== NXT 세션: NXT 지정종목 필터 적용 ===")
        candidates = filter_nxt_candidates(candidates, cache)
        if not candidates:
            print_warning("NXT 거래 가능 후보 종목이 없습니다")
            return 0

    print_info(f"최종 후보 종목: {len(candidates)}개")

    # Phase 5: 복합 스코어링
    logger.info("=== Phase 5: 복합 스코어링 ===")
    scored = score_all_candidates(
        candidates=candidates,
        stock_data=stock_data,
        market_data=market_data,
        futures_data=futures_data,
        volume_data=volume_data,
        theme_data=theme_data,
        news_collector=news_collector,
        market_news=market_news,
    )

    print_info(f"스코어링 완료: {len(scored)}개 종목")

    # Phase 6: 최종 추천 생성
    logger.info("=== Phase 6: 최종 추천 생성 ===")
    recs = generate_recommendations(
        scored_candidates=scored,
        market_data=market_data,
        n=args.top,
    )

    # Phase 7: 콘솔 출력
    print_recommendations(recs)
    print_reasons(recs)

    # Phase 8: Discord 전송
    if args.discord:
        send_recommendations(recs, market_data, futures_data, session=session)

    # Phase 9: 리포트 저장
    if not args.no_save:
        try:
            filepath = save_report(recs, market_data, futures_data)
            print_info(f"리포트 저장 완료: {filepath}")
        except Exception as e:
            print_warning(f"리포트 저장 실패: {e}")

    return len(recs)


def main():
    args = parse_args()

    if args.debug:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        n = run(args)
        if n == 0:
            print_info("추천 종목 없음 - 시장 상황을 재확인하세요")
    except KeyboardInterrupt:
        print_info("\n사용자 중단")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"예기치 않은 오류: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
