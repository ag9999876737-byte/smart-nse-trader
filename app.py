# full code here
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from st_aggrid import AgGrid, GridOptionsBuilder
import concurrent.futures

st.set_page_config(page_title="Smart NSE Scanner + Portfolio", layout="wide")
st.title("📈 Smart NSE Scanner + Editable Portfolio")

# ----------------------------------
# PORTFOLIO SECTION
# ----------------------------------
if "portfolio" not in st.session_state:
    st.session_state.portfolio = pd.DataFrame([
        {"Symbol":"BEL.NS","Quantity":11,"Buy Price":403.18},
        {"Symbol":"GOLDBEES.NS","Quantity":5,"Buy Price":41.85},
        {"Symbol":"HINDPETRO.NS","Quantity":3,"Buy Price":151.33},
    ])

st.header("📊 Editable Portfolio")
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

# Fetch portfolio data
def fetch_data(symbols):
    try:
        return yf.download(tickers=symbols, period="1mo", interval="1d", group_by='ticker', progress=False)
    except:
        return None

portfolio_syms = edited_portfolio["Symbol"].tolist()
if portfolio_syms:
    data = fetch_data(portfolio_syms)
    total_investment = 0
    total_current_value = 0
    portfolio_results = []

    for _, r in edited_portfolio.iterrows():
        sym = r["Symbol"]
        qty = r["Quantity"]
        buy_price = r["Buy Price"]
        try:
            df = data[sym] if len(portfolio_syms) > 1 else data
            current_price = float(df["Close"].iloc[-1])
            ema50 = df["Close"].rolling(50).mean().iloc[-1]
            high = df["High"].rolling(30).max().iloc[-1]
            low = df["Low"].rolling(30).min().iloc[-1]
            atr = (high - low) / 2
            target = current_price + 2 * atr
            stop_loss = current_price - 1.5 * atr
            rr_ratio = (target - current_price) / (current_price - stop_loss)
        except:
            current_price = 0
            target = 0
            rr_ratio = 0
            ema50 = 0

        unrealized = round((current_price - buy_price) * qty, 2)
        total_investment += buy_price * qty
        total_current_value += current_price * qty

        if current_price < buy_price * 0.95 and current_price > ema50:
            action = "💰 Buy More"
        elif current_price > target or rr_ratio > 2:
            action = "🏁 Consider Selling / Take Profit"
        elif current_price < ema50 or rr_ratio < 1:
            action = "⚠ Sell / Cut Loss"
        else:
            action = "👀 Hold"

        portfolio_results.append({
            "Symbol": sym,
            "Quantity": qty,
            "Buy Price": buy_price,
            "Current Price": round(current_price,2),
            "Unrealized P&L": unrealized,
            "RR Ratio": round(rr_ratio,2),
            "Target Price": round(target,2),
            "Suggested Action": action
        })

    df_portfolio = pd.DataFrame(portfolio_results)
    total_unrealized = total_current_value - total_investment

    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Total Investment", f"₹{total_investment:,.2f}")
    col2.metric("📈 Current Value", f"₹{total_current_value:,.2f}")
    col3.metric("💹 Total Unrealized P&L", f"₹{total_unrealized:,.2f}", delta=f"₹{total_unrealized:,.2f}")

    st.subheader("Portfolio Analysis")
    st.dataframe(df_portfolio)
else:
    st.info("Portfolio is empty - add some stocks.")

# ----------------------------------
# MARKET SCANNER SECTION
# ----------------------------------
st.header("🔍 Market Scanner (Any NSE tickers)")

uploaded = st.file_uploader("Upload a CSV with tickers (column named Symbol)", type="csv")
scan_input = st.text_input("Or enter tickers (comma-separated)", value="RELIANCE.NS, TCS.NS, INFY.NS")

if uploaded:
    df_symbols = pd.read_csv(uploaded)
    if "Symbol" in df_symbols.columns:
        scan_symbols = df_symbols["Symbol"].astype(str).str.strip().tolist()
    else:
        st.error("CSV must contain a column named Symbol")
        scan_symbols = []
else:
    scan_symbols = [s.strip().upper() for s in scan_input.split(",") if s.strip()]

st.write(f"Scanning {len(scan_symbols)} tickers...")

def analyze_stock(symbol, data):
    try:
        df = data[symbol] if len(scan_symbols) > 1 else data
        if len(df) < 60: return None

        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()
        df["TR"] = np.maximum(df["High"]-df["Low"], np.maximum(abs(df["High"]-df["Close"].shift()), abs(df["Low"]-df["Close"].shift())))
        df["ATR14"] = df["TR"].rolling(14).mean()

        latest = df.iloc[-1]
        price = float(latest["Close"])
        atr = float(latest["ATR14"])
        breakout = float(df["High"].rolling(30).max().iloc[-2])
        avg_vol = float(df["Volume"].rolling(20).mean().iloc[-1])

        score = 0
        warning = ""
        if price > latest["EMA20"] and price > latest["EMA50"]:
            score += 40
        else:
            warning = "Below EMA50"
        if price > breakout:
            score += 20
        if float(latest["Volume"]) > 1.3 * avg_vol:
            score += 15

        stop_loss = price - 1.5 * atr
        target = price + 2 * atr
        rr_ratio = round((target - price)/(price - stop_loss),2)

        if score >= 70: rating="🔥 Strong Buy"
        elif score >= 55: rating="✅ Buy"
        elif score >= 40: rating="👀 Watch"
        else: rating="Avoid"

        sell_hint = ""
        if price < latest["EMA50"] or rr_ratio < 1:
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

if st.button("Scan Now"):
    if scan_symbols:
        data = download_batch(scan_symbols) if (scan_symbols := scan_symbols) else None
        if data is None: st.error("Download failed")
        else:
            results=[]
            with st.spinner("Analyzing..."):
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                    futures=[executor.submit(lambda s: analyze_stock(s,data), s) for s in scan_symbols]
                    for f in concurrent.futures.as_completed(futures):
                        r=f.result()
                        if r: results.append(r)

            if results:
                df_results=pd.DataFrame(results).fillna("").copy()
                df_results=df_results.sort_values(by="Score",ascending=False)
                try:
                    gb=GridOptionsBuilder.from_dataframe(df_results)
                    gb.configure_pagination(paginationAutoPageSize=True)
                    AgGrid(df_results,gridOptions=gb.build(),height=400)
                except:
                    st.dataframe(df_results)
            else:
                st.info("No valid setups found.")
    else:
        st.info("Enter tickers or upload CSV.")
