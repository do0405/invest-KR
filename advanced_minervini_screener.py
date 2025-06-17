from __future__ import annotations

"""Run the Advanced Mark Minervini style stock screener with financial statement criteria."""

import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import dart_fss as dart

from screener_utils import ensure_pykrx, load_market_caps, relative_strength, get_ticker_name, calculate_raw_rs, calculate_all_rs_scores
from minervini_screener import minervini_screener

DATA_DIR = "data"
RESULT_DIR = "result"

# 재무제표 데이터 캐시
FINANCIAL_DATA_CACHE = {}


def setup_dart_api():
    """Set up the DART API key."""
    # 여기에 API 키를 직접 입력하세요
    api_key = "366d2006d4fdbcf450523598f07a9229cada1e3e"  # 예: "1a2b3c4d5e6f7g8h9i0j"
    
    # 환경 변수에서 API 키 가져오기 시도
    if not api_key:
        api_key = os.environ.get("DART_API_KEY")
    
    # API 키가 없으면 사용자에게 안내
    if not api_key:
        print("\n" + "=" * 80)
        print("DART API 키가 필요합니다.")
        print("1. https://opendart.fss.or.kr 에서 회원가입 후 API 키를 발급받으세요.")
        print("2. 발급받은 API 키를 환경 변수 DART_API_KEY에 설정하거나 아래 코드에 직접 입력하세요.")
        print("   - 코드에 직접 입력: advanced_minervini_screener.py 파일의 api_key 변수에 입력")
        print("   - 환경 변수 설정: PowerShell에서 $env:DART_API_KEY='발급받은키' 실행")
        print("=" * 80 + "\n")
        
        # 사용자 입력 받기
        api_key = input("DART API 키를 입력하세요: ").strip()
        
        if not api_key:
            print("API 키가 제공되지 않았습니다. 재무제표 기준을 적용할 수 없습니다.")
            return False
    
    # API 키 설정
    dart.set_api_key(api_key)
    return True


def get_corp_code(ticker: str) -> Optional[str]:
    """Get the corporation code for the given ticker."""
    try:
        # 회사 목록 가져오기
        corp_list = dart.get_corp_list()
        # 티커로 회사 찾기
        corps = corp_list.find_by_stock_code(ticker)
        
        # corps가 None인 경우 처리
        if corps is None:
            print(f"No corporation found for ticker {ticker}")
            return None
            
        # corps가 리스트 또는 이터러블인 경우
        if hasattr(corps, '__iter__') and not isinstance(corps, str):
            try:
                if len(corps) > 0:
                    return corps[0].corp_code
                else:
                    print(f"Empty corporation list for ticker {ticker}")
                    return None
            except TypeError as e:
                # corps가 이터러블이지만 len()을 지원하지 않는 경우
                # 단일 객체로 처리
                return corps.corp_code
        else:
            # corps가 단일 객체인 경우
            return corps.corp_code
    except Exception as e:
        print(f"Error getting corporation code for {ticker}: {e}")
    return None


def get_financial_statements(corp_code: str, years: int = 3) -> Dict:
    """Get financial statements for the given corporation code.
    
    필요한 정보만 빠르게 추출하도록 최적화된 함수입니다.
    """
    # 캐시에 있으면 캐시된 데이터 반환
    if corp_code in FINANCIAL_DATA_CACHE:
        return FINANCIAL_DATA_CACHE[corp_code]
    
    try:
        # 현재 날짜 기준으로 과거 데이터 가져오기
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365 * years)
        
        # 회사 객체 가져오기
        corp_list = dart.get_corp_list()
        corps = corp_list.find_by_corp_code(corp_code)
        
        # corps가 None이거나 빈 리스트인 경우 처리
        if not corps:
            print(f"No corporation found for corp_code {corp_code}")
            return {}
            
        # corps가 리스트 또는 이터러블인 경우
        if hasattr(corps, '__iter__') and not isinstance(corps, str):
            try:
                if len(corps) > 0:
                    corp = corps[0]
                else:
                    print(f"Empty corporation list for corp_code {corp_code}")
                    return {}
            except TypeError:
                # corps가 이터러블이지만 len()을 지원하지 않는 경우
                # 단일 객체로 처리
                corp = corps
        else:
            # corps가 단일 객체인 경우
            corp = corps
        
        # 필요한 정보만 추출하기 위한 설정
        required_statements = {
            '손익계산서': ['기본주당이익', '매출액', '영업이익'],
            '재무상태표': ['자본총계', '부채총계']
        }
        
        try:
            # 재무제표 추출
            fs = corp.extract_fs(start_date.strftime('%Y%m%d'), end_date.strftime('%Y%m%d'))
            
            # 필요한 정보만 필터링
            filtered_fs = {}
            for statement_type, required_items in required_statements.items():
                if statement_type in fs:
                    filtered_fs[statement_type] = {}
                    for period_type in ['분기별', '연간']:
                        if period_type in fs[statement_type]:
                            # 필요한 행만 추출
                            df = fs[statement_type][period_type]
                            available_items = [item for item in required_items if item in df.index]
                            if available_items:
                                filtered_fs[statement_type][period_type] = df.loc[available_items]
            
            # 캐시에 저장
            FINANCIAL_DATA_CACHE[corp_code] = filtered_fs
            
            # API 호출 제한 방지를 위한 딜레이
            time.sleep(0.5)
            
            return filtered_fs
        except Exception as e:
            print(f"Error extracting financial statements for {corp_code}: {e}")
            return {}
    except Exception as e:
        print(f"Error getting financial statements for {corp_code}: {e}")
        return {}


