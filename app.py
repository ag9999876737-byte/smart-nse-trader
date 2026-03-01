import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Smart Swing Scanner Pro", layout="wide")

st.title("📈 Indian Market Smart Swing Scanner (Top 100)")
st.write("Momentum Ranking Engine – Scans Top 100 NSE Stocks")

# -----------------------------------
# Market Regime (Info Only)
# -----------------------------------
def get_market_regime():
    nifty = yf.download("^NSEI", period="3mo", interval="1d", progress=False)
    if nifty.empty or len(nifty) < 50:
        return "Unknown"

    nifty["EMA50"] = nifty["Close"].ewm(span=50).mean()
    if nifty["Close"].iloc[-1] > nifty["EMA50"].iloc[-1]:
        return "Bullish"
    else:
        return "Weak"

market_regime = get_market_regime()
st.info(f"Market Regime: {market_regime}")

# -----------------------------------
# Top 100 NSE Stocks (Nifty 50 + Next 50)
# -----------------------------------
top_100_stocks = [
    # Nifty 50
    "RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
    "LT.NS","SBIN.NS","AXISBANK.NS","MARUTI.NS","BAJFINANCE.NS",
    "ITC.NS","SUNPHARMA.NS","TITAN.NS","ULTRACEMCO.NS","NTPC.NS",
    "POWERGRID.NS","ADANIENT.NS","ADANIPORTS.NS","HCLTECH.NS","WIPRO.NS",
    "ONGC.NS","COALINDIA.NS","JSWSTEEL.NS","HINDALCO.NS","TATASTEEL.NS",
    "BHARTIARTL.NS","NESTLEIND.NS","ASIANPAINT.NS","HINDUNILVR.NS",
    "BAJAJFINSV.NS","BAJAJ-AUTO.NS","DIVISLAB.NS","DRREDDY.NS",
    "BRITANNIA.NS","HEROMOTOCO.NS","INDUSINDBK.NS","EICHERMOT.NS",
    "GRASIM.NS","TECHM.NS","UPL.NS","CIPLA.NS","APOLLOHOSP.NS",
    "TATAMOTORS.NS","SHREECEM.NS","SBILIFE.NS","HDFCLIFE.NS",
    "BPCL.NS","IOC.NS","M&M.NS",

    # Nifty Next 50 (Representative Large Caps)
    "ADANIGREEN.NS","ADANIPOWER.NS","AMBUJACEM.NS","BANKBARODA.NS",
    "BERGEPAINT.NS","BOSCHLTD.NS","CHOLAFIN.NS","DABUR.NS",
    "DLF.NS","GAIL.NS","GODREJCP.NS","HAVELLS.NS","ICICIGI.NS",
    "ICICIPRULI.NS","IDBI.NS","INDIGO.NS","JINDALSTEL.NS",
    "LICHSGFIN.NS","LODHA.NS","LUPIN.NS","MARICO.NS",
    "MUTHOOTFIN.NS","NAUKRI.NS","PEL.NS","PIDILITIND.NS",
    "PNB.NS","RECLTD.NS","SAIL.NS","SIEMENS.NS",
    "SRF.NS","TATACOMM.NS","TORNTPHARM.NS","TVSMOTOR.NS",
    "UNITDSPR.NS","VEDL.NS","VOLTAS.NS","ZEEL.NS",
    "ZOMATO.NS","NYKAA.NS","IRCTC.NS","PFC.NS",
    "ABB.NS","BHEL.NS","CANBK.NS","COLPAL.NS",
    "CONCOR.NS","HAL.NS","NMDC.NS","POLYCAB.NS"
]

# -----------------------------------
# Stock Scoring Logic
# -----------------------------------
def analyze_stock(symbol):

    try:
        df = yf.download(symbol, period="6mo", interval="1d", progress=False)

        if df.empty or len(df) < 60:
            return None

        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()

        df["TR"] = np.maximum(
            df["High"] - df["Low"],
            np.maximum(
                abs(df["High"] - df["Close"].shift()),
                abs(df["Low"] - df["Close"].shift())
            )
        )

        df["ATR14"] = df["TR"].rolling(14).mean()
        latest = df.iloc[-1]

        price = latest["Close"]
        ema20 = latest["EMA20"]
        ema50 = latest["EMA50"]

        score = 0

        if price > ema20:
            score += 20
        if price > ema50:
            score += 20

        breakout_level = df["High"].rolling(30).max().iloc[-2]
        if price > breakout_level:
            score += 20

        avg_vol = df["Volume"].rolling(20).mean().iloc[-1]
        if latest["Volume"] > 1.3 * avg_vol:
            score += 15

        nifty = yf.download("^NSEI", period="2mo", interval="1d", progress=False)
        if not nifty.empty and len(nifty) > 30:
            stock_return = (price / df["Close"].iloc[-20]) - 1
            nifty_return = (nifty["Close"].iloc[-1] / nifty["Close"].iloc[-20]) - 1
            if stock_return > nifty_return:
                score += 15

        atr = latest["ATR14"]
        stop_loss = price - 1.5 * atr
        target = price + 2 * atr

        if score >= 70:
            rating = "🔥 Strong Buy"
        elif score >= 55:
            rating = "✅ Buy"
        elif score >= 40:
            rating = "👀 Watch"
        else:
            rating = "Avoid"

        return {
            "Symbol": symbol,
            "Price": round(price, 2),
            "Score": score,
            "Rating": rating,
            "Market Regime": market_regime,
            "Stop Loss": round(stop_loss, 2),
            "Target": round(target, 2)
        }

    except:
        return None

# -----------------------------------
# Scan Button
# -----------------------------------
if st.button("🔍 Scan Top 100 Stocks"):

    results = []
    progress = st.progress(0)
    total = len(top_100_stocks)

    for i, stock in enumerate(top_100_stocks):
        res = analyze_stock(stock)
        if res:
            results.append(res)
        progress.progress((i + 1) / total)

    if results:
        df_results = pd.DataFrame(results)
        df_results = df_results.sort_values(by="Score", ascending=False)
        st.success("Top Ranked Opportunities")
        st.dataframe(df_results.head(15))
    else:
        st.info("No data available.")
