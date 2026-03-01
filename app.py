import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Smart Swing Scanner - Top 250", layout="wide")

st.title("📈 Indian Market Smart Swing Scanner (Top 250)")
st.write("Momentum Ranking Engine – Large + Midcap Universe")

# -----------------------------------
# MARKET REGIME
# -----------------------------------
@st.cache_data
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
# STATIC TOP 250 NSE STOCK LIST
# -----------------------------------

# Instead of external CSV, use yfinance NSE ticker universe filter
@st.cache_data
def get_nse_top_250():
    url = "https://archives.nseindia.com/content/indices/ind_nifty250list.csv"
    try:
        df = pd.read_csv(url)
        symbols = df["Symbol"].tolist()
        return [s + ".NS" for s in symbols]
    except:
        return []

symbols = get_nse_top_250()

if not symbols:
    st.error("Unable to load Nifty 250 list. Try again later.")
    st.stop()

# -----------------------------------
# STOCK SCORING
# -----------------------------------
@st.cache_data(show_spinner=False)
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
# SCAN BUTTON
# -----------------------------------
if st.button("🔍 Scan Nifty 250"):

    results = []
    progress = st.progress(0)
    total = len(symbols)

    for i, stock in enumerate(symbols):
        res = analyze_stock(stock)
        if res:
            results.append(res)
        progress.progress((i + 1) / total)

    if results:
        df_results = pd.DataFrame(results)
        df_results = df_results.sort_values(by="Score", ascending=False)
        st.success("Top Ranked Opportunities (Top 20 Shown)")
        st.dataframe(df_results.head(20))
    else:
        st.info("No valid setups found.")
