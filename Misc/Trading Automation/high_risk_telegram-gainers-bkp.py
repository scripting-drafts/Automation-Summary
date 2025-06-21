# --- HIGH RISK TRADING BOT with TELEGRAM BUTTON CONTROL (GAINERS + FIXES) ---

from binance.client import Client
from binance.exceptions import BinanceAPIException
import pandas as pd
import threading
import time
from datetime import datetime
import json, os

# ==== Telegram Setup ====
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# ------------------ USER SETTINGS ------------------------
from secret import API_KEY, API_SECRET, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
BASE_ASSET = 'USDC'
TRADING_INTERVAL = 5  # seconds
# ---------------------------------------------------------

client = Client(API_KEY, API_SECRET)
balance = {'usd': 0.0}
positions = {}
trade_log = []
SYMBOLS = []

import decimal

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
    # fallback to 0.000001 if not found
    return 0.000001, 0.000001

def round_qty(symbol, qty):
    step_size, min_qty = lot_step_size_for(symbol)
    # Round down to nearest step size
    step_dec = decimal.Decimal(str(step_size))
    qty_dec = decimal.Decimal(str(qty))
    rounded = float((qty_dec // step_dec) * step_dec)
    # Ensure at least min_qty, but not more than qty
    if rounded < min_qty:
        return 0.0  # Can't trade less than minQty
    return rounded


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
    state["log"] = trade_log[-100:]  # last 100 trades
    save_bot_state(state)

def process_actions():
    state = get_bot_state()
    actions = state.get("actions", [])
    performed = []
    for act in actions:
        if act["type"] == "rotate":
            rotate_positions()
            performed.append(act)
        elif act["type"] == "pause":
            state["paused"] = True
            performed.append(act)
        elif act["type"] == "resume":
            state["paused"] = False
            performed.append(act)
        elif act["type"] == "invest":
            invest_gainers()
            performed.append(act)
        elif act["type"] == "sell_all":
            sell_results = sell_everything()
            state["last_sell_report"] = sell_results  # for Telegram reporting
            performed.append(act)
    state["actions"] = [a for a in actions if a not in performed]
    save_bot_state(state)

# ========== Trading Logic ===============
def fetch_usdc_balance():
    try:
        bal = client.get_asset_balance(asset=BASE_ASSET)
        balance['usd'] = float(bal['free'])
    except Exception:
        balance['usd'] = 0.0

def get_top_gainers(limit=10):
    try:
        tickers = client.get_ticker()
        # Only USDC pairs, positive change
        gainers = [t for t in tickers if t['symbol'].endswith(BASE_ASSET) and not t['symbol'].startswith(BASE_ASSET)]
        gainers = [t for t in gainers if float(t['priceChangePercent']) > 0]
        sorted_gainers = sorted(gainers, key=lambda x: float(x['priceChangePercent']), reverse=True)
        return [t['symbol'] for t in sorted_gainers[:limit]]
    except Exception as e:
        print(f"[ERROR] Failed to fetch top gainers: {e}")
        return []

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
                    "timestamp": time.time()
                }
            except:
                continue
        return resumed
    except Exception as e:
        return {}

def get_recent_close(symbol, minutes=5):
    try:
        candles = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1MINUTE, limit=minutes)
        return [float(c[4]) for c in candles]
    except:
        return []

def is_strong_trend(prices):
    if len(prices) < 3:
        return False
    change = prices[-1] - prices[0]
    return change > 0 and all(later > earlier for earlier, later in zip(prices, prices[1:]))

def get_latest_price(symbol):
    return float(client.get_symbol_ticker(symbol=symbol)["price"])

def calculate_trade_amount(n=1):
    fetch_usdc_balance()
    if n == 0:
        return 0.0
    return round((balance['usd'] / n) * 0.98, 2)

def min_notional_for(symbol):
    try:
        info = client.get_symbol_info(symbol)
        for f in info['filters']:
            if f['filterType'] == 'MIN_NOTIONAL':
                return float(f['notional'])
        return 10.0
    except Exception:
        return 10.0

