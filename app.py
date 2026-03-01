import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="Smart Swing Scanner", layout="wide")
st.title("🚀 Smart Swing Trading Scanner")

st.markdown("Scans NSE stocks for breakout swing opportunities.")

# -------------------------------
# Get NSE Stock List
# -------------------------------
@st.cache_data(ttl=3600)
def get_nse_stocks():
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    df = pd.read_csv(url)
    return df['SYMBOL'].tolist()

# -------------------------------
# Check Market Regime
# -------------------------------
def market_trend():
    try:
        nifty = yf.download("^NSEI", period="3mo", progress=False)

        if nifty.empty or len(nifty) < 50:
            return True  # If data fails, allow scan instead of crash

        nifty['EMA50'] = nifty['Close'].ewm(span=50).mean()

        return nifty['Close'].iloc[-1] > nifty['EMA50'].iloc[-1]

    except:
        return True  # Fail safe: don't block scan

# -------------------------------
# Analyze Stock
# -------------------------------
def analyze_stock(symbol, nifty_data):

    try:
        data = yf.download(symbol + ".NS", period="3mo", progress=False)

        if len(data) < 50:
            return None

        close = data['Close']
        high = data['High']
        low = data['Low']
        volume = data['Volume']

        current_price = close.iloc[-1]

        if current_price < 50:
            return None

        # EMAs
        ema20 = close.ewm(span=20).mean().iloc[-1]
        ema50 = close.ewm(span=50).mean().iloc[-1]

        # Breakout logic
        breakout_level = high.rolling(20).max().iloc[-2]
        breakout = current_price > breakout_level

        # Volume confirmation
        avg_vol = volume.rolling(20).mean().iloc[-1]
        vol_confirm = volume.iloc[-1] > 1.5 * avg_vol

        # Relative strength vs NIFTY
        stock_return = (current_price / close.iloc[-20]) - 1
        nifty_return = (nifty_data['Close'].iloc[-1] / nifty_data['Close'].iloc[-20]) - 1
        relative_strength = stock_return > nifty_return

        # ATR for stop loss
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]

        stop_loss = current_price - (1.5 * atr)
        target = current_price + (2 * atr)

        # Scoring
        score = 0

        if current_price > ema20:
            score += 20
        if current_price > ema50:
            score += 20
        if breakout:
            score += 25
        if vol_confirm:
            score += 15
        if relative_strength:
            score += 20

        if score < 60:
            return None

        return {
            "Stock": symbol,
            "Price": round(current_price, 2),
            "Score": score,
            "Target": round(target, 2),
            "Stop Loss": round(stop_loss, 2)
        }

    except:
        return None


# -------------------------------
# Main App Logic
# -------------------------------

if st.button("🔎 Scan Market for Swing Setups"):

    if not market_trend() is False:
        st.warning("Market trend is weak (NIFTY below 50 EMA). Avoid aggressive buying.")
        st.stop()

    st.success("Market trend is positive. Scanning for opportunities...")

    stocks = get_nse_stocks()
    nifty_data = yf.download("^NSEI", period="3mo", progress=False)

    results = []

    with st.spinner("Scanning top liquid stocks..."):
        for stock in stocks[:400]:   # Limit for stability
            result = analyze_stock(stock, nifty_data)
            if result:
                results.append(result)

    if results:
        df = pd.DataFrame(results).sort_values("Score", ascending=False)

        st.subheader("🏆 Top Swing Opportunities")

        for _, row in df.head(5).iterrows():
            st.markdown(f"""
            ### {row['Stock']} — Score {row['Score']}/100
            💰 Price: ₹{row['Price']}  
            🎯 Target: ₹{row['Target']}  
            🛑 Stop Loss: ₹{row['Stop Loss']}  
            ---
            """)

        st.subheader("📊 Full Ranked List")
        st.dataframe(df, use_container_width=True)

    else:
        st.warning("No strong swing setups found today.")

st.markdown("---")
st.caption("Educational tool. Not financial advice.")
