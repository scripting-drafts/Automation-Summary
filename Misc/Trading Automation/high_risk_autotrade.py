import yaml
from binance.client import Client
from binance.exceptions import BinanceAPIException
import threading
import time
from datetime import datetime
import json, os, decimal, csv, sys

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

from secret import API_KEY, API_SECRET, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

BASE_ASSET = 'USDC'
TRADING_INTERVAL = 2
SELL_GAIN = 1.002       # +0.2% profit triggers sell
SELL_LOSS = 0.9995      # -0.05% loss triggers sell

client = Client(API_KEY, API_SECRET)
balance = {'usd': 0.0}
positions = {}
TRADE_LOG_FILE = "trades_detailed.csv"
YAML_SYMBOLS_FILE = "symbols.yaml"

def pct_change(klines):
    if len(klines) < 2: return 0
    prev_close = float(klines[0][4])
    last_close = float(klines[1][4])
    return (last_close - prev_close) / prev_close * 100

def has_recent_momentum(symbol, min_1m=0.3, min_5m=0.6, min_15m=1.0):
    try:
        klines_1m = client.get_klines(symbol=symbol, interval='1m', limit=2)
        klines_5m = client.get_klines(symbol=symbol, interval='5m', limit=2)
        klines_15m = client.get_klines(symbol=symbol, interval='15m', limit=2)
        return (
            pct_change(klines_1m) > min_1m and
            pct_change(klines_5m) > min_5m and
            pct_change(klines_15m) > min_15m
        )
    except Exception:
        return False

def auto_sell_momentum_positions(min_profit=1.0, trailing_stop=0.6, max_hold_time=1200):
    now = time.time()
    for symbol, pos in list(positions.items()):
        entry = float(pos['entry'])
        qty = float(pos['qty'])
        trade_time = float(pos.get('trade_time', now))
        current_price = get_latest_price(symbol)
        pnl_pct = (current_price - entry) / entry * 100
        held_for = now - trade_time

        if 'max_price' not in pos:
            pos['max_price'] = entry
        pos['max_price'] = max(pos['max_price'], current_price)
        trail_pct = (current_price - pos['max_price']) / pos['max_price'] * 100

        # Only start trailing stop after min_profit
        if pnl_pct >= min_profit and trail_pct <= -trailing_stop:
            # Take profit if price drops from top
            sell(symbol, qty)
            del positions[symbol]
        elif held_for >= max_hold_time:
            # Time exit, don't stay stuck forever
            sell(symbol, qty)
            del positions[symbol]


def get_yaml_ranked_momentum(
        limit=3, 
        min_marketcap=100_000, 
        min_volume=100_000, 
        min_volatility=0.002):
    stats = load_symbol_stats()
    if not stats:
        return []
    tickers = {t['symbol']: t for t in client.get_ticker() if t['symbol'] in stats}
    candidates = []
    for symbol, s in stats.items():
        ticker = tickers.get(symbol)
        if not ticker:
            continue
        mc = s.get("market_cap", 0) or 0
        vol = s.get("volume_1d", 0) or 0
        vola = s.get("volatility", {}).get("1d", 0) or 0
        price_change = float(ticker.get('priceChangePercent', 0))
        # Filters
        if mc < min_marketcap or vol < min_volume or vola < min_volatility:
            continue
        if not has_recent_momentum(symbol):
            continue
        # Calculate the momentum score (sum of recent % changes)
        k1m = client.get_klines(symbol=symbol, interval='1m', limit=2)
        k5m = client.get_klines(symbol=symbol, interval='5m', limit=2)
        k15m = client.get_klines(symbol=symbol, interval='15m', limit=2)
        k1h = client.get_klines(symbol=symbol, interval='1h', limit=2)
        momentum_score = (
            pct_change(k1m)
            + pct_change(k5m) * 1.5
            + pct_change(k15m) * 2
            + pct_change(k1h)
        )
        candidates.append({
            "symbol": symbol,
            "market_cap": mc,
            "volume": vol,
            "volatility": vola,
            "price_change": price_change,
            "momentum_score": momentum_score,
        })

    ranked = sorted(
        candidates, 
        key=lambda x: (x["momentum_score"], x["market_cap"], x["volume"]), 
        reverse=True
    )
    return [x["symbol"] for x in ranked[:limit]]



#----------Firstly ommited methods----------------#
def get_bot_state():
    if not os.path.exists("bot_state.json"):
        return {"balance": 0, "positions": {}, "paused": False, "log": [], "actions": []}
    with open("bot_state.json", "r") as f:
        return json.load(f)

def save_bot_state(state):
    with open("bot_state.json", "w") as f:
        json.dump(state, f)

def sync_state():
    state = get_bot_state()
    state["balance"] = balance['usd']
    state["positions"] = positions
    state["log"] = trade_log[-100:] if 'trade_log' in globals() else []
    save_bot_state(state)

