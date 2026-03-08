import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from st_aggrid import AgGrid, GridOptionsBuilder
import concurrent.futures
from datetime import datetime, timedelta

# --------------------------
# PAGE CONFIG
# --------------------------
st.set_page_config(page_title="15% Annual Return Portfolio", layout="wide")
st.title("📈 Long‑Term Wealth Builder (Target 15% p.a.)")
st.write("Combine technical momentum with fundamental quality. Manage your portfolio like a professional.")

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
# SCORING WEIGHTS (Technical)
# --------------------------
TECH_WEIGHTS = {"trend":30, "lt_trend":15, "breakout":15, "volume":15, "relative_strength":25}

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
        df["EMA200"] = df["Close"].ewm(span=200).mean()
        last_close = float(df["Close"].iloc[-1])
        last_ema50 = float(df["EMA50"].iloc[-1])
        last_ema200 = float(df["EMA200"].iloc[-1])
        if last_close > last_ema50 and last_close > last_ema200:
            return "Strong Bullish"
        elif last_close > last_ema50:
            return "Bullish"
        else:
            return "Weak / Bearish"
    except Exception:
        return "Unknown"

market_regime = get_market_regime()
if "Weak" in market_regime:
    st.warning(f"⚠ Market Regime: {market_regime} — Consider reducing exposure")
elif "Bullish" in market_regime:
    st.success(f"✅ Market Regime: {market_regime} — Favorable for long‑term investing")
else:
    st.info(f"Market Regime: {market_regime}")

# --------------------------
# RECOMMENDATION OF THE DAY (cached)
# --------------------------
@st.cache_data(ttl=86400)  # Refresh once per day
def get_daily_recommendation():
    """
    Runs scanner on full list, enriches top results with fundamentals,
    and returns the single best stock based on combined score.
    """
    st.info("Computing recommendation of the day... (may take a few seconds)")
    # Download data for all symbols (chunked)
    data_dict = download_chunked(symbols, period="6mo", interval="1d")
    # Get Nifty return
    nifty_df = yf.download("^NSEI", period="2mo", interval="1d", progress=False)
    nifty_return = 0
    if nifty_df is not None and len(nifty_df) > 30:
        latest_nifty = float(nifty_df["Close"].iloc[-1])
        past_nifty = float(nifty_df["Close"].iloc[-20])
        nifty_return = (latest_nifty / past_nifty) - 1

    # Analyze all stocks
    results = []
    for sym, df in data_dict.items():
        res = analyze_stock_technical(sym, nifty_return, df)
        if res:
            results.append(res)
    if not results:
        return None
    df_tech = pd.DataFrame(results)
    # Take top 50 by technical score to limit fundamental calls
    top_50 = df_tech.nlargest(50, "Tech_Score").to_dict("records")
    enriched = []
    for item in top_50:
        sym = item["Symbol"]
        fd = get_fundamentals(sym)
        if fd:
            item.update(fd)
            # Compute combined score (simple average of tech score and quality score)
            qscore = fd.get("Quality_Score", 0)
            item["Combined_Score"] = (item["Tech_Score"] + qscore) / 2
            enriched.append(item)
    if not enriched:
        return None
    # Sort by combined score descending
    best = sorted(enriched, key=lambda x: x["Combined_Score"], reverse=True)[0]
    return best

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
    symbols = list(set(symbols))
    for i in range(0, len(symbols), chunk_size):
        chunk = symbols[i:i+chunk_size]
        try:
            df = yf.download(tickers=chunk, period=period, interval=interval,
                             group_by='ticker', progress=False, threads=True)
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

def analyze_stock_technical(symbol, nifty_return, data):
    """Technical analysis only – returns dict with Tech_Score and basic fields."""
    try:
        if len(data) < 60 or "Close" not in data.columns:
            return None

        df = data.copy()
        df = compute_atr(df, 14)
        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()
        df["EMA200"] = df["Close"].ewm(span=200).mean()

        required = ["Close", "EMA20", "EMA50", "EMA200", "ATR14", "Volume"]
        if any(col not in df.columns for col in required):
            return None

        latest = df.iloc[-1]
        price = float(latest["Close"])
        atr = float(latest["ATR14"])
        if pd.isna(atr) or atr == 0:
            return None

        score = 0
        warning = ""

        # Short-term trend (20 & 50 EMA)
        if price > float(latest["EMA20"]) and price > float(latest["EMA50"]):
            score += TECH_WEIGHTS["trend"]
        else:
            warning = "Below short-term EMAs"

        # Long-term trend (200 EMA)
        if price > float(latest["EMA200"]):
            score += TECH_WEIGHTS["lt_trend"]

        # Breakout (30-day high, excluding today)
        breakout_level = float(df["High"].rolling(30).max().iloc[-2])
        if price > breakout_level:
            score += TECH_WEIGHTS["breakout"]

        # Volume surge
        avg_vol = float(df["Volume"].rolling(20).mean().iloc[-1])
        if float(latest["Volume"]) > 1.3 * avg_vol:
            score += TECH_WEIGHTS["volume"]

        # Relative strength vs Nifty (20-day return)
        stock_return = (price / float(df["Close"].iloc[-20])) - 1
        if stock_return > nifty_return:
            score += TECH_WEIGHTS["relative_strength"]

        stop_loss = price - (1.5 * atr)
        target = price + (2 * atr)
        risk = price - stop_loss
        reward = target - price
        rr_ratio = round(reward / risk, 2) if risk != 0 else np.inf

        # Rating based on score
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
            "Tech_Score": score,
            "Rating": rating,
            "Warning": warning,
            "Stop Loss": round(stop_loss, 2),
            "Target": round(target, 2),
            "RR Ratio": rr_ratio
        }
    except Exception:
        return None

