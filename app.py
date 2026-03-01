import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests

st.set_page_config(page_title="Smart NSE Market Scanner", layout="wide")
st.title("🚀 Smart NSE Full Market Scanner")

st.markdown("Scans liquid NSE stocks and ranks best opportunities.")

# Get NSE stock list
@st.cache_data(ttl=3600)
def get_nse_stocks():
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    df = pd.read_csv(url)
    return df['SYMBOL'].tolist()

# Analyze stock
def analyze(symbol):
    try:
        ticker = yf.Ticker(symbol + ".NS")
        hist = ticker.history(period="3mo")

        if len(hist) < 50:
            return None

        close = hist['Close']
        current = close.iloc[-1]

        ema20 = close.ewm(span=20).mean().iloc[-1]
        ema50 = close.ewm(span=50).mean().iloc[-1]

        volume_avg = hist['Volume'].rolling(20).mean().iloc[-1]
        volume_now = hist['Volume'].iloc[-1]

        if volume_now < 500000:
            return None

        score = 0

        if current > ema20:
            score += 30
        if current > ema50:
            score += 30
        if volume_now > 1.5 * volume_avg:
            score += 20

        momentum = (current / close.iloc[-20] - 1) * 100
        if momentum > 5:
            score += 20

        support = hist['Low'].rolling(20).min().iloc[-1]
        resistance = hist['High'].rolling(20).max().iloc[-1]

        return {
            "Stock": symbol,
            "Price": round(current, 2),
            "Score": score,
            "Momentum %": round(momentum, 2),
            "Target": round(resistance, 2),
            "Stop Loss": round(support * 0.97, 2)
        }

    except:
        return None


if st.button("🔎 Scan Entire Market (Liquid Stocks Only)"):

    with st.spinner("Fetching NSE stock list..."):
        stocks = get_nse_stocks()

    results = []

    with st.spinner("Scanning market... This may take 1–2 minutes..."):
        for i, stock in enumerate(stocks[:400]):  # Limit to 400 for stability
            data = analyze(stock)
            if data and data["Score"] >= 60:
                results.append(data)

    if results:
        df = pd.DataFrame(results).sort_values("Score", ascending=False)

        st.subheader("🏆 Top Market Opportunities")
        for _, row in df.head(5).iterrows():
            st.markdown(f"""
            ### {row['Stock']} — Score {row['Score']}/100
            💰 Price: ₹{row['Price']}  
            📈 Momentum: {row['Momentum %']}%  
            🎯 Target: ₹{row['Target']}  
            🛑 Stop Loss: ₹{row['Stop Loss']}  
            ---
            """)

        st.subheader("📊 Full Ranked List")
        st.dataframe(df, use_container_width=True)

    else:
        st.warning("No strong opportunities found today.")

st.markdown("---")
st.caption("Scans liquid NSE stocks only. Educational tool. Not financial advice.")
