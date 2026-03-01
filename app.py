import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Smart Swing Scanner Pro", layout="wide")

st.title("📈 Indian Market Smart Swing Scanner (Pro Version)")
st.write("Breakout + Relative Strength + Volatility Contraction Strategy")

# -------------------------------
# Market Trend Check (No Stop)
# -------------------------------
def market_trend():
    nifty = yf.download("^NSEI", period="3mo", interval="1d", progress=False)
    if nifty.empty or len(nifty) < 50:
        return True
    nifty["EMA50"] = nifty["Close"].ewm(span=50).mean()
    return nifty["Close"].iloc[-1] > nifty["EMA50"].iloc[-1]

if market_trend() is False:
    st.warning("⚠ Market trend is weak (NIFTY below 50 EMA). Trade cautiously.")

# -------------------------------
# NSE STOCK LIST (Expandable)
# -------------------------------
nse_stocks = [
    "RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
    "LT.NS","SBIN.NS","AXISBANK.NS","MARUTI.NS","BAJFINANCE.NS",
    "ITC.NS","SUNPHARMA.NS","TITAN.NS","ULTRACEMCO.NS",
    "NTPC.NS","POWERGRID.NS","ADANIENT.NS","ADANIPORTS.NS",
    "HCLTECH.NS","WIPRO.NS","ONGC.NS","COALINDIA.NS"
]

# -------------------------------
# Stock Analysis Logic
# -------------------------------
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
        df["ATR5"] = df["TR"].rolling(5).mean()
        df["ATR20"] = df["TR"].rolling(20).mean()

        latest = df.iloc[-1]

        price = latest["Close"]
        ema20 = latest["EMA20"]
        ema50 = latest["EMA50"]

        score = 0

        # Trend Filters
        if price > ema20:
            score += 20
        if price > ema50:
            score += 20

        # 30-Day Breakout
        breakout_level = df["High"].rolling(30).max().iloc[-2]
        breakout = price > breakout_level
        if breakout:
            score += 25

        # Volume Confirmation
        avg_vol = df["Volume"].rolling(20).mean().iloc[-1]
        if latest["Volume"] > 1.5 * avg_vol:
            score += 15

        # Relative Strength vs NIFTY
        nifty = yf.download("^NSEI", period="2mo", interval="1d", progress=False)
        if not nifty.empty and len(nifty) > 30:
            stock_return = (price / df["Close"].iloc[-20]) - 1
            nifty_return = (nifty["Close"].iloc[-1] / nifty["Close"].iloc[-20]) - 1

            if stock_return > nifty_return:
                score += 20

        # Not Overextended (within 8% of EMA20)
        distance_from_ema20 = (price - ema20) / ema20
        if distance_from_ema20 > 0.08:
            return None

        # Volatility Contraction
        if latest["ATR5"] >= latest["ATR20"]:
            return None

        # Strong Close
        candle_range = latest["High"] - latest["Low"]
        if candle_range > 0:
            close_position = (price - latest["Low"]) / candle_range
            if close_position < 0.7:
                return None

        if score < 60:
            return None

        atr = latest["ATR14"]
        stop_loss = price - 1.5 * atr
        target = price + 2 * atr

        return {
            "Symbol": symbol,
            "Price": round(price, 2),
            "Score": score,
            "Stop Loss": round(stop_loss, 2),
            "Target": round(target, 2)
        }

    except:
        return None

# -------------------------------
# Scan Button
# -------------------------------
if st.button("🔍 Scan Market"):

    results = []

    progress = st.progress(0)
    total = len(nse_stocks)

    for i, stock in enumerate(nse_stocks):
        res = analyze_stock(stock)
        if res:
            results.append(res)
        progress.progress((i + 1) / total)

    if results:
        df_results = pd.DataFrame(results)
        df_results = df_results.sort_values(by="Score", ascending=False)
        st.success("High Probability Setups Found")
        st.dataframe(df_results)
    else:
        st.info("No strong setups found today.")