def process_actions():
    state = get_bot_state()
    actions = state.get("actions", [])
    performed = []
    for act in actions:
        if act["type"] == "rotate":
            rotate_positions()
            performed.append(act)
        elif act["type"] == "invest":
            invest_momentum()
            performed.append(act)
        elif act["type"] == "sell_all":
            sell_everything()
            performed.append(act)
    state["actions"] = [a for a in actions if a not in performed]
    save_bot_state(state)

def queue_action(action):
    state = get_bot_state()
    state.setdefault("actions", []).append({"type": action})
    save_bot_state(state)

def rotate_positions():
    sold = []
    for symbol in list(positions.keys()):
        qty = positions[symbol]["qty"]
        entry = positions[symbol]["entry"]
        trade_time = positions[symbol]["trade_time"]
        sell_qty = round_qty(symbol, qty)
        if sell_qty == 0 or qty == 0:
            del positions[symbol]
            continue
        try:
            exit_price, fee, tax = sell(symbol, qty)
            if exit_price:
                log_trade(symbol, entry, exit_price, qty, trade_time, time.time(), fee, tax)
                del positions[symbol]
            else:
                sold.append(symbol)
        except Exception as e:
            sold.append(symbol)
    sync_investments_with_binance()
    time.sleep(2)
    invest_momentum()
    sync_investments_with_binance()
    return sold

def sell_everything():
    results = []
    for symbol in list(positions.keys()):
        qty = positions[symbol]['qty']
        entry = positions[symbol]['entry']
        trade_time = positions[symbol].get("trade_time", time.time())
        exit_price, fee, tax = sell(symbol, qty)
        exit_time = time.time()
        if exit_price:
            log_trade(symbol, entry, exit_price, qty, trade_time, exit_time, fee, tax, action="sell")
            results.append((symbol, exit_price))
            del positions[symbol]
    return results

def auto_sell_pnl_positions(target_pnl=11.0, stop_loss=0.2, trailing_stop=0.8, max_hold_time=3600):
    now = time.time()
    for symbol, pos in list(positions.items()):
        try:
            entry = float(pos['entry'])
            qty = float(pos['qty'])
            trade_time = float(pos.get('trade_time', now))
            sell_qty = round_qty(symbol, qty)
            min_notional = min_notional_for(symbol)
            current_price = get_latest_price(symbol)
            notional = sell_qty * current_price
            if sell_qty == 0 or qty == 0 or notional < min_notional:
                del positions[symbol]
                continue
            pnl_pct = (current_price - entry) / entry * 100
            held_for = now - trade_time
            if 'max_price' not in pos:
                pos['max_price'] = entry
            pos['max_price'] = max(pos['max_price'], current_price)
            trail_pct = (current_price - pos['max_price']) / pos['max_price'] * 100
            should_sell = False
            if pnl_pct >= target_pnl or pnl_pct <= -stop_loss or trail_pct <= -trailing_stop or held_for >= max_hold_time:
                should_sell = True
            if should_sell:
                exit_price, fee, _ = sell(symbol, sell_qty)
                exit_time = time.time()
                tax = estimate_trade_tax(entry, exit_price, sell_qty, trade_time, exit_time)
                log_trade(symbol, entry, exit_price, sell_qty, trade_time, exit_time, fee, tax, action="sell")
                del positions[symbol]
        except Exception as e:
            continue

def estimate_trade_tax(entry, exit_price, qty, trade_time, exit_time):
    if exit_price > entry:
        return abs(exit_price - entry) * qty * 0.002
    return 0

def log_trade(symbol, entry, exit_price, qty, trade_time, exit_time, fees=0, tax=0, action="sell"):
    pnl = (exit_price - entry) * qty if action == "sell" else 0
    pnl_pct = ((exit_price - entry) / entry * 100) if action == "sell" and entry != 0 else 0
    duration_sec = int(exit_time - trade_time) if action == "sell" else 0
    trade = {
        'Time': datetime.fromtimestamp(trade_time).strftime("%Y-%m-%d %H:%M:%S"),
        'Action': action,
        'Symbol': symbol,
        'Entry': round(entry, 8),
        'Exit': round(exit_price, 8),
        'Qty': round(qty, 8),
        'PnL $': round(pnl, 8),
        'PnL %': round(pnl_pct, 3),
        'Duration (s)': duration_sec,
        'Fees': round(fees, 8),
        'Tax': round(tax, 8)
    }
    try:
        file_exists = os.path.isfile(TRADE_LOG_FILE)
        with open(TRADE_LOG_FILE, "a", newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(trade.keys()))
            if not file_exists:
                writer.writeheader()
            writer.writerow(trade)
    except Exception as e:
        print(f"[LOG ERROR] {e}")

def too_many_positions():
    return len(positions) > 10

def market_is_risky():
    return False

def sell(symbol, qty):
    try:
        sell_qty = round_qty(symbol, qty)
        if sell_qty == 0:
            return None, 0, 0
        order = client.order_market_sell(symbol=symbol, quantity=sell_qty)
        price = float(order['fills'][0]['price'])
        fee = sum(float(f['commission']) for f in order['fills']) if "fills" in order else 0
        return price, fee, 0
    except BinanceAPIException as e:
        print(f"[SELL ERROR] {symbol}: {e}")
        return None, 0, 0
