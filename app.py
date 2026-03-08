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
st.title("📈 Smart NSE Swing Scanner + Editable Portfolio")
st.write("Scan NSE top stocks and manage your portfolio with professional suggestions.")

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
WEIGHTS = {"trend":40, "breakout":20, "volume":15, "relative_strength":15}

# --------------------------
# PORTFOLIO
# --------------------------
if "portfolio" not in st.session_state:
    st.session_state.portfolio = pd.DataFrame([
        {"Symbol":"BEL.NS","Quantity":11,"Buy Price":403.18},
        {"Symbol":"GOLDBEES.NS","Quantity":5,"Buy Price":41.85},
        {"Symbol":"HINDPETRO.NS","Quantity":3,"Buy Price":151.33},
        {"Symbol":"JUNIORBEES.NS","Quantity":8,"Buy Price":461.79},
        {"Symbol":"MMTC.NS","Quantity":10,"Buy Price":30.20},
        {"Symbol":"NATIONALUM.NS","Quantity":5,"Buy Price":53.20},
        {"Symbol":"NBCC.NS","Quantity":4,"Buy Price":98.75},
        {"Symbol":"NIFTYBEES.NS","Quantity":9,"Buy Price":178.54},
        {"Symbol":"NTPC.NS","Quantity":5,"Buy Price":99.40},
        {"Symbol":"ONGC.NS","Quantity":0,"Buy Price":275.00},
        {"Symbol":"RCF.NS","Quantity":2,"Buy Price":75.85},
        {"Symbol":"RVNL.NS","Quantity":1,"Buy Price":36.70},
        {"Symbol":"SILVERBEES.NS","Quantity":8,"Buy Price":321.78},
        {"Symbol":"SUZLON.NS","Quantity":7,"Buy Price":66.20},
    ])

# --------------------------
# MARKET REGIME
# --------------------------
@st.cache_data(ttl=3600)
def get_market_regime():
    try:
        df = yf.download("^NSEI", period="3mo", interval="1d", progress=False)
        if df is None or df.empty or "Close" not in df.columns: return "Unknown"
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df["EMA50"] = df["Close"].ewm(span=50).mean()
        last_close = float(df["Close"].iloc[-1])
        last_ema50 = float(df["EMA50"].iloc[-1])
        return "Bullish" if last_close > last_ema50 else "Weak"
    except:
        return "Unknown"

market_regime = get_market_regime()
if market_regime == "Weak": st.warning("⚠ Market Trend Weak — Trades carry higher risk")
elif market_regime == "Bullish": st.success("✅ Market Trend Bullish")
else: st.info("Market Regime Unknown")

# --------------------------
# SAFE DOWNLOAD FUNCTION
# --------------------------
@st.cache_data(ttl=1800)
def download_batch(symbols, period="6mo", interval="1d"):
    try:
        df = yf.download(tickers=symbols, period=period, interval=interval, group_by='ticker', progress=False)
        return df
    except:
        return None

# --------------------------
# ANALYZE STOCK
# --------------------------
def analyze_stock(symbol, nifty_return, data):
    try:
        if len(data)<60 or "Close" not in data.columns: return None
        df=data.copy()
        df["EMA20"]=df["Close"].ewm(span=20).mean()
        df["EMA50"]=df["Close"].ewm(span=50).mean()
        df["TR"]=np.maximum(df["High"]-df["Low"], np.maximum(abs(df["High"]-df["Close"].shift()),abs(df["Low"]-df["Close"].shift())))
        df["ATR14"]=df["TR"].rolling(14).mean()
        latest=df.iloc[-1]
        price=float(latest["Close"])
        atr=float(latest["ATR14"])
        score=0
        warning=""
        if price>float(latest["EMA20"]) and price>float(latest["EMA50"]): score+=WEIGHTS["trend"]
        else: warning="Below EMA50"
        breakout_level=float(df["High"].rolling(30).max().iloc[-2])
        if price>breakout_level: score+=WEIGHTS["breakout"]
        avg_vol=float(df["Volume"].rolling(20).mean().iloc[-1])
        if float(latest["Volume"])>1.3*avg_vol: score+=WEIGHTS["volume"]
        stock_return=(price/float(df["Close"].iloc[-20]))-1
        if stock_return>nifty_return: score+=WEIGHTS["relative_strength"]
        stop_loss=price-(1.5*atr)
        target=price+(2*atr)
        rr_ratio=round((target-price)/(price-stop_loss),2)
        if score>=70: rating="🔥 Strong Buy"
        elif score>=55: rating="✅ Buy"
        elif score>=40: rating="👀 Watch"
        else: rating="Avoid"
        sell_hint=""
        if price<float(latest["EMA50"]) or rr_ratio<1: sell_hint="⚠ Consider Selling"
        return {"Symbol":symbol,"Price":round(price,2),"Score":score,"Rating":rating,
                "Warning":warning,"Stop Loss":round(stop_loss,2),"Target":round(target,2),
                "RR Ratio":rr_ratio,"Sell Hint":sell_hint}
    except: return None

