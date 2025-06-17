from __future__ import annotations

"""Utility helpers for stock screeners."""

import os
import subprocess
from datetime import datetime
from typing import Dict


def ensure_pykrx() -> None:
    """Ensure that the ``pykrx`` package is installed."""
    try:
        import pykrx  # type: ignore  # noqa: F401
    except ImportError:
        print("pykrx not found. Attempting to install...")
        subprocess.check_call([
            "python3",
            "-m",
            "pip",
            "install",
            "pykrx",
        ])


def load_market_caps(date: datetime) -> Dict[str, float]:
    """Return market caps for all tickers on ``date``."""
    from pykrx import stock

    df = stock.get_market_cap_by_ticker(date.strftime("%Y%m%d"))
    caps = df["시가총액"].to_dict()
    return {str(k): float(v) for k, v in caps.items()}


def get_ticker_name(ticker: str) -> str:
    """Return the Korean name for the given ticker."""
    from pykrx import stock
    
    try:
        name = stock.get_market_ticker_name(ticker)
        return name
    except Exception:
        return ticker  # 오류 발생 시 티커 코드 반환


import pandas as pd


# 전체 종목의 RS 원시 점수를 저장할 전역 변수
_rs_raw_scores = {}
_rs_percentile_scores = {}
_rs_scores_calculated = False

def calculate_raw_rs(df: pd.DataFrame) -> float:
    """Calculate raw RS score based on weighted returns.
    
    Calculation based on:
    1. Calculate returns for 3, 6, 9, and 12 months
    2. Apply weights: 40% for 3 months, 20% for each of the others
    
    Returns:
        Weighted return value
    """
    # Check if we have enough data
    if len(df) < 252:  # Need at least a year of data
        # Fall back to simple RS calculation
        last_price = df["종가"].iloc[-1]
        high52 = df["종가"].rolling(min(len(df), 252)).max().iloc[-1]
        low52 = df["종가"].rolling(min(len(df), 252)).min().iloc[-1]
        if high52 == low52:
            return 0.0
        return 100 * (last_price - low52) / (high52 - low52)
    
    # Get current price
    current_price = df["종가"].iloc[-1]
    
    # Calculate returns for different periods
    # Using business days approximation: 63 days ≈ 3 months, 126 days ≈ 6 months, etc.
    try:
        price_3m = df["종가"].iloc[-min(len(df), 63)]
        price_6m = df["종가"].iloc[-min(len(df), 126)]
        price_9m = df["종가"].iloc[-min(len(df), 189)]
        price_12m = df["종가"].iloc[-min(len(df), 252)]
        
        # Calculate returns
        return_3m = ((current_price - price_3m) / price_3m) * 100 if price_3m > 0 else 0
        return_6m = ((current_price - price_6m) / price_6m) * 100 if price_6m > 0 else 0
        return_9m = ((current_price - price_9m) / price_9m) * 100 if price_9m > 0 else 0
        return_12m = ((current_price - price_12m) / price_12m) * 100 if price_12m > 0 else 0
        
        # Apply weights according to IBD methodology
        weighted_return = (return_3m * 0.4) + (return_6m * 0.2) + (return_9m * 0.2) + (return_12m * 0.2)
        
        return weighted_return
    except Exception:
        # Fall back to simple RS calculation if any error occurs
        last_price = df["종가"].iloc[-1]
        high52 = df["종가"].rolling(min(len(df), 252)).max().iloc[-1]
        low52 = df["종가"].rolling(min(len(df), 252)).min().iloc[-1]
        if high52 == low52:
            return 0.0
        return 100 * (last_price - low52) / (high52 - low52)


def calculate_all_rs_scores() -> None:
    """Calculate RS scores for all stocks and convert to percentile ranks.
    
    This function scans all stock data files, calculates raw RS scores,
    and then converts them to percentile ranks (1-99 scale).
    """
    global _rs_raw_scores, _rs_percentile_scores, _rs_scores_calculated
    
    # 이미 계산되었으면 다시 계산하지 않음
    if _rs_scores_calculated:
        return
    
    print("모든 종목의 RS 점수를 계산하는 중...")
    
    # 데이터 디렉토리 확인
    data_dir = "data"
    if not os.path.isdir(data_dir):
        print("데이터 디렉토리가 없습니다. RS 점수 계산을 건너뜁니다.")
        return
    
    # 모든 종목의 원시 RS 점수 계산
    for file in os.listdir(data_dir):
        if not file.endswith(".csv"):
            continue
        
        ticker = os.path.splitext(file)[0]
        path = os.path.join(data_dir, file)
        
        try:
            df = pd.read_csv(path, index_col=0, parse_dates=True)
            if df.empty:
                continue
                
            # 원시 RS 점수 계산
            raw_score = calculate_raw_rs(df)
            _rs_raw_scores[ticker] = raw_score
        except Exception as e:
            print(f"{ticker} RS 점수 계산 오류: {e}")
    
    # 원시 점수가 없으면 종료
    if not _rs_raw_scores:
        print("계산된 RS 점수가 없습니다.")
        return
    
    # 원시 점수를 기준으로 정렬하여 백분위 순위 계산
    sorted_tickers = sorted(_rs_raw_scores.keys(), key=lambda x: _rs_raw_scores[x], reverse=True)
    total_stocks = len(sorted_tickers)
    
    for i, ticker in enumerate(sorted_tickers):
        # 백분위 순위 계산 (1-99 스케일)
        percentile = 100 - ((i / total_stocks) * 100)
        _rs_percentile_scores[ticker] = round(percentile)
    
    _rs_scores_calculated = True
    print(f"총 {total_stocks}개 종목의 RS 점수 계산 완료")


def relative_strength(df: pd.DataFrame, ticker: str = None) -> float:
    """Compute IBD-style relative strength score.
    
    Calculation based on:
    1. Calculate returns for 3, 6, 9, and 12 months
    2. Apply weights: 40% for 3 months, 20% for each of the others
    3. Convert to percentile rank (1-99 scale)
    
    Args:
        df: DataFrame containing price data
        ticker: Ticker symbol (required for percentile calculation)
        
    Returns:
        RS score (1-99 scale) if ticker is provided and scores are calculated,
        otherwise raw weighted return
    """
    global _rs_percentile_scores, _rs_raw_scores, _rs_scores_calculated
    
    # 티커가 제공되고 백분위 점수가 계산되어 있으면 백분위 점수 반환
    if ticker and _rs_scores_calculated and ticker in _rs_percentile_scores:
        return _rs_percentile_scores[ticker]
    
    # 티커가 제공되었지만 백분위 점수가 계산되어 있지 않으면 원시 점수 계산
    if ticker and not _rs_scores_calculated:
        # 원시 점수 계산
        raw_score = calculate_raw_rs(df)
        _rs_raw_scores[ticker] = raw_score
        return raw_score
    
    # 티커가 제공되지 않았어도 IBD 스타일 RS 점수 계산
    # 원시 점수를 계산하고 전체 점수 분포에서의 상대적 위치를 추정
    raw_score = calculate_raw_rs(df)
    
    # 원시 점수가 있으면 해당 점수와 가장 가까운 백분위 점수 찾기
    if _rs_scores_calculated and _rs_raw_scores:
        # 원시 점수와 가장 가까운 점수 찾기
        closest_ticker = min(_rs_raw_scores.keys(), key=lambda x: abs(_rs_raw_scores[x] - raw_score))
        return _rs_percentile_scores.get(closest_ticker, raw_score)
    
    return raw_score  # 백분위 점수를 계산할 수 없는 경우 원시 점수 반환