def buy(symbol, amount=None):
    try:
        trade_amount = amount if amount else calculate_trade_amount()
        precision = quote_precision_for(symbol)
        trade_amount = round(trade_amount, precision)
        min_notional = min_notional_for(symbol)
        if trade_amount < min_notional:
            print(f"[SKIP] {symbol}: Trade amount (${trade_amount}) < MIN_NOTIONAL (${min_notional})")
            return None
        order = client.order_market_buy(symbol=symbol, quoteOrderQty=trade_amount)
        price = float(order['fills'][0]['price'])
        qty = float(order['executedQty'])
        # -- ROUND QTY FOR STORAGE (optional, but can prevent drift) --
        qty = round_qty(symbol, qty)
        balance['usd'] -= trade_amount
        return {'entry': price, 'qty': qty, 'timestamp': time.time()}
    except BinanceAPIException as e:
        print(f"[BUY ERROR] {symbol}: {e}")
        return None



def sell(symbol, qty):
    try:
        sell_qty = round_qty(symbol, qty)
        if sell_qty == 0:
            print(f"[SELL ERROR] {symbol}: Qty after rounding is 0.")
            return None
        order = client.order_market_sell(symbol=symbol, quantity=sell_qty)
        price = float(order['fills'][0]['price'])
        return price
    except BinanceAPIException as e:
        print(f"[SELL ERROR] {symbol}: {e}")
        return None

def log_trade(symbol, entry, exit_price, qty):
    pnl = (exit_price - entry) * qty
    trade = {
        'Time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'Symbol': symbol,
        'Entry': round(entry, 4),
        'Exit': round(exit_price, 4),
        'Qty': round(qty, 6),
        'PnL $': round(pnl, 2)
    }
    trade_log.append(trade)
    try:
        with open("trades.csv", "a") as f:
            f.write(f"{trade['Time']},{symbol},{entry:.4f},{exit_price:.4f},{qty:.6f},{pnl:.2f}\n")
    except Exception:
        pass

def rotate_positions():
    """Layman: Sells everything then reinvests in new gainers."""
    not_sold = []
    for symbol in list(positions.keys()):
        try:
            qty = positions[symbol]["qty"]
            entry = positions[symbol]["entry"]
            exit_price = sell(symbol, qty)
            if exit_price:
                log_trade(symbol, entry, exit_price, qty)
                del positions[symbol]
            else:
                not_sold.append(symbol)
        except Exception as e:
            print(f"[ERROR] Rotate failed for {symbol}: {e}")
            not_sold.append(symbol)
    time.sleep(2)
    invest_gainers()
    return not_sold

def refresh_symbols():
    global SYMBOLS
    SYMBOLS = get_top_gainers(10)

def quote_precision_for(symbol):
    try:
        info = client.get_symbol_info(symbol)
        for f in info['filters']:
            if f['filterType'] == 'LOT_SIZE':
                step = str(f['stepSize'])
                if '.' in step:
                    return len(step.split('.')[1].rstrip('0'))
        # Fallback, often 2 for USDC pairs
        return 2
    except Exception:
        return 2

def invest_gainers():
    refresh_symbols()
    gainers = SYMBOLS.copy()
    balance_to_spend = balance['usd'] * 0.98  # Leave a buffer

    if not gainers:
        print("[INFO] No gainers to invest in.")
        return

    # Compute minimal notional for each symbol
    min_notionals = [(symbol, min_notional_for(symbol)) for symbol in gainers]
    affordable_symbols = []
    amount_per_coin = 0

    # Try largest possible group (from all gainers down to 1)
    for n in range(len(gainers), 0, -1):
        subset = min_notionals[:n]
        needed_per_coin = balance_to_spend / n
        if all(needed_per_coin >= mn for _, mn in subset):
            affordable_symbols = [s for s, _ in subset]
            amount_per_coin = needed_per_coin
            break
    else:
        print("[INFO] No gainers meet MIN_NOTIONAL for portfolio split.")
        return

    print(f"[INFO] Investing in {len(affordable_symbols)} gainers, ${amount_per_coin:.2f} per coin.")
    for symbol in affordable_symbols:
        if symbol in positions:
            continue  # Don't rebuy
        try:
            pos = buy(symbol, amount=amount_per_coin)
            if pos:
                positions[symbol] = pos
        except Exception as e:
            print(f"[ERROR] Invest gainers failed for {symbol}: {e}")