# -----------------------------------------------------------

def sync_investments_with_binance():
    try:
        account_info = client.get_account()
        # Keep ALL nonzero assets except base asset (USDC)
        balances = {
            a["asset"]: float(a["free"])
            for a in account_info["balances"]
            if float(a["free"]) > 0.0001 and a["asset"] != BASE_ASSET
        }
        new_positions = {}
        for asset, amount in balances.items():
            symbol = f"{asset}{BASE_ASSET}"
            try:
                price = float(client.get_symbol_ticker(symbol=symbol)["price"])
                new_positions[symbol] = {
                    "entry": price,  # For new syncs, "entry" is current price, unless you have historical
                    "qty": amount,
                    "timestamp": time.time(),
                    "trade_time": time.time()
                }
            except Exception:
                continue
        positions.clear()
        positions.update(new_positions)
        print("[INFO] Synced investments with real Binance balances.")
    except Exception as e:
        print(f"[SYNC ERROR] Could not sync investments with Binance: {e}")


sync_investments_with_binance()

def resume_positions_from_binance():
    try:
        account_info = client.get_account()
        balances = {
            a["asset"]: float(a["free"])
            for a in account_info["balances"]
            if float(a["free"]) > 0.0001 and a["asset"] != BASE_ASSET
        }
        resumed = {}
        for asset, amount in balances.items():
            symbol = f"{asset}{BASE_ASSET}"
            try:
                price = float(client.get_symbol_ticker(symbol=symbol)["price"])
                resumed[symbol] = {
                    "entry": price,
                    "qty": amount,
                    "timestamp": time.time(),
                    "trade_time": time.time()
                }
            except:
                continue
        return resumed
    except Exception as e:
        return {}

# --- YAML-based gainers selection ---
def load_symbol_stats():
    try:
        with open(YAML_SYMBOLS_FILE, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"[YAML ERROR] Could not read {YAML_SYMBOLS_FILE}: {e}")
        return {}

def get_yaml_ranked_gainers(limit=10, min_marketcap=100_000, min_volume=100_000, min_volatility=0.001):
    stats = load_symbol_stats()
    if not stats:
        return []
    tickers = {t['symbol']: t for t in client.get_ticker() if t['symbol'] in stats}
    candidates = []
    for symbol, s in stats.items():
        ticker = tickers.get(symbol)
        if not ticker:
            continue
        mc = s.get("market_cap", 0) or 0
        vol = s.get("volume_1d", 0) or 0
        vola = s.get("volatility", {}).get("1d", 0) or 0
        price_change = float(ticker.get('priceChangePercent', 0))
        if mc < min_marketcap or vol < min_volume or vola < min_volatility:
            continue
        candidates.append({
            "symbol": symbol,
            "market_cap": mc,
            "volume": vol,
            "volatility": vola,
            "price_change": price_change
        })
    ranked = sorted(
        candidates,
        key=lambda x: (x["market_cap"], x["price_change"], x["volatility"], x["volume"]),
        reverse=True
    )
    return [x["symbol"] for x in ranked[:limit]]

# -- [All your unchanged code is here, not pasted to save space] --
# -- See your full file above for the implementation of sell, buy, telegram, etc. --

import math

def place_buy_order(symbol, usd_amount):
    # Get the latest price for the symbol
    price = float(client.get_symbol_ticker(symbol=symbol)['price'])
    # Get symbol info to determine min quantity and step size
    info = client.get_symbol_info(symbol)
    step_size = None
    min_qty = None
    for f in info['filters']:
        if f['filterType'] == 'LOT_SIZE':
            step_size = float(f['stepSize'])
            min_qty = float(f['minQty'])
            break
    if step_size is None:
        raise Exception(f"Could not fetch step size for {symbol}")

    # Calculate quantity
    quantity = usd_amount / price
    # Round DOWN to the nearest allowed step
    precision = int(round(-math.log(step_size, 10), 0))
    quantity = math.floor(quantity * 10**precision) / 10**precision

    # Ensure quantity meets the minimum
    if quantity < min_qty:
        print(f"Calculated quantity {quantity} is less than min_qty {min_qty} for {symbol}")
        return None

    try:
        order = client.create_order(
            symbol=symbol,
            side='BUY',
            type='MARKET',
            quantity=quantity
        )
        print(f"[REAL TRADE] Bought {quantity} {symbol} (~${usd_amount:.2f})")
        return order
    except Exception as e:
        print(f"Order failed for {symbol}: {e}")
        return None

# --- CHANGED: refresh_symbols to use YAML ---
def refresh_symbols():
    global SYMBOLS
    SYMBOLS = get_yaml_ranked_momentum(3)

def get_position(symbol):
    # Example: Query your portfolio for the current holding
    # Replace this with your real portfolio lookup
    portfolio = {
        "BTCUSDC": 100,  # Example: $100 in BTCUSDC
        "ETHUSDC": 50,
    }
    return portfolio.get(symbol, 0)

