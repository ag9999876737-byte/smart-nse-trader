import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import time
import plotly.graph_objects as go

# Page configuration for mobile
st.set_page_config(
    page_title="Indian Stock Alerts",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for mobile-friendly dark theme
st.markdown("""
<style>
    /* Mobile optimization */
    .main > div {
        padding: 0px 10px;
    }
    
    /* Dark theme */
    .stApp {
        background-color: #0a0b0e;
    }
    
    h1, h2, h3, h4, p, li {
        color: white !important;
    }
    
    /* Stock cards - mobile friendly */
    .stock-card {
        background: linear-gradient(145deg, #1a1c1f, #15171a);
        border: 1px solid #2a2c2f;
        border-radius: 15px;
        padding: 15px;
        margin: 10px 0;
        box-shadow: 0 4px 8px rgba(0,0,0,0.3);
    }
    
    /* Signal cards */
    .signal-card {
        background: linear-gradient(145deg, #1e2125, #181b1f);
        border-left: 6px solid;
        border-radius: 15px;
        padding: 15px;
        margin: 15px 0;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }
    
    .buy-card {
        border-left-color: #00ff00;
    }
    
    .sell-card {
        border-left-color: #ff0000;
    }
    
    /* Metric boxes */
    .metric-box {
        background: linear-gradient(145deg, #1e2125, #181b1f);
        border-radius: 15px;
        padding: 15px;
        text-align: center;
        margin: 5px 0;
    }
    
    /* Buttons - bigger for mobile touch */
    .stButton > button {
        background: linear-gradient(145deg, #00bcd4, #0097a7) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 15px 20px !important;
        font-weight: 600 !important;
        font-size: 16px !important;
        width: 100%;
        margin: 5px 0;
    }
    
    /* Success message */
    .success-msg {
        background-color: #00ff0020;
        border-left: 4px solid #00ff00;
        padding: 10px;
        border-radius: 5px;
        color: white;
        margin: 10px 0;
    }
    
    /* Price colors */
    .price-up {
        color: #00ff00;
        font-weight: bold;
    }
    
    .price-down {
        color: #ff0000;
        font-weight: bold;
    }
    
    /* Confidence badges */
    .high-conf {
        background: #00ff00;
        color: black;
        padding: 6px 12px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
    }
    
    .med-conf {
        background: #ffff00;
        color: black;
        padding: 6px 12px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
    }
    
    .low-conf {
        background: #ff0000;
        color: white;
        padding: 6px 12px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
    }
    
    /* Select box - bigger for mobile */
    .stSelectbox > div > div {
        background-color: #1a1c1f !important;
        color: white !important;
        border: 1px solid #2a2c2f !important;
        min-height: 50px !important;
    }
    
    /* Progress bar */
    .stProgress > div > div {
        background-color: #00bcd4 !important;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.title("📈 Indian Stock Alerts")
st.markdown("---")

# Initialize session state
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ['RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK']
if 'signals' not in st.session_state:
    st.session_state.signals = []

# Stock mapping for NSE
STOCKS = {
    'RELIANCE': 'RELIANCE.NS',
    'TCS': 'TCS.NS',
    'HDFCBANK': 'HDFCBANK.NS',
    'INFY': 'INFY.NS',
    'ICICIBANK': 'ICICIBANK.NS',
    'HINDUNILVR': 'HINDUNILVR.NS',
    'ITC': 'ITC.NS',
    'SBIN': 'SBIN.NS',
    'BHARTIARTL': 'BHARTIARTL.NS',
    'KOTAKBANK': 'KOTAKBANK.NS',
    'BAJFINANCE': 'BAJFINANCE.NS',
    'LT': 'LT.NS',
    'WIPRO': 'WIPRO.NS',
    'AXISBANK': 'AXISBANK.NS',
    'TITAN': 'TITAN.NS',
    'ASIANPAINT': 'ASIANPAINT.NS',
    'MARUTI': 'MARUTI.NS',
    'SUNPHARMA': 'SUNPHARMA.NS'
}

# Function to get stock price
@st.cache_data(ttl=30)
def get_stock_price(symbol):
    """Get current stock price"""
    try:
        ticker = yf.Ticker(STOCKS[symbol])
        data = ticker.history(period="1d")
        if not data.empty:
            current = data['Close'].iloc[-1]
            open_price = data['Open'].iloc[-1]
            change = current - open_price
            change_pct = (change / open_price) * 100 if open_price != 0 else 0
            return {
                'price': round(current, 2),
                'change': round(change, 2),
                'change_pct': round(change_pct, 2)
            }
    except Exception as e:
        return None
    return None

# Function to analyze stock
def analyze_stock(symbol):
    """Generate trading signals"""
    try:
        ticker = yf.Ticker(STOCKS[symbol])
        hist = ticker.history(period="2mo")
        
        if hist.empty or len(hist) < 20:
            return None
        
        current = hist['Close'].iloc[-1]
        
        # Calculate EMAs
        ema20 = hist['Close'].ewm(span=20).mean().iloc[-1]
        ema50 = hist['Close'].ewm(span=50).mean().iloc[-1]
        
        # Calculate RSI
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1] if not rsi.empty else 50
        
        # Volume analysis
        volume_avg = hist['Volume'].rolling(window=20).mean().iloc[-1]
        volume_current = hist['Volume'].iloc[-1]
        volume_ratio = volume_current / volume_avg if volume_avg > 0 else 1
        
        # Support/Resistance
        support = hist['Low'].rolling(window=20).min().iloc[-1]
        resistance = hist['High'].rolling(window=20).max().iloc[-1]
        
        # Generate signal
        signal = "HOLD"
        confidence = 50
        reasons = []
        
        # Bullish signals
        bullish_score = 0
        if current > ema20:
            bullish_score += 20
            reasons.append("Above 20-day EMA")
        if current > ema50:
            bullish_score += 20
            reasons.append("Above 50-day EMA")
        if current_rsi < 40:
            bullish_score += 15
            reasons.append("Oversold")
        if volume_ratio > 1.2:
            bullish_score += 15
            reasons.append("High volume")
        if current > support * 1.03:
            bullish_score += 15
            reasons.append("Above support")
            
        # Bearish signals
        bearish_score = 0
        if current < ema20:
            bearish_score += 20
        if current < ema50:
            bearish_score += 20
        if current_rsi > 70:
            bearish_score += 20
            reasons.append("Overbought")
        if volume_ratio < 0.7:
            bearish_score += 10
        if current < resistance * 0.97:
            bearish_score += 15
            
        # Determine action
        if bullish_score >= bearish_score and bullish_score >= 60:
            signal = "BUY"
            confidence = min(bullish_score + 20, 95)
            stop_loss = round(support * 0.97, 2)
            target = round(resistance, 2)
        elif bearish_score > bullish_score and bearish_score >= 60:
            signal = "SELL"
            confidence = min(bearish_score + 20, 95)
            stop_loss = round(resistance * 1.03, 2)
            target = round(support, 2)
        else:
            signal = "HOLD"
            confidence = 50
            stop_loss = None
            target = None
            
        # Risk level
        if confidence >= 80:
            risk = "Low"
        elif confidence >= 60:
            risk = "Medium"
        else:
            risk = "High"
            
        return {
            'symbol': symbol,
            'action': signal,
            'price': round(current, 2),
            'confidence': confidence,
            'risk': risk,
            'stop_loss': stop_loss,
            'target': target,
            'rsi': round(current_rsi, 1),
            'volume': round(volume_ratio, 2),
            'reasons': reasons[:2]
        }
        
    except Exception as e:
        return None

# Market Overview Section
st.subheader("📊 Market Overview")

col1, col2 = st.columns(2)

with col1:
    # NIFTY 50
    try:
        nifty = yf.Ticker("^NSEI").history(period="1d")
        if not nifty.empty:
            nifty_price = nifty['Close'].iloc[-1]
            nifty_change = nifty['Close'].iloc[-1] - nifty['Open'].iloc[-1]
            nifty_pct = (nifty_change / nifty['Open'].iloc[-1]) * 100 if nifty['Open'].iloc[-1] != 0 else 0
            color = "price-up" if nifty_change > 0 else "price-down" if nifty_change < 0 else ""
            
            st.markdown(f"""
            <div class="metric-box">
                <h3 style="margin:0">NIFTY 50</h3>
                <h2 style="margin:10px 0">₹{nifty_price:.2f}</h2>
                <p class="{color}">{nifty_change:+.2f} ({nifty_pct:+.2f}%)</p>
            </div>
            """, unsafe_allow_html=True)
    except:
        st.markdown("""
        <div class="metric-box">
            <h3>NIFTY 50</h3>
            <p>Loading...</p>
        </div>
        """, unsafe_allow_html=True)

with col2:
    # BANK NIFTY
    try:
        bank = yf.Ticker("^NSEBANK").history(period="1d")
        if not bank.empty:
            bank_price = bank['Close'].iloc[-1]
            bank_change = bank['Close'].iloc[-1] - bank['Open'].iloc[-1]
            bank_pct = (bank_change / bank['Open'].iloc[-1]) * 100 if bank['Open'].iloc[-1] != 0 else 0
            color = "price-up" if bank_change > 0 else "price-down" if bank_change < 0 else ""
            
            st.markdown(f"""
            <div class="metric-box">
                <h3 style="margin:0">BANK NIFTY</h3>
                <h2 style="margin:10px 0">₹{bank_price:.2f}</h2>
                <p class="{color}">{bank_change:+.2f} ({bank_pct:+.2f}%)</p>
            </div>
            """, unsafe_allow_html=True)
    except:
        st.markdown("""
        <div class="metric-box">
            <h3>BANK NIFTY</h3>
            <p>Loading...</p>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# Watchlist Section
st.subheader("📋 My Watchlist")

# Add to watchlist
col1, col2 = st.columns([2, 1])
with col1:
    new_stock = st.selectbox("Select stock", list(STOCKS.keys()), label_visibility="collapsed")
with col2:
    if st.button("➕ Add", use_container_width=True):
        if new_stock not in st.session_state.watchlist:
            st.session_state.watchlist.append(new_stock)
            st.success(f"✅ Added {new_stock}")

# Display watchlist in 2 columns
cols = st.columns(2)
for i, symbol in enumerate(st.session_state.watchlist):
    with cols[i % 2]:
        price_data = get_stock_price(symbol)
        if price_data:
            color = "price-up" if price_data['change'] > 0 else "price-down" if price_data['change'] < 0 else ""
            
            # Remove button
            if st.button("❌", key=f"rm_{symbol}"):
                st.session_state.watchlist.remove(symbol)
                st.rerun()
            
            st.markdown(f"""
            <div class="stock-card">
                <div style="display: flex; justify-content: space-between;">
                    <h3 style="margin:0">{symbol}</h3>
                </div>
                <div style="display: flex; justify-content: space-between; margin-top: 10px;">
                    <h2 style="margin:0">₹{price_data['price']}</h2>
                    <p class="{color}" style="font-size: 16px;">{price_data['change']:+.2f} ({price_data['change_pct']:+.1f}%)</p>
                </div>
            </div>
            """, unsafe_allow_html=True)

st.markdown("---")

# Signals Section
st.subheader("🎯 Trading Signals")

if st.button("🔍 SCAN FOR SIGNALS", type="primary", use_container_width=True):
    with st.spinner("Analyzing stocks... Please wait..."):
        signals = []
        progress_bar = st.progress(0)
        
        for i, symbol in enumerate(st.session_state.watchlist):
            signal = analyze_stock(symbol)
            if signal and signal['action'] != "HOLD":
                signals.append(signal)
            progress_bar.progress((i + 1) / len(st.session_state.watchlist))
            time.sleep(0.5)
        
        st.session_state.signals = signals
        
        if signals:
            st.markdown(f'<p class="success-msg">✅ Found {len(signals)} trading signals!</p>', unsafe_allow_html=True)
        else:
            st.info("No strong signals found")

# Display signals
if st.session_state.signals:
    for signal in st.session_state.signals:
        card_class = "buy-card" if signal['action'] == "BUY" else "sell-card"
        conf_class = "high-conf" if signal['confidence'] >= 80 else "med-conf" if signal['confidence'] >= 60 else "low-conf"
        action_color = "#00ff00" if signal['action'] == "BUY" else "#ff0000"
        
        st.markdown(f"""
        <div class="signal-card {card_class}">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h2 style="margin:0">{signal['symbol']}</h2>
                <h2 style="color: {action_color}; margin:0">{signal['action']}</h2>
            </div>
            
            <div style="display: flex; justify-content: space-between; margin: 15px 0;">
                <div>
                    <p style="color: #888; margin:0">Price</p>
                    <h3 style="margin:5px 0">₹{signal['price']}</h3>
                </div>
                <div style="text-align: center;">
                    <p style="color: #888; margin:0">Confidence</p>
                    <span class="{conf_class}" style="margin-top:5px;">{signal['confidence']}%</span>
                </div>
                <div style="text-align: right;">
                    <p style="color: #888; margin:0">Risk</p>
                    <p style="margin:5px 0; color: {'#00ff00' if signal['risk'] == 'Low' else '#ffff00' if signal['risk'] == 'Medium' else '#ff0000'};">{signal['risk']}</p>
                </div>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 10px 0;">
                <div>
                    <p style="color: #888; margin:0">Stop Loss</p>
                    <p style="margin:5px 0; color: #ff0000;">₹{signal['stop_loss'] if signal['stop_loss'] else 'N/A'}</p>
                </div>
                <div>
                    <p style="color: #888; margin:0">Target</p>
                    <p style="margin:5px 0; color: #00ff00;">₹{signal['target'] if signal['target'] else 'N/A'}</p>
                </div>
            </div>
            
            <div style="display: flex; gap: 10px; margin-top: 10px;">
                <div style="background: #2a2c2f; padding: 5px 10px; border-radius: 15px;">
                    <small>RSI: {signal['rsi']}</small>
                </div>
                <div style="background: #2a2c2f; padding: 5px 10px; border-radius: 15px;">
                    <small>Vol: {signal['volume']}x</small>
                </div>
            </div>
            
            <div style="margin-top: 10px; font-size: 14px; color: #888;">
                {' • '.join(signal['reasons'])}
            </div>
        </div>
        """, unsafe_allow_html=True)

# Refresh button
st.markdown("---")
if st.button("🔄 Refresh Data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.caption("⚠️ Data updates every 30 seconds. Not financial advice.")