def sell_everything():
    """Sells all positions, reports which ones failed."""
    not_sold = []
    for symbol in list(positions.keys()):
        try:
            qty = positions[symbol]["qty"]
            entry = positions[symbol]["entry"]
            exit_price = sell(symbol, qty)
            if exit_price:
                log_trade(symbol, entry, exit_price, qty)
                del positions[symbol]
            else:
                not_sold.append(symbol)
        except Exception as e:
            print(f"[ERROR] Sell failed for {symbol}: {e}")
            not_sold.append(symbol)
    return not_sold

def invest_gainers_auto():
    refresh_symbols()
    gainers = SYMBOLS.copy()
    balance_to_spend = balance['usd'] * 0.98  # Reserve a bit

    # Calculate the maximal set of gainers to invest in as a group
    if not gainers:
        print("[INFO] No gainers to invest in.")
        return

    # Compute minimal notional for each symbol
    min_notionals = [(symbol, min_notional_for(symbol)) for symbol in gainers]
    # Try largest possible group (from all gainers down to 1)
    for n in range(len(gainers), 0, -1):
        subset = min_notionals[:n]
        needed_per_coin = balance_to_spend / n
        if all(needed_per_coin >= mn for _, mn in subset):
            affordable_symbols = [s for s, _ in subset]
            amount_per_coin = needed_per_coin
            break
    else:
        print("[INFO] No gainers meet MIN_NOTIONAL for portfolio split.")
        return

    print(f"[INFO] Investing in {len(affordable_symbols)} gainers, ${amount_per_coin:.2f} per coin.")
    for symbol in affordable_symbols:
        if symbol in positions:
            continue  # Don't rebuy
        try:
            pos = buy(symbol, amount=amount_per_coin)
            if pos:
                positions[symbol] = pos
        except Exception as e:
            print(f"[ERROR] Invest gainers failed for {symbol}: {e}")

def trading_loop():
    while True:
        try:
            fetch_usdc_balance()
            sold = False
            for symbol in list(positions.keys()):
                current_price = get_latest_price(symbol)
                entry = positions[symbol]["entry"]
                qty = positions[symbol]["qty"]
                if current_price >= entry * 1.01 or current_price <= entry * 0.995:
                    exit_price = sell(symbol, qty)
                    if exit_price:
                        log_trade(symbol, entry, exit_price, qty)
                        del positions[symbol]
                        sold = True
            sync_state()
            process_actions()
            # --- New investments automatically if no open positions or after a sale
            if (not positions) or sold:
                invest_gainers_auto()
        except Exception as e:
            print(f"[LOOP ERROR] {e}")
        time.sleep(TRADING_INTERVAL)


# ========== Telegram Interface ===============
main_keyboard = [
    ["📊 Balance", "💼 Open Positions"],
    ["🔄 Rotate", "🟢 Invest", "🔴 Sell All"],
    ["🛑 Pause", "▶️ Resume", "📝 Trade Log"]
]

def queue_action(act_type):
    state = get_bot_state()
    if "actions" not in state:
        state["actions"] = []
    state["actions"].append({"type": act_type})
    save_bot_state(state)