import random

def get_momentum_score(symbol):
    # Example: Return a random trend score between 1 (mild) and 3 (hot)
    # Replace with your real momentum scoring logic!
    return random.uniform(1, 3)


def calculate_investment_amount(symbol, position, trending_score):
    base_amount = 10  # How much you usually invest per entry, in USD
    max_pyramid = 3    # Allow up to 3x base amount in total

    max_investment = base_amount * max_pyramid

    # Scale investment: If trending_score=1, invest base_amount. If 3, invest 3x more (if room).
    desired_position = min(base_amount * trending_score, max_investment)
    add_amount = desired_position - position

    # Don't add negative or tiny amounts
    if add_amount < 10:  # minimum increment
        return 0
    return add_amount



def invest_in_symbol(symbol):
    position = get_position(symbol)  # e.g., return current $ or None/0 if none
    trending_score = get_momentum_score(symbol)  # Optional: how hot is it?

    # Decide how much to invest/re-invest
    add_amount = calculate_investment_amount(symbol, position, trending_score)
    if add_amount <= 0:
        print(f"No additional investment for {symbol}.")
        return

    try:
        order = place_buy_order(symbol, add_amount)
        print(f"Invested additional ${add_amount} in {symbol}: {order}")
    except Exception as e:
        print(f"Failed to invest in {symbol}: {e}")

def invest_in_symbols(symbols):
    for symbol in symbols:
        invest_in_symbol(symbol)

def invest_momentum():
    sync_investments_with_binance()
    refresh_symbols()
    symbols = get_yaml_ranked_momentum(limit=3)
    invest_in_symbols(symbols)


def invest_gainers(gainers_sorted):
    fetch_usdc_balance()   # Always refresh before investing
    usdc = balance['usd']
    if usdc < 1 or not gainers_sorted:
        print("[INFO] No available USDC to invest or gainers list is empty.")
        return

    print("[INFO] Top gainers (sorted):", gainers_sorted)

    # Diversify by splitting available USDC as much as possible
    for n in range(len(gainers_sorted), 0, -1):
        selected = gainers_sorted[:n]
        amount_per_coin = usdc / n
        affordable = []
        for symbol in selected:
            min_notional = min_notional_for(symbol)
            if amount_per_coin < min_notional:
                print(f"[SKIP] {symbol}: Not enough USDC (${amount_per_coin:.2f}) for min_notional (${min_notional:.2f}).")
                continue
            affordable.append(symbol)
        if affordable:
            print(f"[INFO] Diversifying into {len(affordable)} gainers, ${amount_per_coin:.2f} per coin.")
            for symbol in affordable:
                fetch_usdc_balance()   # Always fetch before each buy!
                usdc = balance['usd']
                if usdc < min_notional_for(symbol):
                    print(f"[SKIP] {symbol}: Insufficient USDC (${usdc:.2f}) for min_notional (${min_notional_for(symbol):.2f}).")
                    continue
                print(f"[DEBUG] Attempting to buy {symbol}: trade_amount=${amount_per_coin:.2f}, min_notional=${min_notional_for(symbol):.2f}")
                result = buy(symbol, amount=amount_per_coin)
                if not result:
                    print(f"[BUY ERROR] {symbol}: Buy failed, refreshing USDC balance and skipping.")
                    fetch_usdc_balance()
                else:
                    print(f"[INFO] Bought {symbol} for ${amount_per_coin:.2f}")
            return  # Perform only the largest affordable split per round

    # Fallback: try with all USDC on top gainers in order
    for symbol in gainers_sorted:
        min_notional = min_notional_for(symbol)
        fetch_usdc_balance()
        usdc = balance['usd']
        if usdc < min_notional:
            print(f"[SKIP] {symbol}: Not enough USDC (${usdc:.2f}) for min_notional (${min_notional:.2f}).")
            continue
        print(f"[INFO] Attempting to buy {symbol} with all available USDC (${usdc:.2f})...")
        result = buy(symbol, amount=usdc)
        if not result:
            print(f"[BUY ERROR] {symbol}: Buy failed, refreshing USDC balance and skipping.")
            fetch_usdc_balance()
        else:
            print(f"[INFO] Bought {symbol} for ${usdc:.2f}")
            return

    print("[INFO] Buy failed for all affordable gainers. Waiting for next opportunity.")

def fetch_usdc_balance():
    """
    Updates global `balance['usd']` with the true free (unlocked) USDC on Binance.
    """
    try:
        asset_info = client.get_asset_balance(asset="USDC")
        free = float(asset_info['free'])
        balance['usd'] = free
        print(f"[DEBUG] Live USDC balance: {free}")
    except Exception as e:
        print(f"[ERROR] Fetching USDC balance: {e}")
        balance['usd'] = 0

# --- CHANGED: invest_gainers now uses YAML gainers ---
def invest_gainers():
    sync_investments_with_binance()
    refresh_symbols()
    gainers = get_yaml_ranked_gainers(limit=10)
    invest_momentum()


