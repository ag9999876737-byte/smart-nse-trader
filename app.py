import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from st_aggrid import AgGrid, GridOptionsBuilder
import concurrent.futures

# --------------------------
# PAGE CONFIG
# --------------------------
st.set_page_config(page_title="Smart NSE Scanner + Professional Portfolio", layout="wide")
st.title("📈 Smart NSE Swing Scanner + Professional Portfolio")
st.write("Momentum-based ranking engine with risk management and actionable portfolio insights")

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
    st.session_state.portfolio = [
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
    ]

# Add custom stock
st.header("📊 My Portfolio")
with st.expander("Add Stock to Portfolio"):
    col1, col2, col3, col4 = st.columns(4)
    with col1: p_symbol = st.text_input("Symbol (e.g., INFY.NS)")
    with col2: p_qty = st.number_input("Quantity",min_value=1,value=1)
    with col3: p_price = st.number_input("Buy Price",min_value=0.0,value=0.0,format="%.2f")
    with col4:
        if st.button("Add Stock"):
            if p_symbol and p_symbol not in [x['Symbol'] for x in st.session_state.portfolio]:
                st.session_state.portfolio.append({"Symbol":p_symbol,"Quantity":p_qty,"Buy Price":p_price})
                st.success(f"{p_symbol} added to portfolio")

# --------------------------
# CACHED DOWNLOAD
# --------------------------
@st.cache_data(ttl=1800)
def download_batch(symbols, period="6mo", interval="1d"):
    try:
        df = yf.download(tickers=symbols, period=period, interval=interval, group_by='ticker', progress=False)
        return df
    except:
        return None

# --------------------------
# MARKET REGIME
# --------------------------
@st.cache_data(ttl=3600)
def get_market_regime():
    df = yf.download("^NSEI", period="3mo", interval="1d", progress=False)
    if df is None or df.empty or "Close" not in df.columns: return "Unknown"
    df["EMA50"] = df["Close"].ewm(span=50).mean()
    return "Bullish" if df["Close"].iloc[-1] > df["EMA50"].iloc[-1] else "Weak"

market_regime = get_market_regime()
if market_regime == "Weak": st.warning("⚠ Market Trend Weak — Trades carry higher risk")
elif market_regime == "Bullish": st.success("✅ Market Trend Bullish")
else: st.info("Market Regime Unknown")

# --------------------------
# ANALYSIS FUNCTION
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
# AGGRID COLOR
# --------------------------
def rating_color(params):
    val=params.value
    if isinstance(val,str):
        if '🔥' in val: return {'color':'red','fontWeight':'bold'}
        elif '✅' in val: return {'color':'green','fontWeight':'bold'}
        elif '👀' in val: return {'color':'orange','fontWeight':'bold'}
    return {}

# --------------------------
# PORTFOLIO RECOMMENDATION
# --------------------------
def portfolio_action(price, buy_price, rr_ratio, ema50, target):
    if price < buy_price*0.95 and price>ema50: return "💰 Buy More"
    elif price>target or rr_ratio>2: return "🏁 Consider Selling / Take Profit"
    elif price<ema50 or rr_ratio<1: return "⚠ Sell / Cut Loss"
    else: return "👀 Hold"

# --------------------------
# SCAN MARKET
# --------------------------
if st.button("🔍 Scan Market"):
    st.write("Scanning stocks... ⏳")
    data=download_batch(symbols)
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
                gb.configure_column("Rating",cellStyle=rating_color)
                AgGrid(df_results.head(50),gridOptions=gb.build(),height=400)
            except: st.dataframe(df_results.head(50))

            # --------------------------
            # PORTFOLIO ANALYSIS
            # --------------------------
            st.header("📈 Portfolio Analysis")
            if st.session_state.portfolio:
                portfolio_data=[]
                # download prices for custom stocks not in top 250
                custom_symbols=[x['Symbol'] for x in st.session_state.portfolio if x['Symbol'] not in symbols]
                port_data=download_batch(custom_symbols) if custom_symbols else {}
                for stock in st.session_state.portfolio:
                    symbol=stock['Symbol']
                    qty=stock['Quantity']
                    buy_price=stock['Buy Price']
                    try:
                        if symbol in symbols:
                            price=df_results[df_results['Symbol']==symbol]['Price'].values[0]
                            target=df_results[df_results['Symbol']==symbol]['Target'].values[0]
                            rr_ratio=df_results[df_results['Symbol']==symbol]['RR Ratio'].values[0]
                            ema50=df_results[df_results['Symbol']==symbol]['Price'].values[0]-rr_ratio  # approx
                        else:
                            price=float(port_data[symbol]['Close'].iloc[-1])
                            high=float(port_data[symbol]['High'].rolling(30).max().iloc[-1])
                            low=float(port_data[symbol]['Low'].rolling(30).min().iloc[-1])
                            atr=(high-low)/2
                            target=price+2*atr
                            stop_loss=price-1.5*atr
                            rr_ratio=(target-price)/(price-stop_loss)
                            ema50=port_data[symbol]['Close'].rolling(50).mean().iloc[-1]
                    except:
                        price=0; target=0; rr_ratio=0; ema50=0
                    unrealized=round((price-buy_price)*qty,2)
                    action=portfolio_action(price,buy_price,rr_ratio,ema50,target)
                    portfolio_data.append({"Symbol":symbol,"Quantity":qty,"Buy Price":buy_price,
                                           "Current Price":price,"Unrealized P&L":unrealized,
                                           "RR Ratio":rr_ratio,"Target Price":round(target,2),
                                           "Suggested Action":action})
                df_port=pd.DataFrame(portfolio_data)
                st.dataframe(df_port)
            else:
                st.info("No stocks in portfolio yet.")
        else:
            st.info("No valid setups found.")
