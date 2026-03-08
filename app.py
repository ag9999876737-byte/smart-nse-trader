import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from st_aggrid import AgGrid, GridOptionsBuilder
from datetime import datetime, timedelta
import concurrent.futures

# --------------------------
# PAGE CONFIG
# --------------------------
st.set_page_config(page_title="Smart NSE Scanner", layout="wide")
st.title("📈 Smart NSE Swing Scanner (Top 250 Universe)")
st.write("Momentum-based ranking engine with risk management")

# --------------------------
# TOP 250 STATIC LIST
# --------------------------
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

symbols = list(set(TOP_250))  # Remove duplicates

# --------------------------
# CACHED STOCK DOWNLOAD
# --------------------------
@st.cache_data(ttl=1800)
def download_batch(symbols, period="6mo", interval="1d"):
    try:
        df = yf.download(
            tickers=symbols,
            period=period,
            interval=interval,
            group_by='ticker',
            progress=False
        )
        return df
    except Exception as e:
        st.error(f"Batch download failed: {e}")
        return None

# --------------------------
# MARKET REGIME CHECK
# --------------------------
@st.cache_data(ttl=3600)
def get_market_regime():
    df = yf.download("^NSEI", period="3mo", interval="1d", progress=False)
    if df is None or df.empty or "Close" not in df.columns:
        return "Unknown"
    df["EMA50"] = df["Close"].ewm(span=50).mean()
    close = df["Close"].iloc[-1]
    ema50 = df["EMA50"].iloc[-1]
    return "Bullish" if close > ema50 else "Weak"

market_regime = get_market_regime()
if market_regime == "Weak":
    st.warning("⚠ Market Trend Weak — Trades carry higher risk")
elif market_regime == "Bullish":
    st.success("✅ Market Trend Bullish")
else:
    st.info("Market Regime Unknown")

# --------------------------
# SIDEBAR WEIGHTS
# --------------------------
st.sidebar.header("Scoring Weights")
trend_weight = st.sidebar.slider("Trend Weight", 0, 50, 40)
breakout_weight = st.sidebar.slider("Breakout Weight", 0, 30, 20)
volume_weight = st.sidebar.slider("Volume Weight", 0, 20, 15)
rs_weight = st.sidebar.slider("Relative Strength Weight", 0, 20, 15)

# --------------------------
# ANALYSIS FUNCTION
# --------------------------
def analyze_stock(symbol, nifty_return, data):

    try:
        if len(data) < 60 or "Close" not in data.columns:
            return None

        df = data.copy()
        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()
        df["EMA20_weekly"] = df["Close"].resample("W").last().ewm(span=20).mean()
        df["EMA50_weekly"] = df["Close"].resample("W").last().ewm(span=50).mean()

        df["TR"] = np.maximum(
            df["High"] - df["Low"],
            np.maximum(
                abs(df["High"] - df["Close"].shift()),
                abs(df["Low"] - df["Close"].shift())
            )
        )
        df["ATR14"] = df["TR"].rolling(14).mean()
        latest = df.iloc[-1]

        price = float(latest["Close"])
        ema20 = float(latest["EMA20"])
        ema50 = float(latest["EMA50"])
        atr = float(latest["ATR14"])

        score = 0
        warning = ""

        # Trend
        if price > ema20 and price > ema50:
            score += trend_weight
        else:
            warning = "Below EMA50"

        # Breakout
        breakout_level = float(df["High"].rolling(30).max().iloc[-2])
        if price > breakout_level:
            score += breakout_weight

        # Volume Spike
        avg_vol = float(df["Volume"].rolling(20).mean().iloc[-1])
        if float(latest["Volume"]) > 1.3 * avg_vol:
            score += volume_weight

        # Relative Strength vs Nifty
        stock_return = (price / float(df["Close"].iloc[-20])) - 1
        if stock_return > nifty_return:
            score += rs_weight

        # Stop Loss / Target
        stop_loss = price - (1.5 * atr)
        target = price + (2 * atr)
        rr_ratio = round((target - price) / (price - stop_loss), 2)

        # Rating
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
            "Target": round(target, 2),
            "RR Ratio": rr_ratio
        }

    except Exception as e:
        return None

# --------------------------
# SCAN BUTTON
# --------------------------
if st.button("🔍 Scan Market"):

    st.write("Scanning stocks... Please wait ⏳")

    # Batch download all stock data
    data = download_batch(symbols)
    if data is None:
        st.error("Failed to download stock data.")
    else:
        # Precompute Nifty return
        nifty_df = yf.download("^NSEI", period="2mo", interval="1d", progress=False)
        nifty_return = 0
        if nifty_df is not None and len(nifty_df) > 30:
            latest = float(nifty_df["Close"].iloc[-1])
            past = float(nifty_df["Close"].iloc[-20])
            nifty_return = (latest / past) - 1

        results = []

        with st.spinner("Analyzing stocks..."):
            # Use ThreadPool for faster analysis
            def process_stock(symbol):
                if symbol in data.columns.levels[0]:  # MultiTicker
                    stock_data = data[symbol]
                else:
                    stock_data = data[symbol]
                return analyze_stock(symbol, nifty_return, stock_data)

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                future_to_symbol = {executor.submit(process_stock, sym): sym for sym in symbols}
                for future in concurrent.futures.as_completed(future_to_symbol):
                    res = future.result()
                    if res:
                        results.append(res)

        if results:
            df_results = pd.DataFrame(results)
            df_results = df_results.sort_values(by="Score", ascending=False)
            st.success("Top Opportunities (Sorted by Score)")

            # Display using AgGrid
            gb = GridOptionsBuilder.from_dataframe(df_results.head(50))
            gb.configure_pagination(paginationAutoPageSize=True)
            gb.configure_default_column(editable=False, groupable=True)
            gb.configure_column("Rating", cellStyle=lambda x: {'color': 'red'} if '🔥' in x else {'color': 'green'})
            AgGrid(df_results.head(50), gridOptions=gb.build(), height=400)

        else:
            st.info("No valid setups found.")