def log_trade(symbol, entry, exit_price, qty, trade_time, exit_time, fees=0, tax=0, action="sell"):
    pnl = (exit_price - entry) * qty if action == "sell" else 0
    pnl_pct = ((exit_price - entry) / entry * 100) if action == "sell" and entry != 0 else 0
    duration_sec = int(exit_time - trade_time) if action == "sell" else 0

    trade = {
        'Time': datetime.fromtimestamp(trade_time).strftime("%Y-%m-%d %H:%M:%S"),
        'Action': action,
        'Symbol': symbol,
        'Entry': round(entry, 8),
        'Exit': round(exit_price, 8),
        'Qty': round(qty, 8),
        'PnL $': round(pnl, 8),
        'PnL %': round(pnl_pct, 3),
        'Duration (s)': duration_sec,
        'Fees': round(fees, 8),
        'Tax': round(tax, 8)
    }
    trade_log.append(trade)
    try:
        file_exists = os.path.isfile(TRADE_LOG_FILE)
        with open(TRADE_LOG_FILE, "a", newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(trade.keys()))
            if not file_exists:
                writer.writeheader()
            writer.writerow(trade)
    except Exception as e:
        print(f"[LOG ERROR] {e}")

def auto_sell_momentum_positions(min_profit=1.0, trailing_stop=0.6, max_hold_time=900):
    # min_profit: minimum profit (%) before trailing stop activates
    # trailing_stop: trailing stop (% below max price after min_profit)
    # max_hold_time: sell after 15 minutes if not sold
    now = time.time()
    for symbol, pos in list(positions.items()):
        try:
            entry = float(pos['entry'])
            qty = float(pos['qty'])
            trade_time = float(pos.get('trade_time', now))
            current_price = get_latest_price(symbol)
            pnl_pct = (current_price - entry) / entry * 100
            held_for = now - trade_time

            if 'max_price' not in pos:
                pos['max_price'] = entry
            pos['max_price'] = max(pos['max_price'], current_price)
            trail_pct = (current_price - pos['max_price']) / pos['max_price'] * 100

            should_sell = False
            reason = ""
            if pnl_pct >= min_profit and trail_pct <= -trailing_stop:
                should_sell = True
                reason = f"Trailing stop: profit {pnl_pct:.2f}%, now {trail_pct:.2f}% from high."
            elif held_for >= max_hold_time:
                should_sell = True
                reason = f"Timed exit after {held_for/60:.1f} minutes."

            if should_sell:
                exit_price, fee, _ = sell(symbol, qty)
                exit_time = time.time()
                tax = estimate_trade_tax(entry, exit_price, qty, trade_time, exit_time)
                log_trade(
                    symbol=symbol,
                    entry=entry,
                    exit_price=exit_price,
                    qty=qty,
                    trade_time=trade_time,
                    exit_time=exit_time,
                    fees=fee,
                    tax=tax,
                    action="sell"
                )
                print(f"[MOMENTUM SELL] {symbol}: {reason}")
                del positions[symbol]
        except Exception as e:
            print(f"[AUTO-SELL ERROR] {symbol}: {e}")


def get_bot_state():
    if not os.path.exists("bot_state.json"):
        return {"balance": 0, "positions": {}, "paused": False, "log": [], "actions": []}
    with open("bot_state.json", "r") as f:
        return json.load(f)
    
def save_bot_state(state):
    with open("bot_state.json", "w") as f:
        json.dump(state, f)

