from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import Any, Union, List, Dict
import os
import uvicorn
from database import init_db, get_connection
import market_data
import parser
import datetime

app = FastAPI(title="ETF & 외화RP 올인원 포트폴리오")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/", response_class=HTMLResponse)
def index():
    html_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(html_file):
        with open(html_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>ETF Portfolio App Starting...</h1>"

@app.get("/api/summary")
def get_portfolio_summary():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM assets ORDER BY id DESC")
    rows = c.fetchall()

    usd_krw_rate = market_data.get_usd_krw_rate()

    assets = []
    total_val_krw = 0.0
    total_invested_krw = 0.0
    krw_assets_val = 0.0
    usd_assets_val_in_usd = 0.0
    usd_rp_val_in_usd = 0.0
    rp_daily_interest_total_usd = 0.0

    for r in rows:
        item = dict(r)
        qty = item["quantity"]
        avg = item["avg_price"]
        cur_price = item["current_price"] or avg
        curr = item["currency"]
        asset_type = item["asset_type"]

        val = qty * cur_price
        invested = qty * avg
        pnl = val - invested
        pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

        item["eval_value"] = round(val, 2)
        item["invested_value"] = round(invested, 2)
        item["pnl"] = round(pnl, 2)
        item["pnl_pct"] = round(pnl_pct, 2)

        if curr == "KRW":
            val_in_krw = val
            inv_in_krw = invested
            krw_assets_val += val
        else: # USD
            val_in_krw = val * usd_krw_rate
            inv_in_krw = invested * usd_krw_rate
            usd_assets_val_in_usd += val
            if asset_type == "USD_RP":
                usd_rp_val_in_usd += val
                # 외화 RP 하루치 일할 이자 ($ 및 ₩)
                rp_yield = item.get("dividend_yield") or 3.35
                daily_interest_usd = (val * (rp_yield / 100.0)) / 365.0
                monthly_interest_usd = daily_interest_usd * 30.0
                rp_daily_interest_total_usd += daily_interest_usd
                item["rp_daily_interest_usd"] = round(daily_interest_usd, 4)
                item["rp_daily_interest_krw"] = round(daily_interest_usd * usd_krw_rate, 1)
                item["rp_monthly_interest_usd"] = round(monthly_interest_usd, 2)
                item["rp_monthly_interest_krw"] = round(monthly_interest_usd * usd_krw_rate, 0)

        item["eval_value_krw"] = round(val_in_krw, 0)
        total_val_krw += val_in_krw
        total_invested_krw += inv_in_krw
        assets.append(item)

    total_val_usd = total_val_krw / usd_krw_rate if usd_krw_rate > 0 else 0.0
    total_pnl_krw = total_val_krw - total_invested_krw
    total_pnl_pct = (total_pnl_krw / total_invested_krw * 100) if total_invested_krw > 0 else 0.0

    # 당일 총자산 히스토리 자동 기록 (실제 보유 자산이 있을 때만 기록)
    if total_val_krw > 0:
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        c.execute("""
            INSERT INTO portfolio_history (record_date, total_val_krw, total_val_usd, total_invested_krw)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(record_date) DO UPDATE SET
                total_val_krw=excluded.total_val_krw,
                total_val_usd=excluded.total_val_usd,
                total_invested_krw=excluded.total_invested_krw
        """, (today_str, total_val_krw, total_val_usd, total_invested_krw))
        conn.commit()
    conn.close()

    # 비중 및 리밸런싱/배당 분석
    annual_div_krw_total = 0.0
    monthly_div_chart = [0.0] * 12

    for item in assets:
        val_krw = item["eval_value_krw"]
        weight = round((val_krw / total_val_krw * 100), 2) if total_val_krw > 0 else 0.0
        item["weight_pct"] = weight

        target_w = item.get("target_weight") or 0.0
        diff_w = round(weight - target_w, 2)
        target_val_krw = total_val_krw * (target_w / 100.0)
        rebalance_amount_krw = round(target_val_krw - val_krw, 0)

        item["diff_weight_pct"] = diff_w
        item["rebalance_amount_krw"] = rebalance_amount_krw
        if abs(diff_w) <= 1.5:
            item["status"] = "유지 (목표 부합)"
            item["status_color"] = "text-emerald-400"
        elif diff_w < -1.5:
            item["status"] = "부족 (추가 매수)"
            item["status_color"] = "text-amber-400"
        else:
            item["status"] = "초과 (비중 과다)"
            item["status_color"] = "text-blue-400"

        dy = item.get("dividend_yield") or 0.0
        freq = item.get("div_frequency") or "QUARTERLY"
        annual_div_asset_krw = val_krw * (dy / 100.0)
        annual_div_krw_total += annual_div_asset_krw

        if asset_type in ["CASH_KRW", "USD_RP"] or freq == "MONTHLY":
            m_amt = annual_div_asset_krw / 12.0
            for m in range(12): monthly_div_chart[m] += m_amt
        elif freq == "QUARTERLY":
            q_amt = annual_div_asset_krw / 4.0
            for m in [2, 5, 8, 11]: monthly_div_chart[m] += q_amt
        elif freq == "YEARLY":
            monthly_div_chart[11] += annual_div_asset_krw

    monthly_div_chart = [round(amt, 0) for amt in monthly_div_chart]

    return {
        "rate": usd_krw_rate,
        "total_value_krw": round(total_val_krw, 0),
        "total_value_usd": round(total_val_usd, 2),
        "total_invested_krw": round(total_invested_krw, 0),
        "total_pnl_krw": round(total_pnl_krw, 0),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "krw_assets_krw": round(krw_assets_val, 0),
        "usd_assets_usd": round(usd_assets_val_in_usd, 2),
        "usd_rp_val_usd": round(usd_rp_val_in_usd, 2),
        "rp_daily_interest_total_usd": round(rp_daily_interest_total_usd, 4),
        "rp_daily_interest_total_krw": round(rp_daily_interest_total_usd * usd_krw_rate, 1),
        "annual_div_krw_total": round(annual_div_krw_total, 0),
        "monthly_div_chart": monthly_div_chart,
        "assets": assets
    }

@app.get("/api/history")
def get_portfolio_history():
    """계좌 총 자산 변화 추이 그래프 데이터"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT record_date, total_val_krw, total_invested_krw FROM portfolio_history ORDER BY record_date ASC")
    rows = c.fetchall()
    conn.close()

    history = [dict(r) for r in rows]
    return {"history": history}

@app.post("/api/asset")
def add_or_update_asset(data: dict):
    conn = get_connection()
    c = conn.cursor()
    symbol = data.get("symbol", "").strip()
    name = data.get("name", "").strip()
    asset_type = data.get("asset_type", "KR_ETF")
    currency = data.get("currency", "KRW")
    quantity = float(data.get("quantity", 0))
    avg_price = float(data.get("avg_price", 0))
    current_price = float(data.get("current_price", 0)) or avg_price
    target_weight = float(data.get("target_weight", 0))
    dividend_yield = float(data.get("dividend_yield", 0))
    div_frequency = data.get("div_frequency", "QUARTERLY")
    account = data.get("account", "ISA").strip()

    c.execute("""
        INSERT INTO assets (symbol, name, asset_type, currency, quantity, avg_price, current_price, target_weight, dividend_yield, div_frequency, account, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(symbol, account) DO UPDATE SET
            name=excluded.name,
            asset_type=excluded.asset_type,
            currency=excluded.currency,
            quantity=excluded.quantity,
            avg_price=excluded.avg_price,
            current_price=excluded.current_price,
            target_weight=excluded.target_weight,
            dividend_yield=excluded.dividend_yield,
            div_frequency=excluded.div_frequency,
            updated_at=CURRENT_TIMESTAMP
    """, (symbol, name, asset_type, currency, quantity, avg_price, current_price, target_weight, dividend_yield, div_frequency, account))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/rp-interest-rate")
def update_rp_rate(data: dict):
    """외화 RP 약정 이율 원클릭 변경"""
    rate = float(data.get("rate", 3.35))
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE assets SET dividend_yield = ? WHERE symbol = 'USD_RP'", (rate,))
    conn.commit()
    conn.close()
    return {"status": "success", "new_rate": rate}

@app.post("/api/cma-interest-rate")
def update_cma_rate(data: dict):
    """발행어음 CMA 약정 이율 원클릭 변경"""
    rate = float(data.get("rate", 2.60))
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE assets SET dividend_yield = ? WHERE account = 'CMA' AND (symbol = 'CASH_KRW' OR asset_type = 'CASH_KRW')", (rate,))
    conn.commit()
    conn.close()
    return {"status": "success", "new_rate": rate}

@app.post("/api/target-weights")
def update_target_weights(data: Any = Body(...)):
    if isinstance(data, list):
        targets = data
    elif isinstance(data, dict):
        targets = data.get("targets", [])
    else:
        targets = []

    conn = get_connection()
    c = conn.cursor()
    for t in targets:
        tw = float(t.get("target_weight", 0))
        target_id = t.get("id")
        try:
            tid = int(target_id) if target_id else 0
        except (ValueError, TypeError):
            tid = 0

        if tid > 0:
            c.execute("UPDATE assets SET target_weight = ? WHERE id = ?", (tw, tid))
        elif t.get("account"):
            c.execute("UPDATE assets SET target_weight = ? WHERE symbol = ? AND account = ?", (tw, t["symbol"], t["account"]))
        else:
            c.execute("UPDATE assets SET target_weight = ? WHERE symbol = ?", (tw, t["symbol"]))
    conn.commit()
    conn.close()
    return {"status": "success", "updated_count": len(targets)}

@app.delete("/api/asset/{identifier}")
def delete_asset(identifier: str, account: str = None):
    conn = get_connection()
    c = conn.cursor()
    if identifier.isdigit():
        c.execute("DELETE FROM assets WHERE id = ?", (int(identifier),))
    elif account:
        c.execute("DELETE FROM assets WHERE symbol = ? AND account = ?", (identifier, account))
    else:
        c.execute("DELETE FROM assets WHERE symbol = ?", (identifier,))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/refresh-prices")
def refresh_prices():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, symbol, asset_type FROM assets")
    rows = c.fetchall()
    
    rate = market_data.get_usd_krw_rate()
    updated = []
    for r in rows:
        sym = r["symbol"]
        atype = r["asset_type"]
        new_price = market_data.get_current_price(sym, atype)
        if new_price > 0:
            c.execute("UPDATE assets SET current_price = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_price, r["id"]))
            updated.append({"symbol": sym, "price": new_price})
    
    conn.commit()
    conn.close()
    return {"status": "success", "rate": rate, "updated": updated}

@app.get("/api/lookup-ticker/{symbol}")
def lookup_ticker(symbol: str):
    """티커 입력 시 실시간 종목 정보(이름, 단가, 배당률 등) 자동 조회"""
    return market_data.lookup_ticker_info(symbol)

@app.get("/api/chart/{symbol}")
def get_chart_data(symbol: str, asset_type: str = "KR_ETF", period: str = "6mo"):
    candles = market_data.get_historical_candles(symbol, asset_type, period=period)
    return {"symbol": symbol, "candles": candles}

@app.post("/api/parse-image")
async def parse_image(file: UploadFile = File(...), api_key: str = Form(None)):
    contents = await file.read()
    mime = file.content_type or "image/jpeg"
    result = parser.parse_portfolio_image(contents, mime, api_key=api_key)
    return result

@app.post("/api/parse-text")
def parse_text(data: dict):
    raw_text = data.get("text", "")
    api_key = data.get("api_key", None)
    result = parser.parse_trade_text(raw_text, api_key=api_key)
    return result

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
