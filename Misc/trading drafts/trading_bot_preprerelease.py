
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


def resume_positions_from_binance():
    try:
        account_info = client.get_account()
        balances = {a["asset"]: float(a["free"]) for a in account_info["balances"] if float(a["free"]) > 0.0001}

        positions = {}
        for asset, amount in balances.items():
            if asset == "USDC":
                continue  # skip the base coin
            symbol = f"{asset}USDC"
            try:
                price = float(client.get_symbol_ticker(symbol=symbol)["price"])
                positions[symbol] = {
                    "entry": price,
                    "qty": float(amount),
                    "timestamp": time.time()
                }
            except:
                continue  # skip symbols that aren't tradable
        print(f"[RESUME] Found {len(positions)} open position(s) from Binance balances.")
        return positions
    except Exception as e:
        print(f"[ERROR] Resuming from Binance failed: {e}")
        return {}

# Load positions on startup
positions = resume_positions_from_binance()
print(f"[RESUME] Resuming {len(positions)} open position(s) from previous session:")
for sym, pos in positions.items():
    print(f" ↪ {sym}: entry=${pos['entry']}, qty={pos['qty']}")

CUSTOM_SYMBOLS = ['BNBUSDC', 'BTCUSDC', 'ETHUSDC', 'XRPUSDC', 'XLMUSDC', 'LINKUSDC', 'LTCUSDC', 'TRXUSDC', 'ADAUSDC', 'NEOUSDC', 'ATOMUSDC', 'ALGOUSDC', 'DOGEUSDC', 'ONTUSDC', 'BCHUSDC', 'SOLUSDC', 'ARBUSDC', 'AVAXUSDC', 'DOTUSDC', 'INJUSDC', 'OPUSDC', 'ORDIUSDC', 'SUIUSDC', 'TIAUSDC', 'MANTAUSDC', 'BLURUSDC', 'ALTUSDC', 'SEIUSDC', 'JUPUSDC', 'FILUSDC', 'WLDUSDC', 'UNIUSDC', 'PIXELUSDC', 'STRKUSDC', 'PEPEUSDC', 'SHIBUSDC', 'NEARUSDC', 'FETUSDC', 'EURUSDC', 'BONKUSDC', 'FLOKIUSDC', 'PENDLEUSDC', 'BOMEUSDC', 'JTOUSDC', 'WIFUSDC', 'CKBUSDC', 'ENAUSDC', 'ETHFIUSDC', 'YGGUSDC', 'CFXUSDC', 'RUNEUSDC', 'SAGAUSDC', 'APTUSDC', 'GALAUSDC', 'STXUSDC', 'ICPUSDC', 'OMNIUSDC', 'TRBUSDC', 'ARKMUSDC', 'ARUSDC', 'BBUSDC', 'CRVUSDC', 'PEOPLEUSDC', 'REZUSDC', 'ENSUSDC', 'LDOUSDC', 'NOTUSDC', 'TNSRUSDC', 'ZKUSDC', 'ZROUSDC', 'IOUSDC', '1000SATSUSDC', 'RENDERUSDC', 'TONUSDC', 'DOGSUSDC', 'RAREUSDC', 'SLFUSDC', 'AAVEUSDC', 'POLUSDC', 'ACTUSDC', 'NEIROUSDC', 'PNUTUSDC', 'CATIUSDC', 'FDUSDUSDC', 'HBARUSDC', 'OMUSDC', 'RAYUSDC', 'TAOUSDC', 'APEUSDC', 'EIGENUSDC', 'MEMEUSDC', '1MBABYDOGEUSDC', 'CETUSUSDC', 'COWUSDC', 'DYDXUSDC', 'HMSTRUSDC', 'TURBOUSDC', 'KAIAUSDC', 'SANDUSDC', 'CHZUSDC', 'PYTHUSDC', 'RSRUSDC', 'WUSDC', 'XTZUSDC', 'ACXUSDC', 'ORCAUSDC', 'HIVEUSDC', 'IDEXUSDC', 'TLMUSDC', '1000CATUSDC', 'PENGUUSDC', 'BIOUSDC', 'MOVEUSDC', 'PHAUSDC', 'STEEMUSDC', 'USUALUSDC', 'AIXBTUSDC', 'CGPTUSDC', 'COOKIEUSDC', 'SUSDC', 'TRUMPUSDC', 'ANIMEUSDC', 'BERAUSDC', '1000CHEEMSUSDC', 'TSTUSDC', 'LAYERUSDC', 'CAKEUSDC', 'HEIUSDC', 'KAITOUSDC', 'SHELLUSDC', 'GPSUSDC', 'REDUSDC', 'CHESSUSDC', 'EGLDUSDC', 'OSMOUSDC', 'UTKUSDC', 'TUSDC', 'CVCUSDC', 'EURIUSDC', 'SYNUSDC', 'VELODROMEUSDC', 'DFUSDC', 'EPICUSDC', 'GMXUSDC', 'MKRUSDC', 'RPLUSDC', 'BMTUSDC', 'FORMUSDC', 'IOTAUSDC', 'JUVUSDC', 'THEUSDC', 'VANRYUSDC', 'NILUSDC', 'BEAMXUSDC', 'VANAUSDC', 'PARTIUSDC', 'MUBARAKUSDC', 'TUTUSDC', 'BANANAS31USDC', 'BROCCOLI714USDC', 'THETAUSDC', 'API3USDC', 'AUCTIONUSDC', 'BANANAUSDC', 'GUNUSDC', 'QNTUSDC', 'VETUSDC', 'ZENUSDC', 'BABYUSDC', 'ONDOUSDC', 'BIGTIMEUSDC', 'VIRTUALUSDC', 'KERNELUSDC', 'WCTUSDC', 'PAXGUSDC', 'ACHUSDC', 'GMTUSDC', 'HYPERUSDC', 'INITUSDC', 'SIGNUSDC', 'STOUSDC', 'ENJUSDC', 'SYRUPUSDC', 'KMNOUSDC', 'SXTUSDC', 'PUNDIXUSDC', 'NXPCUSDC', 'HAEDALUSDC', 'HUMAUSDC', 'AUSDC', 'SOPHUSDC', 'RESOLVUSDC', 'HOMEUSDC', 'FLUXUSDC', 'MASKUSDC', 'SUSHIUSDC', 'SPKUSDC']
INTERVAL = Client.KLINE_INTERVAL_1MINUTE
MAX_OPEN_POSITIONS = 3
MIN_TRADE_USD = 5.1
RESERVE = 0.50
PAPER_MODE = False  # Switch to True for fallback on failed trades

