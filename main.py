#!/usr/bin/env python3
"""
invest-KR 메인 실행 스크립트

이 스크립트는 다음 기능을 수행합니다:
1. OHLCV 데이터 다운로드 (기존 데이터가 있을 경우 업데이트)
2. 스크리닝 실행 (Setup 스크리너 및 Mark Minervini 스크리너)
3. 진행 상황 출력

사용법:
    python3 main.py
"""
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta
import pandas as pd
import time

# 스크리너 모듈 임포트
import setup_screener
import minervini_screener
import advanced_minervini_screener
from screener_utils import ensure_pykrx


def print_progress(message: str, progress: int = None, total: int = None) -> None:
    """
    진행 상황을 출력합니다.
    
    Args:
        message: 출력할 메시지
        progress: 현재 진행 상황 (선택 사항)
        total: 전체 작업량 (선택 사항)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if progress is not None and total is not None:
        percentage = (progress / total) * 100
        progress_bar = f"[{'#' * int(percentage // 5)}{' ' * (20 - int(percentage // 5))}]" 
        print(f"[{timestamp}] {message} - {progress}/{total} {progress_bar} {percentage:.1f}%")
    else:
        print(f"[{timestamp}] {message}")


def get_tickers() -> list[str]:
    """
    모든 KOSPI 및 KOSDAQ 종목 코드를 반환합니다.
    """
    from pykrx import stock

    print_progress("KOSPI 종목 코드를 가져오는 중...")
    tickers = stock.get_market_ticker_list(market="KOSPI")
    print_progress(f"KOSPI 종목 {len(tickers)}개를 가져왔습니다.")
    
    print_progress("KOSDAQ 종목 코드를 가져오는 중...")
    kosdaq_tickers = stock.get_market_ticker_list(market="KOSDAQ")
    print_progress(f"KOSDAQ 종목 {len(kosdaq_tickers)}개를 가져왔습니다.")
    
    tickers += kosdaq_tickers
    print_progress(f"총 {len(tickers)}개 종목 코드를 가져왔습니다.")
    return tickers


def get_latest_date_from_csv(csv_path: str) -> datetime | None:
    """
    CSV 파일에서 가장 최근 날짜를 가져옵니다.
    
    Args:
        csv_path: CSV 파일 경로
        
    Returns:
        가장 최근 날짜 또는 파일이 없거나 비어있을 경우 None
    """
    if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
        return None
    
    try:
        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        if df.empty:
            return None
        # 인덱스가 날짜인 경우
        if isinstance(df.index, pd.DatetimeIndex):
            return df.index[-1].to_pydatetime()
        # 날짜 열이 있는 경우
        elif '날짜' in df.columns:
            return pd.to_datetime(df['날짜'].iloc[-1]).to_pydatetime()
        return None
    except Exception as e:
        print_progress(f"경고: {csv_path} 파일 읽기 오류 - {e}")
        return None


def save_ohlcv(ticker: str, start: datetime, end: datetime) -> None:
    """
    특정 종목의 OHLCV 데이터를 가져와 저장합니다.
    기존 데이터가 있는 경우 업데이트합니다.
    최적화: 영업일 기준으로 필요한 데이터만 가져옵니다.
    
    Args:
        ticker: 종목 코드
        start: 시작 날짜
        end: 종료 날짜
    """
    from pykrx import stock
    
    os.makedirs("data", exist_ok=True)
    csv_path = os.path.join("data", f"{ticker}.csv")
    
    # 시작일과 종료일이 같거나 시작일이 더 나중이면 업데이트 불필요
    if start.date() >= end.date():
        return
    
    # 주말이나 공휴일을 건너뛰기 위해 시작일 조정
    current_start = start
    while not is_market_open_day(current_start) and current_start.date() < end.date():
        current_start += timedelta(days=1)
    
    if current_start.date() >= end.date():
        return
    
    # 데이터 가져오기
    try:
        df = stock.get_market_ohlcv_by_date(
            current_start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), ticker
        )
    except Exception as e:
        print_progress(f"{ticker}: 데이터 가져오기 오류 - {e}")
        return
    
    if df.empty:
        print_progress(f"{ticker}: 데이터가 없습니다")
        return
    
    # 기존 데이터와 병합
    if os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
        try:
            existing_df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
            if not existing_df.empty:
                # 중복 날짜 제거 후 병합
                df = pd.concat([existing_df, df])
                df = df[~df.index.duplicated(keep='last')]
                df.sort_index(inplace=True)
        except Exception as e:
            print_progress(f"경고: {ticker} 데이터 병합 오류 - {e}")
    
    # 저장
    df.to_csv(csv_path)
    # 상세 로그는 필요한 경우만 출력
    if len(df) > 0:
        print_progress(f"{ticker}: 데이터 저장 완료 (총 {len(df)}일)")


def is_market_open_day(date: datetime) -> bool:
    """
    주어진 날짜가 시장 개장일인지 확인합니다.
    
    Args:
        date: 확인할 날짜
        
    Returns:
        시장 개장일이면 True, 아니면 False
    """
    # 주말 체크
    if date.weekday() >= 5:  # 5: 토요일, 6: 일요일
        return False
        
    # 공휴일 체크는 pykrx의 get_market_ohlcv_by_date 함수가 내부적으로 처리함
    # 여기서는 주말만 체크
    
    return True


def get_last_market_day() -> datetime:
    """
    가장 최근 시장 개장일을 반환합니다.
    
    Returns:
        가장 최근 시장 개장일
    """
    today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 오늘이 개장일이면 어제 데이터까지만 있을 것이므로 어제 날짜 반환
    if is_market_open_day(today):
        # 현재 시간이 장 마감 이후인지 확인 (15:30 이후)
        if datetime.now().hour >= 15 and datetime.now().minute >= 30:
            return today  # 장 마감 이후면 오늘 날짜 반환
        else:
            # 장 마감 전이면 이전 개장일 찾기
            day = today - timedelta(days=1)
            while not is_market_open_day(day):
                day = day - timedelta(days=1)
            return day
    
    # 오늘이 개장일이 아니면 이전 개장일 찾기
    day = today - timedelta(days=1)
    while not is_market_open_day(day):
        day = day - timedelta(days=1)
    return day


def download_ohlcv_data() -> None:
    """
    모든 종목의 OHLCV 데이터를 다운로드하거나 업데이트합니다.
    최적화: 최신 데이터가 있는 경우 업데이트만 수행합니다.
    """
    print_progress("OHLCV 데이터 다운로드/업데이트를 시작합니다")
    ensure_pykrx()
    
    # 현재 기준 마지막 시장 개장일
    last_market_day = get_last_market_day()
    print_progress(f"마지막 시장 개장일: {last_market_day.strftime('%Y-%m-%d')}")
    
    end = datetime.today()
    # 약 400 거래일 (약 560 일)
    start = end - timedelta(days=560)
    
    tickers = get_tickers()
    print_progress(f"총 {len(tickers)}개 종목의 데이터를 처리합니다")
    
    # 업데이트가 필요한 종목 필터링
    update_needed = []
    already_updated = 0
    
    print_progress("업데이트가 필요한 종목을 확인하는 중...")
    for ticker in tickers:
        csv_path = os.path.join("data", f"{ticker}.csv")
        latest_date = get_latest_date_from_csv(csv_path)
        
        # 파일이 없거나 최신 데이터가 없는 경우
        if latest_date is None:
            update_needed.append((ticker, start, end))
        # 최신 데이터가 마지막 시장 개장일보다 이전인 경우
        elif latest_date.date() < last_market_day.date():
            # 최신 데이터 다음 날부터 업데이트
            update_start = latest_date + timedelta(days=1)
            update_needed.append((ticker, update_start, end))
        else:
            already_updated += 1
    
    print_progress(f"이미 최신 상태인 종목: {already_updated}개, 업데이트 필요한 종목: {len(update_needed)}개")
    
    # 업데이트가 필요한 종목이 없으면 종료
    if not update_needed:
        print_progress("모든 종목이 이미 최신 상태입니다.")
        return
    
    # 업데이트 진행
    success_count = 0
    error_count = 0
    
    for i, (ticker, start_date, end_date) in enumerate(update_needed):
        try:
            print_progress(f"종목 데이터 업데이트 중", i + 1, len(update_needed))
            save_ohlcv(ticker, start_date, end_date)
            success_count += 1
            # API 호출 제한을 피하기 위한 짧은 대기
            time.sleep(0.1)
        except Exception as exc:
            print_progress(f"{ticker} 데이터 가져오기 실패: {exc}")
            error_count += 1
    
    print_progress("OHLCV 데이터 처리 완료")
    print_progress(f"성공: {success_count}, 오류: {error_count}, 이미 최신: {already_updated}")


def run_screeners() -> None:
    """
    모든 스크리너를 실행합니다.
    """
    print_progress("스크리너 실행을 시작합니다")
    
    # Setup 스크리너 실행
    print_progress("Setup 스크리너 실행 중...")
    setup_screener.run()
    print_progress("Setup 스크리너 실행 완료")
    
    # Mark Minervini 스크리너 실행
    print_progress("Mark Minervini 스크리너 실행 중...")
    minervini_screener.run()
    print_progress("Mark Minervini 스크리너 실행 완료")
    
    # 고급 Mark Minervini 스크리너 실행 (재무제표 기준 포함)
    print_progress("고급 Mark Minervini 스크리너 실행 중...")
    try:
        advanced_minervini_screener.run()
        print_progress("고급 Mark Minervini 스크리너 실행 완료")
    except Exception as e:
        print_progress(f"고급 Mark Minervini 스크리너 실행 오류: {e}")
        print_progress("고급 스크리너를 별도로 실행하려면: python advanced_minervini_screener.py")
    
    print_progress("모든 스크리너 실행 완료")


def show_results() -> None:
    """
    스크리닝 결과를 출력합니다.
    """
    result_dir = "result"
    if not os.path.isdir(result_dir):
        print_progress("결과 디렉토리가 없습니다. 스크리너를 먼저 실행하세요.")
        return
    
    # Setup 스크리너 결과
    setup_result_path = os.path.join(result_dir, "setup_screener.csv")
    if os.path.exists(setup_result_path):
        try:
            setup_df = pd.read_csv(setup_result_path, encoding="utf-8-sig")
            print_progress(f"\nSetup 스크리너 결과 (총 {len(setup_df)}개 종목)")
            if not setup_df.empty:
                print("\n" + "=" * 50)
                # 출력할 열 순서 조정 (종목코드, 종목명, RS 순서로)
                if "name" in setup_df.columns:
                    cols = ["ticker", "name", "relative_strength"]
                    setup_df = setup_df[cols]
                print(setup_df.head(10).to_string(index=False))
                if len(setup_df) > 10:
                    print(f"... 외 {len(setup_df) - 10}개 종목")
                print("=" * 50 + "\n")
        except Exception as e:
            print_progress(f"Setup 스크리너 결과 읽기 오류: {e}")
    
    # Mark Minervini 스크리너 결과
    minervini_result_path = os.path.join(result_dir, "minervini_screener.csv")
    if os.path.exists(minervini_result_path):
        try:
            minervini_df = pd.read_csv(minervini_result_path, encoding="utf-8-sig")
            print_progress(f"\nMark Minervini 스크리너 결과 (총 {len(minervini_df)}개 종목)")
            if not minervini_df.empty:
                print("\n" + "=" * 50)
                # 출력할 열 순서 조정 (종목코드, 종목명, RS 순서로)
                if "name" in minervini_df.columns:
                    cols = ["ticker", "name", "relative_strength"]
                    minervini_df = minervini_df[cols]
                print(minervini_df.head(10).to_string(index=False))
                if len(minervini_df) > 10:
                    print(f"... 외 {len(minervini_df) - 10}개 종목")
                print("=" * 50 + "\n")
        except Exception as e:
            print_progress(f"Mark Minervini 스크리너 결과 읽기 오류: {e}")
    
    # 고급 Mark Minervini 스크리너 결과
    advanced_result_path = os.path.join(result_dir, "advanced_minervini_screener.csv")
    if os.path.exists(advanced_result_path):
        try:
            advanced_df = pd.read_csv(advanced_result_path, encoding="utf-8-sig")
            print_progress(f"\n고급 Mark Minervini 스크리너 결과 (총 {len(advanced_df)}개 종목)")
            if not advanced_df.empty:
                print("\n" + "=" * 50)
                # 출력할 열 순서 조정 (종목코드, 종목명, RS 순서로)
                if "name" in advanced_df.columns:
                    cols = ["ticker", "name", "relative_strength"]
                    advanced_df = advanced_df[cols]
                print(advanced_df.head(10).to_string(index=False))
                if len(advanced_df) > 10:
                    print(f"... 외 {len(advanced_df) - 10}개 종목")
                print("=" * 50 + "\n")
        except Exception as e:
            print_progress(f"고급 Mark Minervini 스크리너 결과 읽기 오류: {e}")


def main() -> None:
    """
    메인 함수: 데이터 다운로드, 스크리닝, 결과 출력을 순차적으로 실행합니다.
    """
    start_time = time.time()
    print_progress("invest-KR 프로그램을 시작합니다")
    
    # OHLCV 데이터 다운로드/업데이트
    download_ohlcv_data()
    
    # 스크리너 실행
    run_screeners()
    
    # 결과 출력
    show_results()
    
    elapsed_time = time.time() - start_time
    print_progress(f"모든 작업이 완료되었습니다. 소요 시간: {elapsed_time:.1f}초")


if __name__ == "__main__":
    main()