def load_trade_history():
    log = []
    if os.path.exists(TRADE_LOG_FILE):
        try:
            with open(TRADE_LOG_FILE, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    log.append(row)
        except Exception as e:
            print(f"[LOAD TRADE ERROR] {e}")
    return log

trade_log = load_trade_history()

def sync_state():
    state = get_bot_state()
    state["balance"] = balance['usd']
    state["positions"] = positions
    state["log"] = trade_log[-100:]
    save_bot_state(state)

def get_1h_percent_change(symbol):
    # Get last 2 hourly candles
    klines = client.get_klines(symbol=symbol, interval='1h', limit=2)
    if len(klines) < 2:
        return 0
    prev_close = float(klines[0][4])
    last_close = float(klines[1][4])
    return (last_close - prev_close) / prev_close * 100

def market_is_risky():
    # For example, check if BTCUSDT 1h change is negative or > X% move
    btc_change_1h = get_1h_percent_change("BTCUSDT")
    return btc_change_1h < -1 or abs(btc_change_1h) > 3

MAX_POSITIONS = 20

def too_many_positions():
    return len(positions) >= MAX_POSITIONS

def round_qty(symbol, qty):
    """
    Round quantity to symbol's step size, as required by Binance.
    """
    info = client.get_symbol_info(symbol)
    step_size = None
    for f in info['filters']:
        if f['filterType'] == 'LOT_SIZE':
            step_size = float(f['stepSize'])
            break
    if step_size is None:
        return qty  # Fallback, no rounding if not found
    # Decimal rounding
    d_qty = decimal.Decimal(str(qty))
    d_step = decimal.Decimal(str(step_size))
    rounded_qty = float((d_qty // d_step) * d_step)
    # Safety: return 0 if below step size
    if rounded_qty < step_size:
        return 0
    return rounded_qty

def quote_precision_for(symbol):
    try:
        info = client.get_symbol_info(symbol)
        for f in info['filters']:
            if f['filterType'] == 'LOT_SIZE':
                step = str(f['stepSize'])
                if '.' in step:
                    return len(step.split('.')[1].rstrip('0'))
        return 2
    except Exception:
        return 2

def sell(symbol, qty):
    try:
        sell_qty = round_qty(symbol, qty)
        if sell_qty == 0:
            print(f"[SKIP] {symbol}: Qty after rounding is 0. Skipping sell for now.")
            return None, 0, 0
        order = client.order_market_sell(symbol=symbol, quantity=sell_qty)
        price = float(order['fills'][0]['price'])
        fee = sum(float(f['commission']) for f in order['fills']) if "fills" in order else 0
        return price, fee, 0
    except BinanceAPIException as e:
        print(f"[SELL ERROR] {symbol}: {e}")
        # Do not remove from positions here.
        return None, 0, 0

def buy(symbol, amount=None):
    print(f"[DEBUG] Actual USDC balance before buy: {balance['usd']}")
    try:
        precision = quote_precision_for(symbol)
        trade_amount = round(amount, precision)
        min_notional = min_notional_for(symbol)
        print(f"[DEBUG] Attempting to buy {symbol}: trade_amount=${trade_amount}, min_notional=${min_notional}")
        if trade_amount < min_notional:
            print(f"[SKIP] {symbol}: Trade amount (${trade_amount}) < MIN_NOTIONAL (${min_notional})")
            return None
        # Let Binance handle rounding/fees
        order = client.order_market_buy(symbol=symbol, quoteOrderQty=trade_amount)
        price = float(order['fills'][0]['price'])
        qty = float(order['executedQty'])
        qty = round_qty(symbol, qty)
        print(f"[INFO] Bought {symbol}: qty={qty}, price={price}")
        balance['usd'] -= trade_amount
        positions[symbol] = {
            'entry': price,
            'qty': qty,
            'timestamp': time.time(),
            'trade_time': time.time()
        }
        print(f"[DEBUG] Actual USDC balance after buy attempt: {balance['usd']}")
        return positions[symbol]
    except BinanceAPIException as e:
        print(f"[BUY ERROR] {symbol}: {e}")
        return None

def rotate_positions():
    not_sold = []
    sync_investments_with_binance()
    for symbol in list(positions.keys()):
        qty = positions[symbol]["qty"]
        entry = positions[symbol]["entry"]
        trade_time = positions[symbol]["trade_time"]
        sell_qty = round_qty(symbol, qty)
        if sell_qty == 0 or qty == 0:
            print(f"[SKIP] {symbol}: Qty after rounding is 0. Removing investment.")
            del positions[symbol]
            continue
        try:
            exit_price, fee, tax = sell(symbol, qty)
            if exit_price:
                log_trade(symbol, entry, exit_price, qty, trade_time, time.time(), fee, tax)
                del positions[symbol]
            else:
                not_sold.append(symbol)
        except Exception as e:
            print(f"[ERROR] Rotate failed for {symbol}: {e}")
            not_sold.append(symbol)
    sync_investments_with_binance()
    time.sleep(2)
    invest_momentum()
    sync_investments_with_binance()
    return not_sold

def process_actions():
    state = get_bot_state()
    actions = state.get("actions", [])
    performed = []
    for act in actions:
        if act["type"] == "rotate":
            rotate_positions()
            performed.append(act)
        elif act["type"] == "invest":
            invest_momentum()
            performed.append(act)
        elif act["type"] == "sell_all":
            sell_results = sell_everything()
            state["last_sell_report"] = sell_results
            performed.append(act)
    state["actions"] = [a for a in actions if a not in performed]
    save_bot_state(state)

def sell_everything():
    not_sold = []
    for symbol in list(positions.keys()):
        qty = positions[symbol]["qty"]
        entry = positions[symbol]["entry"]
        trade_time = positions[symbol]["trade_time"]
        sell_qty = round_qty(symbol, qty)
        if sell_qty == 0 or qty == 0:
            print(f"[SKIP] {symbol}: Qty after rounding is 0. Removing investment.")
            del positions[symbol]
            continue
        try:
            exit_price, fee, tax = sell(symbol, qty)
            if exit_price:
                log_trade(symbol, entry, exit_price, qty, trade_time, time.time(), fee, tax)
                del positions[symbol]
            else:
                not_sold.append(symbol)
        except Exception as e:
            print(f"[ERROR] Sell failed for {symbol}: {e}")
            not_sold.append(symbol)
    
    sync_investments_with_binance()
    return not_sold

TAX_RATE = 0.25  # Example: 25% of net profit, change to your local capital gains rate!

def estimate_trade_tax(entry_price, exit_price, qty, trade_time, exit_time):
    """
    Estimates the tax for a given trade based on holding period and gain.
    Uses 40% for short-term (<24h), 25% for long-term (>=24h).
    """
    holding_period = exit_time - trade_time
    profit = (exit_price - entry_price) * qty
    short_term_rate = 0.40
    long_term_rate = 0.25
    if holding_period < 24 * 3600:
        rate = short_term_rate
    else:
        rate = long_term_rate
    tax = profit * rate if profit > 0 else 0
    return tax

# --- CHANGED: trading loop always uses YAML gainers ---
def trading_loop():
    last_sync = time.time()
    SYNC_INTERVAL = 180

    while True:
        try:
            if market_is_risky():
                print("[INFO] Market too volatile. Skipping investing this round.")
                time.sleep(TRADING_INTERVAL)
                continue

            fetch_usdc_balance()
            auto_sell_momentum_positions()  # <<< use new sell logic

            if time.time() - last_sync > SYNC_INTERVAL:
                sync_investments_with_binance()
                last_sync = time.time()

            if not too_many_positions():
                invest_momentum()  # <<< use new invest logic

            sync_state()
            process_actions()
            fetch_usdc_balance()
        except Exception as e:
            print(f"[LOOP ERROR] {e}")
        time.sleep(TRADING_INTERVAL)


# --- The rest of your code remains unchanged (Telegram, utility functions, etc) ---

main_keyboard = [
    ["📊 Balance", "💼 Investments"],
    ["📝 Trade Log"]
]

def queue_action(act_type):
    state = get_bot_state()
    if "actions" not in state:
        state["actions"] = []
    state["actions"].append({"type": act_type})
    save_bot_state(state)

def get_sellable_positions():
    """
    Returns a dict of only sellable positions: {symbol: pos, ...}
    """
    return {symbol: pos for symbol, pos in positions.items() if is_sellable(symbol, pos.get("qty", 0))}


def is_sellable(symbol, qty):
    """
    Returns True if this symbol/qty is sellable (passes step size and min_notional).
    """
    sell_qty = round_qty(symbol, qty)
    if sell_qty == 0:
        print(f"[DEBUG] {symbol}: Qty after rounding is 0 — not sellable.")
        return False
    try:
        min_notional = min_notional_for(symbol)
        current_price = get_latest_price(symbol)
        notional = sell_qty * current_price
        if notional >= min_notional:
            return True
        print(f"[DEBUG] {symbol}: Notional {notional:.8f} < min_notional {min_notional:.8f} — not sellable.")
        return False
    except Exception as e:
        print(f"[DEBUG] {symbol}: is_sellable error: {e}")
        return False

def get_prices_cache(symbols):
    tickers = client.get_ticker()
    return {t['symbol']: float(t['lastPrice']) for t in tickers if t['symbol'] in symbols}

def investments_handler(update, context):
    msg = format_investments_message()
    update.message.reply_text(msg)

def format_investments_message():
    sellable_positions = get_sellable_positions()
    msg_lines = ["Current Investments:"]
    symbols = list(sellable_positions.keys())
    prices = get_prices_cache(symbols)
    for symbol, pos in sellable_positions.items():
        entry = pos.get("entry", 0)
        qty = pos.get("qty", 0)
        cur_price = prices.get(symbol, 0)
        value = qty * cur_price
        pnl = (cur_price - entry) / entry * 100 if entry else 0
        msg_lines.append(
            f"{symbol}: Qty {qty:.4f} @ {entry:.5f} → {cur_price:.5f} | Value ${value:.2f} | PnL {pnl:.2f}%"
        )
    # Now show "Other Holdings"
    account_info = client.get_account()
    assets = {
        a["asset"]: float(a["free"])
        for a in account_info["balances"]
        if float(a["free"]) > 0.0001 and a["asset"] != BASE_ASSET
    }
    other_assets = [
        asset for asset in assets
        if f"{asset}{BASE_ASSET}" not in sellable_positions
    ]
    if other_assets:
        msg_lines.append("\nOther Holdings:")
        for asset in other_assets:
            amt = assets[asset]
            symbol = f"{asset}{BASE_ASSET}"
            try:
                price = get_latest_price(symbol)
                value = amt * price
                msg_lines.append(f"{symbol}: Qty {amt:.4f} | Value ${value:.2f}")
            except Exception:
                continue
    return "\n".join(msg_lines)


def get_latest_price(symbol):
    return float(client.get_symbol_ticker(symbol=symbol)["price"])

def min_notional_for(symbol):
    try:
        info = client.get_symbol_info(symbol)
        for f in info['filters']:
            if f['filterType'] == 'MIN_NOTIONAL':
                return float(f['notional'])
        return 10.0
    except Exception:
        return 10.0

def estimate_trade_fee(amount, symbol=None):
    FEE_RATE = 0.001
    return amount * FEE_RATE

def lot_step_size_for(symbol):
    try:
        info = client.get_symbol_info(symbol)
        for f in info['filters']:
            if f['filterType'] == 'LOT_SIZE':
                step_size = float(f['stepSize'])
                min_qty = float(f['minQty'])
                return step_size, min_qty
    except Exception:
        pass
    return 0.000001, 0.000001

def telegram_handle_message(update: Update, context: CallbackContext):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        update.message.reply_text("Access Denied.")
        return
    text = update.message.text
    state = get_bot_state()

    if text == "📊 Balance":
        state = get_bot_state()
        pos = state.get("positions", {})
        usdc = state.get("balance", 0)
        total_invested_value = 0
        for s, p in pos.items():
            try:
                current = get_latest_price(s)
                total_invested_value += current * float(p['qty'])
            except Exception:
                continue
        total_portfolio_value = usdc + total_invested_value
        msg = (
            f"USDC Balance: ${usdc:.2f}\n"
            f"Investments: ${total_invested_value:.2f}\n"
            f"Portfolio value: ${total_portfolio_value:.2f} USDC"
        )
        
        update.message.reply_text(msg)

    elif text == "💼 Investments":
        pos = state.get("positions", {})
        usdc = state.get("balance", 0)
        rows = []
        total_invested_value = 0
        for s, p in pos.items():
            try:
                current = get_latest_price(s)
                value = current * float(p['qty'])
                total_invested_value += value
                min_notional = min_notional_for(s)
                step, min_qty = lot_step_size_for(s)
                sellable = float(p['qty']) >= min_qty and value >= min_notional
                pnl_pct = (current - float(p['entry'])) / float(p['entry']) * 100
                warn = ""
                if not sellable:
                    continue
                rows.append(
                    f"{s}\n"
                    f"  Qty: {float(p['qty']):.4f}   Entry: {float(p['entry']):.4f}\n"
                    f"  Now: {current:.4f}   "
                    f"Value: ${value:.2f} USDC   "
                    f"PnL: {pnl_pct:+.2f}%\n"
                    f"{warn}"
                )
            except Exception:
                rows.append(
                    f"{s}\n  Qty: {p['qty']:.4f}   Entry: {p['entry']:.4f}  [price error]\n"
                )
        rows.append(
            f"USDC\n"
            f"  Qty: {usdc:.2f}   Value: ${usdc:.2f} USDC\n"
        )
        total_portfolio_value = usdc + total_invested_value
        msg = (
            f"Investments: ${total_invested_value:.2f} USDC\n"
            f"Liquid (USDC): ${usdc:.2f}\n"
            f"Portfolio value: ${total_portfolio_value:.2f} USDC\n"
            f"\n\n"
            + "\n".join(rows)
        )
        update.message.reply_text(msg)


    elif text == "📝 Trade Log":
        log = trade_log
        if not log:
            update.message.reply_text("No trades yet.")
        else:
            msg = (
                "Time                 Symbol       Entry      Exit       Qty        PnL($)\n"
                "-----------------------------------------------------------------------\n"
            )
            for tr in log[-10:]:
                try:
                    entry = float(tr.get('Entry', 0))
                    exit_ = float(tr.get('Exit', 0))
                    qty = float(tr.get('Qty', 0))
                    pnl = float(tr.get('PnL $', 0))
                    msg += (
                        f"{tr['Time'][:16]:<19} "
                        f"{tr['Symbol']:<11} "
                        f"{entry:<9.4f} "
                        f"{exit_:<9.4f} "
                        f"{qty:<9.5f} "
                        f"{pnl:<8.2f}\n"
                    )
                except (ValueError, KeyError) as e:
                    # Skip this row, optionally log error
                    print(f"[WARN] Bad trade log row: {tr} ({e})")
                    continue

            update.message.reply_text(f"```{msg}```", parse_mode='Markdown')

    # elif text == "🔄 Rotate":
    #     queue_action("rotate")
    #     update.message.reply_text(
    #         "🔄 Rotating investments...\n"
    #         "Rotate = Sell everything and immediately invest in the current top gainers."
    #     )
    # elif text == "🟢 Invest":
    #     queue_action("invest")
    #     update.message.reply_text(
    #         "🟢 Investing in the current top gainers (most positive % change)."
    #     )
    # elif text == "🔴 Sell All":
    #     queue_action("sell_all")
    #     report = state.get("last_sell_report", [])
    #     if not report:
    #         update.message.reply_text("🔴 Selling everything to USDC. Any unsold coins will remain in Investments.")
    #     else:
    #         msg = "Tried to sell all to USDC.\nFailed to sell:\n" + "\n".join(report)
    #         update.message.reply_text(msg)
    else:
        update.message.reply_text("Unknown action.")

def telegram_main():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler('start', lambda update, ctx:
        update.message.reply_text(
            "Welcome! Use the buttons below:\n\n"
            "Rotate: Sells everything and reinvests in top gainers.",
            reply_markup=ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
        )
    ))
    dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), telegram_handle_message))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    refresh_symbols()
    positions.update(resume_positions_from_binance())
    try:
        trading_thread = threading.Thread(target=trading_loop, daemon=True)
        trading_thread.start()
        telegram_main()  # This blocks; run in main thread for proper Ctrl+C
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down gracefully...")
    finally:
        print("[INFO] Goodbye!")
