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
# PORTFOLIO (initial data)
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
        if df is None or df.empty or "Close" not in df.columns:
            return "Unknown"
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df["EMA50"] = df["Close"].ewm(span=50).mean()
        last_close = float(df["Close"].iloc[-1])
        last_ema50 = float(df["EMA50"].iloc[-1])
        return "Bullish" if last_close > last_ema50 else "Weak"
    except Exception:
        return "Unknown"

market_regime = get_market_regime()
if market_regime == "Weak":
    st.warning("⚠ Market Trend Weak — Trades carry higher risk")
elif market_regime == "Bullish":
    st.success("✅ Market Trend Bullish")
else:
    st.info("Market Regime Unknown")

# --------------------------
# HELPER FUNCTIONS
# --------------------------
def compute_atr(df, period=14):
    """Add ATR to dataframe."""
    df = df.copy()
    df["TR"] = np.maximum(
        df["High"] - df["Low"],
        np.maximum(
            abs(df["High"] - df["Close"].shift()),
            abs(df["Low"] - df["Close"].shift())
        )
    )
    df[f"ATR{period}"] = df["TR"].rolling(period).mean()
    return df

@st.cache_data(ttl=1800)
def download_chunked(symbols, period="6mo", interval="1d", chunk_size=50):
    """
    Download data for many symbols in chunks to avoid timeouts.
    Returns a dict {symbol: DataFrame} with OHLCV data.
    """
    all_data = {}
    # Ensure symbols list is unique
    symbols = list(set(symbols))
    for i in range(0, len(symbols), chunk_size):
        chunk = symbols[i:i+chunk_size]
        try:
            df = yf.download(tickers=chunk, period=period, interval=interval,
                             group_by='ticker', progress=False, threads=True)
            # If only one symbol, df is a DataFrame; wrap it in dict
            if len(chunk) == 1:
                all_data[chunk[0]] = df
            else:
                for sym in chunk:
                    if sym in df.columns.levels[0]:
                        all_data[sym] = df[sym]
        except Exception as e:
            st.warning(f"Failed to download chunk {chunk}: {e}")
            continue
    return all_data

def analyze_stock(symbol, nifty_return, data):
    """Analyze a single stock and return a dict with scores, ratings, etc."""
    try:
        if len(data) < 60 or "Close" not in data.columns:
            return None

        # Ensure we have enough data for indicators
        df = data.copy()
        df = compute_atr(df, 14)
        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()

        # Check for required columns
        required = ["Close", "EMA20", "EMA50", "ATR14", "Volume"]
        if any(col not in df.columns for col in required):
            return None

        latest = df.iloc[-1]
        price = float(latest["Close"])
        atr = float(latest["ATR14"])
        if pd.isna(atr) or atr == 0:
            return None

        score = 0
        warning = ""

        # Trend
        if price > float(latest["EMA20"]) and price > float(latest["EMA50"]):
            score += WEIGHTS["trend"]
        else:
            warning = "Below EMA50"

        # Breakout (highest high of last 30 days, excluding today)
        breakout_level = float(df["High"].rolling(30).max().iloc[-2])
        if price > breakout_level:
            score += WEIGHTS["breakout"]

        # Volume surge
        avg_vol = float(df["Volume"].rolling(20).mean().iloc[-1])
        if float(latest["Volume"]) > 1.3 * avg_vol:
            score += WEIGHTS["volume"]

        # Relative strength vs Nifty (20-day return)
        stock_return = (price / float(df["Close"].iloc[-20])) - 1
        if stock_return > nifty_return:
            score += WEIGHTS["relative_strength"]

        # Stop Loss & Target (1.5x ATR, 2x ATR)
        stop_loss = price - (1.5 * atr)
        target = price + (2 * atr)

        # Risk/Reward
        risk = price - stop_loss
        reward = target - price
        rr_ratio = round(reward / risk, 2) if risk != 0 else np.inf

        # Rating
        if score >= 70:
            rating = "🔥 Strong Buy"
        elif score >= 55:
            rating = "✅ Buy"
        elif score >= 40:
            rating = "👀 Watch"
        else:
            rating = "Avoid"

        # Sell hint for existing holdings
        sell_hint = ""
        if price < float(latest["EMA50"]) or rr_ratio < 1:
            sell_hint = "⚠ Consider Selling"

        return {
            "Symbol": symbol,
            "Price": round(price, 2),
            "Score": score,
            "Rating": rating,
            "Warning": warning,
            "Stop Loss": round(stop_loss, 2),
            "Target": round(target, 2),
            "RR Ratio": rr_ratio,
            "Sell Hint": sell_hint
        }
    except Exception as e:
        # Optionally log e
        return None

# --------------------------
# PORTFOLIO EDITOR & ANALYSIS
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

