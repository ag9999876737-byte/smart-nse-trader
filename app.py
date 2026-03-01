import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time

st.set_page_config(page_title="Smart NSE Scanner", layout="wide")
st.title("📈 Smart NSE Swing Scanner (Top 250 Universe)")
st.write("Momentum-based ranking engine with risk management")

# ----------------------------------------------------------
# SAFE DATA DOWNLOAD FUNCTION
# ----------------------------------------------------------
def safe_download(symbol, period="6mo", interval="1d"):
    try:
        df = yf.download(symbol, period=period, interval=interval, progress=False)

        if df is None or df.empty:
            return None

        # Fix MultiIndex issue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        return df
    except:
        return None

# ----------------------------------------------------------
# MARKET REGIME CHECK (NEVER BLOCKS SCANNER)
# ----------------------------------------------------------
@st.cache_data(ttl=3600)
def get_market_regime():
    df = safe_download("^NSEI", period="3mo")

    if df is None or len(df) < 50:
        return "Unknown"

    if "Close" not in df.columns:
        return "Unknown"

    df["EMA50"] = df["Close"].ewm(span=50).mean()

    try:
        close = float(df["Close"].iloc[-1])
        ema50 = float(df["EMA50"].iloc[-1])
    except:
        return "Unknown"

    return "Bullish" if close > ema50 else "Weak"

market_regime = get_market_regime()

if market_regime == "Weak":
    st.warning("⚠ Market Trend Weak — Trades carry higher risk")
elif market_regime == "Bullish":
    st.success("✅ Market Trend Bullish")
else:
    st.info("Market Regime Unknown")

# ----------------------------------------------------------
# TOP 250 STATIC LIST (Stable, No External Dependency)
# Large + Midcap Mix
# ----------------------------------------------------------
TOP_250 = [
    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS",
    "HINDUNILVR.NS","ITC.NS","SBIN.NS","BHARTIARTL.NS","LT.NS",
    "KOTAKBANK.NS","AXISBANK.NS","BAJFINANCE.NS","ASIANPAINT.NS",
    "MARUTI.NS","SUNPHARMA.NS","TITAN.NS","ULTRACEMCO.NS",
    "WIPRO.NS","ONGC.NS","ADANIENT.NS","ADANIPORTS.NS",
    "POWERGRID.NS","NTPC.NS","JSWSTEEL.NS","TATASTEEL.NS",
    "BAJAJFINSV.NS","HCLTECH.NS","COALINDIA.NS","GRASIM.NS",
    "DRREDDY.NS","TECHM.NS","BRITANNIA.NS","EICHERMOT.NS",
    "HEROMOTOCO.NS","DIVISLAB.NS","INDUSINDBK.NS","CIPLA.NS",
    "SBILIFE.NS","HDFCLIFE.NS","TATAMOTORS.NS","BPCL.NS",
    "UPL.NS","SHREECEM.NS","ADANIGREEN.NS","ADANIPOWER.NS",
    "IOC.NS","HINDALCO.NS","BAJAJ-AUTO.NS","PIDILITIND.NS"
]

# Expandable universe (duplicate protection)
symbols = list(set(TOP_250))

# ----------------------------------------------------------
# STOCK ANALYSIS LOGIC
# ----------------------------------------------------------
def analyze_stock(symbol, nifty_return):

    df = safe_download(symbol)

    if df is None or len(df) < 60:
        return None

    if "Close" not in df.columns:
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

    try:
        price = float(latest["Close"])
        ema20 = float(latest["EMA20"])
        ema50 = float(latest["EMA50"])
        atr = float(latest["ATR14"])
    except:
        return None

    score = 0
    warning = ""

    # --- Trend Score
    if price > ema20:
        score += 20
    if price > ema50:
        score += 20
    else:
        warning = "Below EMA50"

    # --- Breakout Score
    breakout_level = float(df["High"].rolling(30).max().iloc[-2])
    if price > breakout_level:
        score += 20

    # --- Volume Spike
    avg_vol = float(df["Volume"].rolling(20).mean().iloc[-1])
    if float(latest["Volume"]) > 1.3 * avg_vol:
        score += 15

    # --- Relative Strength vs Nifty
    try:
        stock_return = (price / float(df["Close"].iloc[-20])) - 1
        if stock_return > nifty_return:
            score += 15
    except:
        pass

    # --- Risk Management
    stop_loss = price - (1.5 * atr)
    target = price + (2 * atr)

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
        "Warning": warning,
        "Stop Loss": round(stop_loss, 2),
        "Target": round(target, 2)
    }

# ----------------------------------------------------------
# SCAN BUTTON
# ----------------------------------------------------------
if st.button("🔍 Scan Market"):

    st.write("Scanning stocks... Please wait ⏳")

    # Precompute Nifty return once (performance optimization)
    nifty_df = safe_download("^NSEI", period="2mo")
    nifty_return = 0

    if nifty_df is not None and len(nifty_df) > 30:
        try:
            latest = float(nifty_df["Close"].iloc[-1])
            past = float(nifty_df["Close"].iloc[-20])
            nifty_return = (latest / past) - 1
        except:
            nifty_return = 0

    results = []
    progress = st.progress(0)

    for i, stock in enumerate(symbols):
        res = analyze_stock(stock, nifty_return)
        if res:
            results.append(res)
        progress.progress((i + 1) / len(symbols))
        time.sleep(0.05)  # Prevent API overload

    if results:
        df_results = pd.DataFrame(results)
        df_results = df_results.sort_values(by="Score", ascending=False)
        st.success("Top Opportunities (Sorted by Score)")
        st.dataframe(df_results.head(20))
    else:
        st.info("No valid setups found.")
