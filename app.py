import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from st_aggrid import AgGrid, GridOptionsBuilder
import concurrent.futures

# --------------------------
# PAGE CONFIG
# --------------------------
st.set_page_config(page_title="Smart NSE Scanner + Portfolio", layout="wide")
st.title("📈 Smart NSE Swing Scanner (Top 250 + Portfolio)")
st.write("Momentum-based ranking engine with risk management and portfolio insights")

# --------------------------
# TOP 250 NSE STOCKS
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

symbols = list(set(TOP_250))

# --------------------------
# SCORING WEIGHTS
# --------------------------
WEIGHTS = {
    "trend": 40,
    "breakout": 20,
    "volume": 15,
    "relative_strength": 15
}

# --------------------------
# CACHED DOWNLOAD
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
    except:
        return None

# --------------------------
# MARKET REGIME
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
# ANALYSIS FUNCTION
# --------------------------
def analyze_stock(symbol, nifty_return, data):
    try:
        if len(data) < 60 or "Close" not in data.columns:
            return None
        df = data.copy()
        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()
        df["TR"] = np.maximum(
            df["High"] - df["Low"],
            np.maximum(abs(df["High"] - df["Close"].shift()), abs(df["Low"] - df["Close"].shift()))
        )
        df["ATR14"] = df["TR"].rolling(14).mean()
        latest = df.iloc[-1]
        price = float(latest["Close"])
        atr = float(latest["ATR14"])
        score = 0
        warning = ""
        # Trend
        if price > float(latest["EMA20"]) and price > float(latest["EMA50"]):
            score += WEIGHTS["trend"]
        else:
            warning = "Below EMA50"
        # Breakout
        breakout_level = float(df["High"].rolling(30).max().iloc[-2])
        if price > breakout_level:
            score += WEIGHTS["breakout"]
        # Volume
        avg_vol = float(df["Volume"].rolling(20).mean().iloc[-1])
        if float(latest["Volume"]) > 1.3 * avg_vol:
            score += WEIGHTS["volume"]
        # Relative strength
        stock_return = (price / float(df["Close"].iloc[-20])) - 1
        if stock_return > nifty_return:
            score += WEIGHTS["relative_strength"]
        # Stop Loss / Target
        stop_loss = price - (1.5 * atr)
        target = price + (2 * atr)
        rr_ratio = round((target - price) / (price - stop_loss),2)
        # Rating
        if score >= 70:
            rating = "🔥 Strong Buy"
        elif score >=55:
            rating = "✅ Buy"
        elif score >=40:
            rating = "👀 Watch"
        else:
            rating = "Avoid"
        # Sell Hint
        sell_hint = ""
        if price < float(latest["EMA50"]) or rr_ratio<1:
            sell_hint = "⚠ Consider Selling"
        return {
            "Symbol": symbol,
            "Price": round(price,2),
            "Score": score,
            "Rating": rating,
            "Warning": warning,
            "Stop Loss": round(stop_loss,2),
            "Target": round(target,2),
            "RR Ratio": rr_ratio,
            "Sell Hint": sell_hint
        }
    except:
        return None

# --------------------------
# AGGRID COLOR
# --------------------------
def rating_color(params):
    val = params.value
    if isinstance(val,str):
        if '🔥' in val:
            return {'color':'red','fontWeight':'bold'}
        elif '✅' in val:
            return {'color':'green','fontWeight':'bold'}
        elif '👀' in val:
            return {'color':'orange','fontWeight':'bold'}
    return {}

# --------------------------
# PORTFOLIO SECTION
# --------------------------
if "portfolio" not in st.session_state:
    st.session_state.portfolio = []

st.header("📊 My Portfolio")
with st.expander("Add Stock to Portfolio"):
    col1,col2,col3,col4 = st.columns(4)
    with col1:
        p_symbol = st.text_input("Symbol (e.g., INFY.NS)")
    with col2:
        p_qty = st.number_input("Quantity",min_value=1,value=1)
    with col3:
        p_price = st.number_input("Buy Price",min_value=0.0,value=0.0,format="%.2f")
    with col4:
        if st.button("Add Stock"):
            if p_symbol and p_symbol not in [x['Symbol'] for x in st.session_state.portfolio]:
                st.session_state.portfolio.append({"Symbol":p_symbol,"Quantity":p_qty,"Buy Price":p_price})
                st.success(f"{p_symbol} added to portfolio")

# --------------------------
# SCAN BUTTON
# --------------------------
if st.button("🔍 Scan Market"):

    st.write("Scanning stocks... Please wait ⏳")
    data = download_batch(symbols)
    if data is None:
        st.error("Failed to download stock data")
    else:
        # Nifty return
        nifty_df = yf.download("^NSEI", period="2mo", interval="1d", progress=False)
        nifty_return = 0
        if nifty_df is not None and len(nifty_df)>30:
            latest = float(nifty_df["Close"].iloc[-1])
            past = float(nifty_df["Close"].iloc[-20])
            nifty_return = (latest/past)-1
        results=[]
        with st.spinner("Analyzing stocks..."):
            def process_stock(symbol):
                try:
                    stock_data = data[symbol]
                    return analyze_stock(symbol,nifty_return,stock_data)
                except:
                    return None
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                futures = [executor.submit(process_stock,sym) for sym in symbols]
                for f in concurrent.futures.as_completed(futures):
                    res = f.result()
                    if res:
                        results.append(res)
        if results:
            df_results = pd.DataFrame(results).fillna("").copy()
            df_results = df_results.sort_values(by="Score",ascending=False)
            st.success("Top Opportunities (Sorted by Score)")
            try:
                gb = GridOptionsBuilder.from_dataframe(df_results.head(50))
                gb.configure_pagination(paginationAutoPageSize=True)
                gb.configure_default_column(editable=False,groupable=True)
                gb.configure_column("Rating",cellStyle=rating_color)
                AgGrid(df_results.head(50),gridOptions=gb.build(),height=400)
            except:
                st.dataframe(df_results.head(50))

            # --------------------------
            # PORTFOLIO EVALUATION
            # --------------------------
            st.header("📈 Portfolio Analysis")
            if st.session_state.portfolio:
                portfolio_data=[]
                symbols_to_download = [x['Symbol'] for x in st.session_state.portfolio if x['Symbol'] not in symbols]
                port_data = download_batch(symbols_to_download)
                for stock in st.session_state.portfolio:
                    symbol = stock['Symbol']
                    qty = stock['Quantity']
                    buy_price = stock['Buy Price']
                    # price fetch
                    try:
                        if symbol in symbols:
                            price = df_results[df_results['Symbol']==symbol]['Price'].values[0]
                        else:
                            price = float(port_data[symbol]['Close'].iloc[-1])
                    except:
                        price = 0
                    unrealized = round((price-buy_price)*qty,2)
                    judgement = ""
                    if price < buy_price:
                        judgement="⚠ Price below buy"
                    elif price > buy_price and price> (price + 2*(price-buy_price)):
                        judgement="✅ Good Profit Potential"
                    else:
                        judgement="👀 Monitor"
                    portfolio_data.append({
                        "Symbol":symbol,
                        "Quantity":qty,
                        "Buy Price":buy_price,
                        "Current Price":price,
                        "Unrealized P&L":unrealized,
                        "Judgement":judgement
                    })
                df_port = pd.DataFrame(portfolio_data)
                st.dataframe(df_port)
            else:
                st.info("No stocks in portfolio yet.")

        else:
            st.info("No valid setups found.")