# Fetch current prices and compute P&L for portfolio
portfolio_symbols = edited_portfolio["Symbol"].tolist()
if portfolio_symbols:
    st.write("Fetching current prices for portfolio...")
    try:
        # Use 6 months of data to have enough for EMA50 and 30-day high/low
        data_dict = download_chunked(portfolio_symbols, period="6mo", interval="1d")
        portfolio_results = []
        total_investment = 0
        total_current_value = 0

        for idx, row in edited_portfolio.iterrows():
            sym = row["Symbol"]
            qty = row["Quantity"]
            buy_price = row["Buy Price"]

            if sym not in data_dict:
                # Skip if no data
                portfolio_results.append({
                    "Symbol": sym,
                    "Quantity": qty,
                    "Buy Price": buy_price,
                    "Current Price": 0,
                    "Unrealized P&L": 0,
                    "RR Ratio": 0,
                    "Target Price": 0,
                    "Suggested Action": "No Data"
                })
                continue

            df = data_dict[sym].copy()
            if len(df) < 30 or "Close" not in df.columns:
                portfolio_results.append({
                    "Symbol": sym,
                    "Quantity": qty,
                    "Buy Price": buy_price,
                    "Current Price": 0,
                    "Unrealized P&L": 0,
                    "RR Ratio": 0,
                    "Target Price": 0,
                    "Suggested Action": "Insufficient Data"
                })
                continue

            # Compute indicators
            df = compute_atr(df, 14)
            df["EMA50"] = df["Close"].ewm(span=50).mean()

            latest = df.iloc[-1]
            current_price = float(latest["Close"])

            # 30-day high/low (using last 30 rows)
            high_30 = df["High"].tail(30).max()
            low_30 = df["Low"].tail(30).min()
            atr = float(latest.get("ATR14", np.nan))
            if pd.isna(atr):
                # Fallback to simple ATR approximation
                atr = (high_30 - low_30) / 2

            # Stop Loss & Target (same logic as scanner)
            stop_loss = current_price - (1.5 * atr)
            target = current_price + (2 * atr)
            risk = current_price - stop_loss
            reward = target - current_price
            if risk == 0:
                rr_ratio = np.inf
            else:
                rr_ratio = round(reward / risk, 2)

            # Unrealized P&L
            unrealized = round((current_price - buy_price) * qty, 2)

            # Suggested action (using same rules as before but robust to NaNs)
            ema50 = float(df["EMA50"].iloc[-1]) if not pd.isna(df["EMA50"].iloc[-1]) else current_price

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
                "Current Price": round(current_price, 2),
                "Unrealized P&L": unrealized,
                "RR Ratio": rr_ratio,
                "Target Price": round(target, 2),
                "Suggested Action": action
            })

            total_investment += buy_price * qty
            total_current_value += current_price * qty

        # Display summary metrics
        df_portfolio = pd.DataFrame(portfolio_results)
        total_unrealized = total_current_value - total_investment
        col1, col2, col3 = st.columns(3)
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
# TOP 250 NSE SCANNER
# --------------------------
if st.button("🔍 Scan Top 250 NSE Stocks"):
    with st.spinner("Downloading data for 250 stocks..."):
        data_dict = download_chunked(symbols, period="6mo", interval="1d")

    # Get Nifty return for relative strength
    nifty_df = yf.download("^NSEI", period="2mo", interval="1d", progress=False)
    nifty_return = 0
    if nifty_df is not None and len(nifty_df) > 30:
        latest_nifty = float(nifty_df["Close"].iloc[-1])
        past_nifty = float(nifty_df["Close"].iloc[-20])
        nifty_return = (latest_nifty / past_nifty) - 1

    # Analyze each stock concurrently with progress bar
    results = []
    progress_bar = st.progress(0, text="Analyzing stocks...")
    symbols_list = list(data_dict.keys())

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_sym = {
            executor.submit(analyze_stock, sym, nifty_return, data_dict[sym]): sym
            for sym in symbols_list
        }
        for i, future in enumerate(concurrent.futures.as_completed(future_to_sym)):
            res = future.result()
            if res:
                results.append(res)
            progress_bar.progress((i + 1) / len(symbols_list))

    progress_bar.empty()

    if results:
        df_results = pd.DataFrame(results).fillna("")
        df_results = df_results.sort_values(by="Score", ascending=False).reset_index(drop=True)

        st.success("Top Opportunities (Sorted by Score)")
        try:
            # Use AgGrid for interactive table
            gb = GridOptionsBuilder.from_dataframe(df_results.head(50))
            gb.configure_pagination(paginationAutoPageSize=True)
            gb.configure_default_column(editable=False, groupable=True)
            AgGrid(df_results.head(50), gridOptions=gb.build(), height=400, fit_columns_on_grid_load=True)
        except Exception:
            # Fallback to simple dataframe if AgGrid fails
            st.dataframe(df_results.head(50))
    else:
        st.info("No valid setups found.")
