import time
import joblib
import numpy as np
import pandas as pd
from binance.client import Client
from binance.enums import *
from sklearn.preprocessing import StandardScaler
import ccxt
from secret import API_KEY, API_SECRET

# Load trained model
model = joblib.load("model.pkl")
scaler = joblib.load("scaler.pkl")

# Binance keys (use environment vars in production)
client = Client(API_KEY, API_SECRET)

symbol = 'BTC/USDT'
qty = 0.001  # amount to buy/sell

def fetch_binance_ohlcv():
    binance = ccxt.binance()
    bars = binance.fetch_ohlcv(symbol, timeframe='1m', limit=60)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    return df

def get_features(df):
    df['return'] = df['close'].pct_change().fillna(0)
    df['ma_7'] = df['close'].rolling(7).mean()
    df['ma_21'] = df['close'].rolling(21).mean()
    df['rsi'] = compute_rsi(df['close'])
    df = df.dropna()
    return df[['return', 'ma_7', 'ma_21', 'rsi']].values[-1:]

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def execute_trade(signal):
    side = SIDE_BUY if signal == 1 else SIDE_SELL
    print(f"Placing {side} order for {symbol}...")
    try:
        order = client.create_order(
            symbol=symbol.replace("/", ""),
            side=side,
            type=ORDER_TYPE_MARKET,
            quantity=qty
        )
        print(f"Trade executed: {order}")
    except Exception as e:
        print(f"Error placing order: {e}")

def main_loop():
    df = fetch_binance_ohlcv()
    x = get_features(df)
    x_scaled = scaler.transform(x)
    prob = model.predict_proba(x_scaled)[0]
    print(f"Signal confidence: BUY={prob[1]:.2f}, SELL={prob[0]:.2f}")
    if prob[1] > 0.7:
        execute_trade(1)
    elif prob[0] > 0.7:
        execute_trade(0)

if __name__ == "__main__":
    while True:
        try:
            main_loop()
        except Exception as e:
            print(f"Error in loop: {e}")
        time.sleep(60)  # every minute
