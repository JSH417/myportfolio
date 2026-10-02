import yfinance as yf
import requests
import re
from database import get_connection

def get_usd_krw_rate() -> float:
    """실시간 USD/KRW 환율 조회 (yfinance 기반 및 네이버 백업)"""
    try:
        ticker = yf.Ticker("USDKRW=X")
        data = ticker.history(period="1d")
        if not data.empty:
            rate = float(data['Close'].iloc[-1])
            save_exchange_rate("USD/KRW", rate)
            return round(rate, 2)
    except Exception as e:
        print(f"yfinance 환율 수집 실패: {e}")

    # 백업: 네이버 환율 크롤링
    try:
        url = "https://m.stock.naver.com/marketindex/exchange/FX_USDKRW"
        res = requests.get(url, timeout=5)
        # fallback to cached rate
    except Exception:
        pass

    # DB 캐시된 환율 반환
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT rate FROM exchange_rates WHERE currency_pair = 'USD/KRW'")
    row = c.fetchone()
    conn.close()
    if row:
        return row['rate']
    return 1380.0  # 기본 fallback

def save_exchange_rate(pair: str, rate: float):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO exchange_rates (currency_pair, rate, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(currency_pair) DO UPDATE SET rate=excluded.rate, updated_at=CURRENT_TIMESTAMP
    """, (pair, rate))
    conn.commit()
    conn.close()

def get_current_price(symbol: str, asset_type: str) -> float:
    """
    종목별 최신 현재가 조회
    - USD_RP, CASH 등은 단가 1.0 유지 (또는 1달러 = 1달러)
    - KR_ETF: '069500' -> '069500.KS' (야후파이낸스 또는 네이버)
    - US_ETF: 'VOO', 'QQQ', 'SCHD'
    """
    if asset_type in ['USD_RP', 'CASH_USD']:
        return 1.0  # 달러 단위 기준 1$
    if asset_type == 'CASH_KRW':
        return 1.0  # 원화 단위 기준 1원

    # 한국 ETF / 주식 심볼 정규화 (숫자 6자리인 경우)
    yf_symbol = symbol
    if re.match(r'^\d{6}$', symbol):
        yf_symbol = f"{symbol}.KS"

    try:
        ticker = yf.Ticker(yf_symbol)
        data = ticker.history(period="1d", interval="1m")
        if data.empty:
            data = ticker.history(period="5d")
        if not data.empty:
            return round(float(data['Close'].iloc[-1]), 2)
    except Exception as e:
        print(f"시세 조회 실패 ({symbol}): {e}")

    # 한국 종목일 때 네이버 증권 간이 조회 백업
    if re.match(r'^\d{6}$', symbol):
        try:
            url = f"https://m.stock.naver.com/api/stock/{symbol}/basic"
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                json_data = r.json()
                close_price = json_data.get("closePrice", "").replace(",", "")
                if close_price:
                    return float(close_price)
        except Exception as e:
            print(f"네이버 시세 조회 실패 ({symbol}): {e}")

    return 0.0

def lookup_ticker_info(symbol: str):
    """티커(심볼) 입력 시 종목명, 현재가, 통화, 배당률 자동 조회"""
    symbol = symbol.strip().upper()
    
    # 1. 외화 RP 특수 케이스
    if symbol in ['USD_RP', 'RP']:
        return {
            "symbol": "USD_RP",
            "name": "온라인전용_수시RP(USD)",
            "asset_type": "USD_RP",
            "currency": "USD",
            "current_price": 1.0,
            "dividend_yield": 3.35
        }

    # 2. 국내 종목 (숫자 6자리)
    if re.match(r'^\d{6}$', symbol):
        stock_name = symbol
        close_price = 0.0
        div_yield = 0.0

        try:
            url = f"https://m.stock.naver.com/api/stock/{symbol}/basic"
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, headers=headers, timeout=4)
            if r.status_code == 200:
                data = r.json()
                stock_name = data.get("stockName", "") or symbol
                close_price = float(data.get("closePrice", "0").replace(",", ""))
        except Exception as e:
            print(f"네이버 기본정보 실패: {e}")

        # 최근 365일간 실제 지급된 분배금 실적 합산 (토스증권 및 증권사 표준)
        try:
            t = yf.Ticker(f"{symbol}.KS")
            divs = t.dividends
            if not divs.empty:
                import datetime
                now = datetime.datetime.now(divs.index.tz)
                one_yr_ago = now - datetime.timedelta(days=365)
                recent_1yr = divs[divs.index >= one_yr_ago]
                sum_div = float(recent_1yr.sum())
                if close_price > 0 and sum_div > 0:
                    div_yield = round((sum_div / close_price) * 100, 2)
        except Exception as e:
            print(f"분배금 실적 조회 실패: {e}")

        return {
            "symbol": symbol,
            "name": stock_name,
            "asset_type": "KR_ETF",
            "currency": "KRW",
            "current_price": close_price,
            "dividend_yield": div_yield
        }

    # 3. 미국 종목 / 글로벌 ETF (yfinance)
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        last_price = round(float(info.last_price), 2) if hasattr(info, 'last_price') and info.last_price else 0.0
        
        # 이름 가져오기
        name = symbol
        try:
            name = ticker.info.get("shortName") or ticker.info.get("longName") or symbol
        except Exception:
            pass

        div_yield = 0.0
        try:
            div_yield = round(float(ticker.info.get("dividendYield", 0) or 0) * 100, 2)
        except Exception:
            pass

        return {
            "symbol": symbol,
            "name": name,
            "asset_type": "US_ETF",
            "currency": "USD",
            "current_price": last_price,
            "dividend_yield": div_yield
        }
    except Exception as e:
        print(f"yfinance 티커 조회 실패: {e}")

    return {"symbol": symbol, "name": symbol, "current_price": 0.0}

def get_historical_candles(symbol: str, asset_type: str, period="6mo", interval="1d"):
    """개별 ETF 종목별 차트용 과거 주가 캔들 데이터 수집"""
    if asset_type in ['USD_RP', 'CASH_USD', 'CASH_KRW']:
        return []

    yf_symbol = symbol
    if re.match(r'^\d{6}$', symbol):
        yf_symbol = f"{symbol}.KS"

    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty and yf_symbol.endswith(".KS"):
            df = ticker.history(period=period, interval=interval)
        
        candles = []
        for index, row in df.iterrows():
            candles.append({
                "date": index.strftime("%Y-%m-%d"),
                "open": round(float(row['Open']), 2),
                "high": round(float(row['High']), 2),
                "low": round(float(row['Low']), 2),
                "close": round(float(row['Close']), 2),
                "volume": int(row['Volume'])
            })
        return candles
    except Exception as e:
        print(f"캔들 데이터 조회 실패 ({symbol}): {e}")
        return []
