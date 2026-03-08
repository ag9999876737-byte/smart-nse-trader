import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from st_aggrid import AgGrid, GridOptionsBuilder
import concurrent.futures

st.set_page_config(page_title="Smart NSE Scanner + Editable Portfolio", layout="wide")
st.title("📈 Smart NSE Swing Scanner + Editable Portfolio")
st.write("Manage your portfolio, track unrealized P&L and get professional suggestions.")

# --------------------------
# Sample Portfolio
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
# Editable Portfolio Section
# --------------------------
st.header("📊 Manage Portfolio")
st.write("Edit Quantity / Buy Price or remove stocks. Add new stocks at the bottom.")

# Use st.data_editor for editable table
edited_portfolio = st.data_editor(
    st.session_state.portfolio,
    num_rows="dynamic",  # allows adding/removing rows
    column_config={
        "Symbol": st.column_config.TextColumn("Stock Symbol"),
        "Quantity": st.column_config.NumberColumn("Quantity", min_value=0, step=1),
        "Buy Price": st.column_config.NumberColumn("Buy Price", min_value=0.0, step=0.01, format="%.2f"),
    },
    key="portfolio_editor",
)

# Save the edited table back to session
st.session_state.portfolio = edited_portfolio.copy()

# --------------------------
# Fetch Current Prices & Calculate P&L
# --------------------------
symbols = edited_portfolio["Symbol"].tolist()
if symbols:
    st.write("Fetching current prices...")
    try:
        data = yf.download(tickers=symbols, period="1mo", interval="1d", group_by='ticker', progress=False)
        portfolio_results = []
        for idx, row in edited_portfolio.iterrows():
            sym = row["Symbol"]
            qty = row["Quantity"]
            buy_price = row["Buy Price"]
            try:
                # handle MultiIndex if multiple tickers
                if len(symbols) > 1:
                    df = data[sym]
                else:
                    df = data
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
            # Professional action logic
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
        st.subheader("Portfolio Analysis")
        st.dataframe(df_portfolio)
    except Exception as e:
        st.error(f"Failed to fetch portfolio prices: {e}")
else:
    st.info("Portfolio is empty. Add stocks to track.")