def get_tradeable_symbols(symbol_list):
    valid = []
    for symbol in symbol_list:
        try:
            client.create_test_order(
                symbol=symbol,
                side='BUY',
                type='MARKET',
                quoteOrderQty=5.1
            )
            valid.append(symbol)
        except Exception as e:
            print(f"[SKIP] {symbol} is not tradable: {e}")
    return valid

ALL_SYMBOLS = get_tradeable_symbols(CUSTOM_SYMBOLS)
def get_usdt_balance():
    try:
        balances = client.get_asset_balance(asset='USDC')
        return float(balances['free'])
    except Exception as e:
        print(f"[ERROR] Could not fetch USDC balance: {e}")
        return 0.0

def fetch_balances():
    assets = ['USDC', 'BUSD', 'BTC', 'ETH']
    result = {}
    try:
        for asset in assets:
            data = client.get_asset_balance(asset=asset)
            result[asset] = float(data['free'])
    except Exception as e:
        print(f"[ERROR] Failed to fetch balances: {e}")
    return result

balance = {'usd': fetch_balances().get('USDC', 0.0)}
print(f"[INFO] Initial balances: " + ", ".join([f"{a}: {v:.4f}" for a, v in fetch_balances().items()]))

print(f"[INFO] Live USDC balance: ${balance['usd']:.2f}")

SYMBOLS = []

def get_active_symbols():
    usable = balance['usd'] - RESERVE
    max_coins = max(1, int(usable // MIN_TRADE_USD))
    active = ALL_SYMBOLS[:min(max_coins, len(ALL_SYMBOLS))]
    print(f"[INFO] Active coins: {active} | Budget per coin: ${usable/len(active):.2f}")
    return active

positions = {}
trade_log = []
symbol_pnls = {}

def calculate_trade_amount():
    usable = balance['usd'] - RESERVE
    return round(usable / len(SYMBOLS), 2) if len(SYMBOLS) > 0 else 0

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
    print(f"[DEBUG] Attempting to BUY {symbol}")
    trade_amount = calculate_trade_amount()
    if trade_amount <= 0:
        print(f"[SKIP] Not enough usable balance for {symbol}. Wanted: ${trade_amount:.2f}")
        return None

    price = get_latest_price(symbol)
    qty = (trade_amount / price) * (1 - 0.001)
    if qty <= 0:
        print(f"[SKIP] {symbol} results in zero qty. Amount: ${trade_amount:.2f}, Price: ${price:.4f}")
        return None

    try:
        if PAPER_MODE:
            print(f"[PAPER] Buying {symbol} @ ${price:.4f} with ${trade_amount}")
            balance['usd'] -= trade_amount
            return {'entry': price, 'qty': qty, 'timestamp': time.time()}
        else:
            order = client.order_market_buy(symbol=symbol, quoteOrderQty=trade_amount)
            price = float(order['fills'][0]['price'])
            qty = float(order['executedQty'])
            balance['usd'] -= trade_amount
            return {'entry': price, 'qty': qty, 'timestamp': time.time()}
    except BinanceAPIException as e:
        print(f"Buy error on {symbol}: {e}")
        return None

def sell(symbol, qty):
    print(f"[DEBUG] Attempting to SELL {symbol} with qty {qty}")
    try:
        price = get_latest_price(symbol)
        if PAPER_MODE:
            print(f"[PAPER] Selling {symbol} @ ${price:.4f}")
            return price
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
    global SYMBOLS, symbol_pnls
    SYMBOLS = get_active_symbols()
    symbol_pnls = {s: 0 for s in SYMBOLS}
    while True:
        for symbol in SYMBOLS:
            try:
                prices = get_recent_close(symbol)
                print(f"[DEBUG] Checking BUY conditions for {symbol}")
                if len(positions) < MAX_OPEN_POSITIONS and symbol not in positions and should_enter(prices):
                    pos = buy(symbol)
                    if pos:
                        positions[symbol] = pos
                elif symbol in positions:
                    current_price = get_latest_price(symbol)
                    entry = positions[symbol]['entry']
                    qty = positions[symbol]['qty']
                    print(f"[DEBUG] Checking SELL conditions for {symbol} at price {current_price:.4f}")
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

st.set_page_config(layout="wide", page_title="📊 Aggressive Mode Bot")
st.title("🧪 Aggressive Trading Bot with Paper Mode")

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
        # st.subheader("📄 Trade History")
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