def check_financial_criteria(ticker: str) -> bool:
    """Check if the stock meets Mark Minervini's financial criteria."""
    # 회사 코드 가져오기
    corp_code = get_corp_code(ticker)
    if not corp_code:
        print(f"Corporation code not found for {ticker}")
        return False
    
    # 재무제표 가져오기
    fs = get_financial_statements(corp_code)
    if not fs:
        print(f"Financial statements not found for {ticker}")
        return False
        
    # 필요한 키가 있는지 먼저 확인
    required_keys = ['손익계산서', '재무상태표']
    for key in required_keys:
        if key not in fs:
            print(f"{ticker}: {key} 데이터가 없습니다.")
            return False
            
    # 손익계산서와 재무상태표의 하위 키 확인
    for statement_type in ['분기별', '연간']:
        if statement_type not in fs['손익계산서']:
            print(f"{ticker}: 손익계산서의 {statement_type} 데이터가 없습니다.")
            return False
        
    if '연간' not in fs['재무상태표']:
        print(f"{ticker}: 재무상태표의 연간 데이터가 없습니다.")
        return False
    
    try:
        # 1. 분기별 EPS 증가율 확인 (최소 25% 이상, 최소 2분기 연속 가속화)
        try:
            # 필요한 행 키가 있는지 확인
            if '기본주당이익' not in fs['손익계산서']['분기별'].index:
                print(f"{ticker}: 분기별 EPS 데이터(기본주당이익)가 없습니다.")
                return False
                
            # 분기별 EPS 데이터 가져오기
            quarterly_eps = fs['손익계산서']['분기별'].loc['기본주당이익']
            
            # 최근 4분기 데이터 확인
            if len(quarterly_eps.columns) < 4:
                print(f"{ticker}: 충분한 분기별 EPS 데이터가 없습니다.")
                return False
            
            # 최근 3분기의 증가율 계산
            eps_growth_rates = []
            for i in range(1, 4):
                current_eps = quarterly_eps.iloc[0, -i]
                prev_eps = quarterly_eps.iloc[0, -(i+1)]
                
                # EPS가 음수에서 양수로 변경된 경우 100% 성장으로 간주
                if prev_eps <= 0 and current_eps > 0:
                    growth_rate = 100
                # 이전 EPS가 0이면 성장률 계산 불가
                elif prev_eps == 0:
                    growth_rate = 0 if current_eps == 0 else 100
                else:
                    growth_rate = ((current_eps - prev_eps) / abs(prev_eps)) * 100
                
                eps_growth_rates.append(growth_rate)
            
            # 최근 분기 EPS 증가율이 25% 미만이면 탈락
            if eps_growth_rates[0] < 25:
                return False
            
            # 최소 2분기 연속 가속화 확인
            if not (eps_growth_rates[0] > eps_growth_rates[1] and eps_growth_rates[1] > eps_growth_rates[2]):
                return False
        except Exception as e:
            print(f"{ticker}: EPS 데이터 분석 중 오류 발생 - {e}")
            return False
        
        # 2. 연간 EPS 성장률 확인 (최근 3년간 최소 15% 이상)
        try:
            # 필요한 행 키가 있는지 확인
            if '기본주당이익' not in fs['손익계산서']['연간'].index:
                print(f"{ticker}: 연간 EPS 데이터(기본주당이익)가 없습니다.")
                return False
                
            # 연간 EPS 데이터 가져오기
            annual_eps = fs['손익계산서']['연간'].loc['기본주당이익']
            
            # 최근 3년 데이터 확인
            if len(annual_eps.columns) < 3:
                print(f"{ticker}: 충분한 연간 EPS 데이터가 없습니다.")
                return False
            
            # 최근 3년의 증가율 계산
            for i in range(1, 3):
                current_eps = annual_eps.iloc[0, -i]
                prev_eps = annual_eps.iloc[0, -(i+1)]
                
                # EPS가 음수에서 양수로 변경된 경우 통과
                if prev_eps <= 0 and current_eps > 0:
                    continue
                # 이전 EPS가 0이면 성장률 계산 불가
                elif prev_eps == 0:
                    if current_eps <= 0:
                        return False
                    continue
                
                growth_rate = ((current_eps - prev_eps) / abs(prev_eps)) * 100
                if growth_rate < 15:
                    return False
        except Exception as e:
            print(f"{ticker}: 연간 EPS 데이터 분석 중 오류 발생 - {e}")
            return False
        
        # 3. 분기별 매출 증가율 확인 (최소 25% 이상, 최소 2분기 연속 가속화)
        try:
            # 필요한 행 키가 있는지 확인
            if '매출액' not in fs['손익계산서']['분기별'].index:
                print(f"{ticker}: 분기별 매출 데이터(매출액)가 없습니다.")
                return False
                
            # 분기별 매출 데이터 가져오기
            quarterly_revenue = fs['손익계산서']['분기별'].loc['매출액']
            
            # 최근 4분기 데이터 확인
            if len(quarterly_revenue.columns) < 4:
                print(f"{ticker}: 충분한 분기별 매출 데이터가 없습니다.")
                return False
            
            # 최근 3분기의 증가율 계산
            revenue_growth_rates = []
            for i in range(1, 4):
                current_revenue = quarterly_revenue.iloc[0, -i]
                prev_revenue = quarterly_revenue.iloc[0, -(i+1)]
                
                if prev_revenue == 0:
                    growth_rate = 0 if current_revenue == 0 else 100
                else:
                    growth_rate = ((current_revenue - prev_revenue) / abs(prev_revenue)) * 100
                
                revenue_growth_rates.append(growth_rate)
            
            # 최근 분기 매출 증가율이 25% 미만이면 탈락
            if revenue_growth_rates[0] < 25:
                return False
            
            # 최소 2분기 연속 가속화 확인
            if not (revenue_growth_rates[0] > revenue_growth_rates[1] and revenue_growth_rates[1] > revenue_growth_rates[2]):
                return False
        except Exception as e:
            print(f"{ticker}: 매출 데이터 분석 중 오류 발생 - {e}")
            return False
        
        # 4. 연간 매출 성장률 확인 (최근 3년간 최소 15% 이상)
        try:
            # 필요한 행 키가 있는지 확인
            if '매출액' not in fs['손익계산서']['연간'].index:
                print(f"{ticker}: 연간 매출 데이터(매출액)가 없습니다.")
                return False
                
            # 연간 매출 데이터 가져오기
            annual_revenue = fs['손익계산서']['연간'].loc['매출액']
            
            # 최근 3년 데이터 확인
            if len(annual_revenue.columns) < 3:
                print(f"{ticker}: 충분한 연간 매출 데이터가 없습니다.")
                return False
            
            # 최근 3년의 증가율 계산
            for i in range(1, 3):
                current_revenue = annual_revenue.iloc[0, -i]
                prev_revenue = annual_revenue.iloc[0, -(i+1)]
                
                if prev_revenue == 0:
                    if current_revenue <= 0:
                        return False
                    continue
                
                growth_rate = ((current_revenue - prev_revenue) / abs(prev_revenue)) * 100
                if growth_rate < 15:
                    return False
        except Exception as e:
            print(f"{ticker}: 연간 매출 데이터 분석 중 오류 발생 - {e}")
            return False
        
        # 5. 영업이익 증가율 확인 (30~40% 이상, 4~6분기 연속 견조한 영업이익)
        try:
            # 필요한 행 키가 있는지 확인
            if '영업이익' not in fs['손익계산서']['분기별'].index:
                print(f"{ticker}: 분기별 영업이익 데이터가 없습니다.")
                return False
                
            # 분기별 영업이익 데이터 가져오기
            quarterly_op_profit = fs['손익계산서']['분기별'].loc['영업이익']
            
            # 최근 6분기 데이터 확인
            min_quarters = min(6, len(quarterly_op_profit.columns))
            if min_quarters < 4:
                print(f"{ticker}: 충분한 분기별 영업이익 데이터가 없습니다.")
                return False
            
            # 최근 분기들의 영업이익이 모두 양수인지 확인
            for i in range(1, min_quarters + 1):
                if quarterly_op_profit.iloc[0, -i] <= 0:
                    return False
            
            # 최근 분기 영업이익 증가율 계산
            current_op_profit = quarterly_op_profit.iloc[0, -1]
            prev_op_profit = quarterly_op_profit.iloc[0, -2]
            
            if prev_op_profit == 0:
                op_profit_growth = 100 if current_op_profit > 0 else 0
            else:
                op_profit_growth = ((current_op_profit - prev_op_profit) / abs(prev_op_profit)) * 100
            
            # 영업이익 증가율이 30% 미만이면 탈락
            if op_profit_growth < 30:
                return False
        except Exception as e:
            print(f"{ticker}: 영업이익 데이터 분석 중 오류 발생 - {e}")
            return False
        
        # 6. 부채비율 확인 (150% 이하)
        try:
            # 최근 재무상태표 가져오기
            balance_sheet = fs['재무상태표']['연간']
            
            # 필요한 행 키가 있는지 확인
            required_bs_keys = ['자본총계', '부채총계']
            for key in required_bs_keys:
                if key not in balance_sheet.index:
                    print(f"{ticker}: 재무상태표에 {key} 데이터가 없습니다.")
                    return False
            
            # 자본총계와 부채총계 가져오기
            total_equity = balance_sheet.loc['자본총계'].iloc[0, -1]
            total_debt = balance_sheet.loc['부채총계'].iloc[0, -1]
            
            # 부채비율 계산
            if total_equity <= 0:
                return False  # 자본이 0 이하면 탈락
            
            debt_ratio = (total_debt / total_equity) * 100
            
            # 부채비율이 150% 초과면 탈락
            if debt_ratio > 150:
                return False
        except Exception as e:
            print(f"{ticker}: 부채비율 계산 중 오류 발생 - {e}")
            return False
        
        # 모든 기준을 통과
        return True
        
    except Exception as e:
        print(f"Error checking financial criteria for {ticker}: {e}")
        return False