# --------------------------
# PORTFOLIO EDITOR
# --------------------------
st.header("📊 Editable Portfolio")
st.write("Edit Quantity / Buy Price, remove stocks, or add new stocks below.")

edited_portfolio = st.data_editor(
    st.session_state.portfolio,
    num_rows="dynamic",
    column_config={
        "Symbol": st.column_config.TextColumn("Stock Symbol"),
        "Quantity": st.column_config.NumberColumn("Quantity", min_value=0, step=1),
        "Buy Price": st.column_config.NumberColumn("Buy Price", min_value=0.0, step=0.01, format="%.2f"),
    },
    key="portfolio_editor",
)
st.session_state.portfolio = edited_portfolio.copy()

# --------------------------
# Fetch current prices & calculate P&L
# --------------------------
symbols = edited_portfolio["Symbol"].tolist()
if symbols:
    st.write("Fetching current prices...")
    try:
        data = yf.download(tickers=symbols, period="1mo", interval="1d", group_by='ticker', progress=False)
        portfolio_results = []
        total_investment = 0
        total_current_value = 0
        for idx, row in edited_portfolio.iterrows():
            sym = row["Symbol"]
            qty = row["Quantity"]
            buy_price = row["Buy Price"]
            try:
                df = data[sym] if len(symbols) > 1 else data
                current_price = float(df["Close"].iloc[-1])
                ema50 = df["Close"].rolling(50).mean().iloc[-1]
                high = df["High"].rolling(30).max().iloc[-1]
                low = df["Low"].rolling(30).min().iloc[-1]
                atr = (high-low)/2
                target = current_price + 2*atr
                stop_loss = current_price - 1.5*atr
                rr_ratio = (target-current_price)/(current_price-stop_loss)
            except:
                current_price = 0
                target = 0
                rr_ratio = 0
                ema50 = 0
            unrealized = round((current_price - buy_price) * qty,2)
            total_investment += buy_price * qty
            total_current_value += current_price * qty
            # Professional action
            if current_price < buy_price*0.95 and current_price>ema50:
                action = "💰 Buy More"
            elif current_price>target or rr_ratio>2:
                action = "🏁 Consider Selling / Take Profit"
            elif current_price<ema50 or rr_ratio<1:
                action = "⚠ Sell / Cut Loss"
            else:
                action = "👀 Hold"
            portfolio_results.append({
                "Symbol":sym,
                "Quantity":qty,
                "Buy Price":buy_price,
                "Current Price":round(current_price,2),
                "Unrealized P&L":unrealized,
                "RR Ratio":round(rr_ratio,2),
                "Target Price":round(target,2),
                "Suggested Action":action
            })
        df_portfolio = pd.DataFrame(portfolio_results)
        
        # Portfolio summary
        total_unrealized = total_current_value - total_investment
        col1,col2,col3 = st.columns(3)
        col1.metric("💰 Total Investment", f"₹{total_investment:,.2f}")
        col2.metric("📈 Current Value", f"₹{total_current_value:,.2f}")
        col3.metric("💹 Total Unrealized P&L", f"₹{total_unrealized:,.2f}", delta=f"₹{total_unrealized:,.2f}")
        
        st.subheader("Portfolio Analysis")
        st.dataframe(df_portfolio)
    except Exception as e:
        st.error(f"Failed to fetch portfolio prices: {e}")
else:
    st.info("Portfolio is empty. Add stocks to track.")

# --------------------------
# Top 250 NSE Scanner Button
# --------------------------
if st.button("🔍 Scan Top 250 NSE Stocks"):
    st.write("Scanning stocks... ⏳")
    data = download_batch(symbols)
    if data is None: st.error("Failed to download stock data")
    else:
        nifty_df=yf.download("^NSEI",period="2mo",interval="1d",progress=False)
        nifty_return=0
        if nifty_df is not None and len(nifty_df)>30:
            latest=float(nifty_df["Close"].iloc[-1])
            past=float(nifty_df["Close"].iloc[-20])
            nifty_return=(latest/past)-1
        results=[]
        with st.spinner("Analyzing stocks..."):
            def process_stock(symbol):
                try:
                    stock_data=data[symbol]
                    return analyze_stock(symbol,nifty_return,stock_data)
                except: return None
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                futures=[executor.submit(process_stock,sym) for sym in symbols]
                for f in concurrent.futures.as_completed(futures):
                    res=f.result()
                    if res: results.append(res)
        if results:
            df_results=pd.DataFrame(results).fillna("").copy()
            df_results=df_results.sort_values(by="Score",ascending=False)
            st.success("Top Opportunities (Sorted by Score)")
            try:
                gb=GridOptionsBuilder.from_dataframe(df_results.head(50))
                gb.configure_pagination(paginationAutoPageSize=True)
                gb.configure_default_column(editable=False,groupable=True)
                AgGrid(df_results.head(50),gridOptions=gb.build(),height=400)
            except:
                st.dataframe(df_results.head(50))
        else:
            st.info("No valid setups found.")
