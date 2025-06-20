
import streamlit as st
import time
import threading
import pandas as pd
import numpy as np
from binance.client import Client
from binance.exceptions import BinanceAPIException
from datetime import datetime
from secret import API_KEY, API_SECRET

client = Client(API_KEY, API_SECRET)

SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT']
INTERVAL = Client.KLINE_INTERVAL_1MINUTE
MAX_OPEN_POSITIONS = 3

positions = {}
trade_log = []
symbol_pnls = {s: 0 for s in SYMBOLS}
balance = {'usd': 29.4}

def calculate_trade_amount():
    reserve = 5
    usable = max(0, balance['usd'] - reserve)
    per_trade = usable / len(SYMBOLS)
    return round(per_trade * 0.95, 2) if per_trade > 5 else 0

def get_latest_price(symbol):
    return float(client.get_symbol_ticker(symbol=symbol)['price'])

def get_recent_close(symbol, minutes=5):
    candles = client.get_klines(symbol=symbol, interval=INTERVAL, limit=minutes)
    return [float(c[4]) for c in candles]

def should_enter(prices):
    if len(prices) < 3:
        return False
    changes = np.diff(prices)
    if np.all(changes == 0):
        return False
    return prices[-1] > prices[0] and prices[-1] > max(prices[:-1])

def buy(symbol):
    trade_amount = calculate_trade_amount()
    if trade_amount <= 0:
        print(f"Skipping {symbol} - not enough usable balance.")
        return None
    try:
        order = client.order_market_buy(symbol=symbol, quoteOrderQty=trade_amount)
        price = float(order['fills'][0]['price'])
        qty = float(order['executedQty'])
        balance['usd'] -= trade_amount
        return {'entry': price, 'qty': qty, 'timestamp': time.time()}
    except BinanceAPIException as e:
        print(f"Buy error on {symbol}: {e}")
        return None

def sell(symbol, qty):
    try:
        order = client.order_market_sell(symbol=symbol, quantity=qty)
        price = float(order['fills'][0]['price'])
        return price
    except BinanceAPIException as e:
        print(f"Sell error on {symbol}: {e}")
        return None

def log_trade(symbol, entry, exit, qty):
    pnl = (exit - entry) * qty
    symbol_pnls[symbol] += pnl
    balance['usd'] += (entry + pnl * qty)
    trade = {
        'Time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'Symbol': symbol,
        'Entry': round(entry, 4),
        'Exit': round(exit, 4),
        'Qty': round(qty, 6),
        'PnL $': round(pnl, 2)
    }
    trade_log.append(trade)

def get_price_chart(symbol, interval='1m', lookback='30 minutes ago UTC'):
    try:
        candles = client.get_historical_klines(symbol, Client.KLINE_INTERVAL_1MINUTE, lookback)
        df = pd.DataFrame(candles, columns=[
            "time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base_volume", "taker_buy_quote_volume", "ignore"
        ])
        df["time"] = pd.to_datetime(df["time"], unit='ms')
        df.set_index("time", inplace=True)
        df = df.astype(float)
        return df[["close"]]
    except Exception as e:
        print(f"Error fetching chart for {symbol}: {e}")
        return pd.DataFrame()

def trading_loop():
    while True:
        for symbol in SYMBOLS:
            try:
                prices = get_recent_close(symbol)
                if len(positions) < MAX_OPEN_POSITIONS and symbol not in positions and should_enter(prices):
                    pos = buy(symbol)
                    if pos:
                        positions[symbol] = pos
                elif symbol in positions:
                    current_price = get_latest_price(symbol)
                    entry = positions[symbol]['entry']
                    qty = positions[symbol]['qty']
                    if current_price >= entry * 1.01 or current_price <= entry * 0.995:
                        exit_price = sell(symbol, qty)
                        if exit_price:
                            log_trade(symbol, entry, exit_price, qty)
                            del positions[symbol]
            except Exception as e:
                print(f"Error with {symbol}: {e}")
        time.sleep(30)

bot_thread = threading.Thread(target=trading_loop, daemon=True)
bot_thread.start()

st.set_page_config(layout="wide", page_title="📊 Smarter Crypto Bot")
st.title("🛡️ Smarter & Safer Trading Bot Dashboard")

balance_area = st.empty()
positions_area = st.empty()
log_area = st.empty()

while True:
    balance_area.markdown(f"### 💰 Current Balance: **${balance['usd']:.2f}**")

    if positions:
        st.subheader("📌 Active Positions")
        pos_df = pd.DataFrame([
            {
                "Symbol": s,
                "Entry": f"${p['entry']:.4f}",
                "Qty": round(p['qty'], 6),
                "Held Since": datetime.fromtimestamp(p['timestamp']).strftime("%H:%M:%S")
            } for s, p in positions.items()
        ])
        positions_area.dataframe(pos_df, use_container_width=True)
    else:
        positions_area.info("No active positions")

    if trade_log:
        st.subheader("📄 Trade History")
        log_df = pd.DataFrame(trade_log)
        log_area.dataframe(log_df, use_container_width=True)

    st.subheader("🏆 Per-Coin Profit Leaderboard")
    sorted_pnls = sorted(symbol_pnls.items(), key=lambda x: x[1], reverse=True)
    leaderboard_df = pd.DataFrame(sorted_pnls, columns=["Symbol", "Total PnL ($)"])
    st.dataframe(leaderboard_df, use_container_width=True)

    st.subheader("📉 Live Price Charts")
    for symbol in SYMBOLS:
        df = get_price_chart(symbol)
        if not df.empty:
            st.markdown(f"### {symbol}")
            st.line_chart(df.rename(columns={"close": "Price"}))
        else:
            st.warning(f"Failed to load chart for {symbol}")

    time.sleep(10)