def telegram_handle_message(update: Update, context: CallbackContext):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        update.message.reply_text("Access Denied.")
        return
    text = update.message.text
    state = get_bot_state()

    if text == "📊 Balance":
        update.message.reply_text(f"USDC Balance: ${state.get('balance',0):.2f}")
    elif text == "💼 Open Positions":
        pos = state.get("positions", {})
        usdc = state.get("balance", 0)
        rows = []
        total_usdc_value = 0
        # Calculate all open positions value in USDC
        for s, p in pos.items():
            try:
                current = get_latest_price(s)
                value = current * p['qty']
                total_usdc_value += value
                pnl_pct = (current - p['entry']) / p['entry'] * 100
                rows.append(
                    f"{s}\n"
                    f"  Qty: {p['qty']:.4f}   Entry: {p['entry']:.4f}\n"
                    f"  Now: {current:.4f}   "
                    f"Value: ${value:.2f} USDC   "
                    f"PnL: {pnl_pct:+.2f}%\n"
                )
            except Exception:
                rows.append(
                    f"{s}\n  Qty: {p['qty']:.4f}   Entry: {p['entry']:.4f}  [price error]\n"
                )
        # Add USDC as an 'asset'
        rows.append(
            f"USDC\n"
            f"  Qty: {usdc:.2f}   Value: ${usdc:.2f} USDC\n"
        )
        total_portfolio_value = usdc + total_usdc_value
        msg = (
            f"Portfolio value: ${total_portfolio_value:.2f} USDC\n"
            f"Assets:\n\n"
            + "\n".join(rows)
        )
        update.message.reply_text(msg)


    elif text == "📝 Trade Log":
        log = state.get("log", [])
        if not log:
            update.message.reply_text("No trades yet.")
        else:
            # Format as table header
            msg = (
                "Time                 Symbol       Entry      Exit       Qty        PnL($)\n"
                "-----------------------------------------------------------------------\n"
            )
            # Last 10 trades, format each row
            for tr in log[-10:]:
                msg += (
                    f"{tr['Time'][:16]:<19} "
                    f"{tr['Symbol']:<11} "
                    f"{tr['Entry']:<9.4f} "
                    f"{tr['Exit']:<9.4f} "
                    f"{tr['Qty']:<9.5f} "
                    f"{tr['PnL $']:<8.2f}\n"
                )
            update.message.reply_text(f"```{msg}```", parse_mode='Markdown')



    elif text == "🔄 Rotate":
        queue_action("rotate")
        update.message.reply_text(
            "🔄 Rotating portfolio...\n"
            "Rotate = Sell everything and immediately invest in the current top gainers."
        )
    elif text == "🟢 Invest":
        queue_action("invest")
        update.message.reply_text(
            "🟢 Investing in the current top gainers (most positive % change)."
        )
    elif text == "🔴 Sell All":
        queue_action("sell_all")
        report = state.get("last_sell_report", [])
        if not report:
            update.message.reply_text("🔴 Selling everything to USDC. Any unsold coins will remain in Open Positions.")
        else:
            msg = "Tried to sell all to USDC.\nFailed to sell:\n" + "\n".join(report)
            update.message.reply_text(msg)
    elif text == "🛑 Pause":
        queue_action("pause")
        update.message.reply_text(
            "Trading paused.\nPause = Temporarily stop all trading. The bot will not buy or sell until resumed."
        )
    elif text == "▶️ Resume":
        queue_action("resume")
        update.message.reply_text(
            "Trading resumed.\nResume = Restart trading after a pause. Bot resumes buying/selling."
        )
    
    else:
        update.message.reply_text("Unknown action.")

def telegram_main():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler('start', lambda update, ctx:
        update.message.reply_text(
            "Welcome! Use the buttons below:\n\n"
            "Rotate: Sells everything and reinvests in top gainers.\n"
            "Pause: Stops all trades. Resume: Restarts trading.",
            reply_markup=ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
        )
    ))
    dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), telegram_handle_message))
    updater.start_polling()
    updater.idle()

# ========== Startup ===========
import subprocess
import sys
import threading
import time

def run_streamlit():
    return subprocess.Popen([sys.executable, "-m", "streamlit", "run", "streamlit_dashboard.py"])

if __name__ == "__main__":
    refresh_symbols()
    positions.update(resume_positions_from_binance())
    streamlit_proc = run_streamlit()
    try:
        trading_thread = threading.Thread(target=trading_loop, daemon=True)
        trading_thread.start()
        telegram_main()  # This blocks; run in main thread for proper Ctrl+C
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down gracefully...")
    finally:
        if streamlit_proc and streamlit_proc.poll() is None:
            streamlit_proc.terminate()
            try:
                streamlit_proc.wait(timeout=5)
            except Exception:
                streamlit_proc.kill()
        print("[INFO] Goodbye!")