def advanced_minervini_screener(df: pd.DataFrame, ticker: str = None) -> bool:
    """Return ``True`` if ``df`` meets Advanced Mark Minervini criteria."""
    # 기본 미너비니 기준 확인
    if not minervini_screener(df, ticker):
        return False
    
    # 재무제표 기준 확인
    if not check_financial_criteria(ticker):
        return False
    
    return True


def run() -> None:
    """Execute the Advanced Minervini screener and save results."""
    ensure_pykrx()
    
    # DART API 설정
    if not setup_dart_api():
        print("DART API 설정에 실패했습니다. 기본 미너비니 스크리너만 실행합니다.")
        return
    
    today = datetime.today()
    caps = load_market_caps(today)  # not strictly needed but maybe useful

    # 모든 종목의 RS 점수 계산
    calculate_all_rs_scores()

    rows: list[dict[str, Any]] = []

    if not os.path.isdir(DATA_DIR):
        print("data directory not found. Run download_ohlcv.py first.")
        return

    print("고급 미너비니 스크리너 실행 중...")
    print("이 과정은 DART API를 통해 재무제표 데이터를 가져오므로 시간이 오래 걸릴 수 있습니다.")
    
    for file in os.listdir(DATA_DIR):
        if not file.endswith(".csv"):
            continue
        ticker = os.path.splitext(file)[0]
        path = os.path.join(DATA_DIR, file)
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        if df.empty:
            continue

        print(f"분석 중: {ticker} - {get_ticker_name(ticker)}")
        
        if advanced_minervini_screener(df, ticker):
            try:
                rs_value = relative_strength(df, ticker)
            except Exception as e:
                print(f"RS 점수 계산 오류: {e}, 기본값 0 사용")
                rs_value = 0
                
            rows.append({
                "ticker": ticker, 
                "name": get_ticker_name(ticker),
                "relative_strength": rs_value
            })

    os.makedirs(RESULT_DIR, exist_ok=True)

    if rows:
        result_df = pd.DataFrame(rows).sort_values("relative_strength", ascending=False)
    else:
        print("조건을 만족하는 종목이 없습니다.")
        result_df = pd.DataFrame(columns=["ticker", "name", "relative_strength"])
        
    result_df.to_csv(os.path.join(RESULT_DIR, "advanced_minervini_screener.csv"), index=False, encoding="utf-8-sig")
    result_df.to_json(os.path.join(RESULT_DIR, "advanced_minervini_screener.json"), orient="records", force_ascii=False)
    
    print(f"고급 미너비니 스크리너 완료. 결과: {len(rows)}개 종목 발견")
    print(f"결과 파일: {os.path.join(RESULT_DIR, 'advanced_minervini_screener.csv')}")


if __name__ == "__main__":
    run()