@st.cache_data(ttl=86400)
def get_fundamentals(symbol):
    """Fetch key fundamental metrics for a symbol."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        pe = info.get("trailingPE", np.nan)
        pb = info.get("priceToBook", np.nan)
        roe = info.get("returnOnEquity", np.nan)
        div_yield = info.get("dividendYield", np.nan)
        mcap = info.get("marketCap", np.nan)

        # Simple quality score (0-100)
        quality = 0
        if not np.isnan(roe) and roe > 0.15:
            quality += 40
        elif not np.isnan(roe) and roe > 0.10:
            quality += 20
        if not np.isnan(pe) and 10 < pe < 25:
            quality += 30
        elif not np.isnan(pe) and pe <= 10:
            quality += 20
        if not np.isnan(pb) and pb < 3:
            quality += 20
        if not np.isnan(div_yield) and div_yield > 0.01:
            quality += 10

        return {
            "Symbol": symbol,
            "P/E": round(pe, 2) if not np.isnan(pe) else "N/A",
            "P/B": round(pb, 2) if not np.isnan(pb) else "N/A",
            "ROE": f"{roe*100:.1f}%" if not np.isnan(roe) else "N/A",
            "Div Yield": f"{div_yield*100:.2f}%" if not np.isnan(div_yield) else "N/A",
            "Market Cap": mcap,
            "Quality_Score": quality
        }
    except Exception:
        return None

# --------------------------
# DISPLAY RECOMMENDATION OF THE DAY
# --------------------------
st.header("📢 Recommendation of the Day")
rec = get_daily_recommendation()
if rec:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Stock", rec["Symbol"])
    col2.metric("Price", f"₹{rec['Price']}")
    col3.metric("Tech Score", rec["Tech_Score"])
    col4.metric("Quality Score", rec["Quality_Score"])
    st.markdown(f"**Action:** {rec['Rating']}  \n**Rationale:** P/E {rec['P/E']}, ROE {rec['ROE']}, above 200‑day EMA, strong relative strength.")
else:
    st.info("Could not fetch recommendation today.")

# --------------------------
# PORTFOLIO EDITOR & ANALYSIS
# --------------------------
st.header("📊 Long‑Term Portfolio")
st.write("Edit holdings, add new stocks, or remove selected ones.")
st.caption("Goal: 15% annual return – think in years, not days.")

# Editable table
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

# Remove stocks section
if not st.session_state.portfolio.empty:
    with st.expander("🗑️ Remove Stocks"):
        stocks_to_remove = st.multiselect(
            "Select stocks to remove",
            options=st.session_state.portfolio["Symbol"].tolist()
        )
        if st.button("Remove Selected"):
            if stocks_to_remove:
                st.session_state.portfolio = st.session_state.portfolio[
                    ~st.session_state.portfolio["Symbol"].isin(stocks_to_remove)
                ]
                st.rerun()
else:
    st.info("Portfolio is empty. Add stocks using the table above.")

# Portfolio analysis (with 6 months data)
portfolio_symbols = st.session_state.portfolio["Symbol"].tolist()
if portfolio_symbols:
    st.subheader("📈 Portfolio Performance & Suggestions")
    with st.spinner("Fetching latest prices..."):
        data_dict = download_chunked(portfolio_symbols, period="6mo", interval="1d")
        portfolio_results = []
        total_investment = 0
        total_current_value = 0

        for idx, row in st.session_state.portfolio.iterrows():
            sym = row["Symbol"]
            qty = row["Quantity"]
            buy_price = row["Buy Price"]

            if sym not in data_dict:
                portfolio_results.append({
                    "Symbol": sym,
                    "Quantity": qty,
                    "Buy Price": buy_price,
                    "Current Price": 0,
                    "Unrealized P&L": 0,
                    "Target": 0,
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
                    "Target": 0,
                    "Suggested Action": "Insufficient Data"
                })
                continue

            df = compute_atr(df, 14)
            df["EMA50"] = df["Close"].ewm(span=50).mean()
            latest = df.iloc[-1]
            current_price = float(latest["Close"])

            # ATR-based target and stop
            atr = float(latest.get("ATR14", np.nan))
            if pd.isna(atr):
                atr = (df["High"].tail(30).max() - df["Low"].tail(30).min()) / 2
            target = current_price + (2 * atr)
            stop = current_price - (1.5 * atr)

            # P&L
            unrealized = round((current_price - buy_price) * qty, 2)
            total_investment += buy_price * qty
            total_current_value += current_price * qty

            # Long‑term action logic
            ema50 = float(df["EMA50"].iloc[-1]) if not pd.isna(df["EMA50"].iloc[-1]) else current_price
            # Fetch fundamentals for better action (optional, but we can use here)
            # For simplicity, we use price vs target/stop
            if current_price > target * 1.1:      # 10% above target → trim
                action = "✂️ Trim (Take Partial Profits)"
            elif current_price < stop * 0.9:      # 10% below stop → review
                action = "🔍 Review Fundamentals"
            elif current_price < ema50 * 0.95:    # 5% below 50‑day EMA → consider adding
                action = "💰 Accumulate on Dip"
            else:
                action = "✅ Hold"

            portfolio_results.append({
                "Symbol": sym,
                "Quantity": qty,
                "Buy Price": buy_price,
                "Current Price": round(current_price, 2),
                "Unrealized P&L": unrealized,
                "Target": round(target, 2),
                "Suggested Action": action
            })

        # Summary metrics
        total_unrealized = total_current_value - total_investment
        col1, col2, col3 = st.columns(3)
        col1.metric("💰 Total Investment", f"₹{total_investment:,.2f}")
        col2.metric("📈 Current Value", f"₹{total_current_value:,.2f}")
        col3.metric("💹 Unrealized P&L", f"₹{total_unrealized:,.2f}", delta=f"₹{total_unrealized:,.2f}")

        df_portfolio = pd.DataFrame(portfolio_results)
        st.dataframe(df_portfolio)

# --------------------------
# SCANNER (Top 250) with Fundamentals
# --------------------------
if st.button("🔍 Scan NSE 250 – Find Long‑Term Buys"):
    with st.spinner("Downloading market data..."):
        data_dict = download_chunked(symbols, period="6mo", interval="1d")

    # Nifty return for relative strength
    nifty_df = yf.download("^NSEI", period="2mo", interval="1d", progress=False)
    nifty_return = 0
    if nifty_df is not None and len(nifty_df) > 30:
        latest_nifty = float(nifty_df["Close"].iloc[-1])
        past_nifty = float(nifty_df["Close"].iloc[-20])
        nifty_return = (latest_nifty / past_nifty) - 1

    # Technical analysis on all symbols (concurrent)
    results = []
    progress_bar = st.progress(0, text="Analyzing technicals...")
    symbols_list = list(data_dict.keys())
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_sym = {
            executor.submit(analyze_stock_technical, sym, nifty_return, data_dict[sym]): sym
            for sym in symbols_list
        }
        for i, future in enumerate(concurrent.futures.as_completed(future_to_sym)):
            res = future.result()
            if res:
                results.append(res)
            progress_bar.progress((i + 1) / len(symbols_list))
    progress_bar.empty()

    if not results:
        st.warning("No technical setups found.")
        st.stop()

    df_tech = pd.DataFrame(results).sort_values(by="Tech_Score", ascending=False).reset_index(drop=True)
    st.success(f"Found {len(df_tech)} stocks with technical data. Enriching top 50 with fundamentals...")

    # Enrich top 50 with fundamentals
    top_50 = df_tech.head(50).to_dict("records")
    enriched = []
    with st.spinner("Fetching fundamentals for top 50..."):
        for item in top_50:
            sym = item["Symbol"]
            fd = get_fundamentals(sym)
            if fd:
                item.update(fd)
                # Combined score (tech + quality) – normalise quality to 0-100
                qscore = fd.get("Quality_Score", 0)
                item["Combined_Score"] = (item["Tech_Score"] + qscore) / 2
                enriched.append(item)

    if not enriched:
        st.warning("Could not fetch fundamentals.")
        st.dataframe(df_tech.head(50))
    else:
        df_final = pd.DataFrame(enriched).sort_values(by="Combined_Score", ascending=False)
        st.subheader("🏆 Top Opportunities (Technical + Fundamental)")
        # Display with AgGrid or simple table
        try:
            gb = GridOptionsBuilder.from_dataframe(df_final)
            gb.configure_pagination(paginationAutoPageSize=True)
            gb.configure_default_column(editable=False, groupable=True)
            AgGrid(df_final, gridOptions=gb.build(), height=500, fit_columns_on_grid_load=True)
        except:
            st.dataframe(df_final)
