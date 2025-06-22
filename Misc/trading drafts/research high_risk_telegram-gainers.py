from binance.client import Client
from binance.exceptions import BinanceAPIException
import threading
import time
import subprocess
from datetime import datetime
import json, os, decimal, requests, csv, sys

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

from secret import API_KEY, API_SECRET, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
BASE_ASSET = 'USDC'
TRADING_INTERVAL = 5  # seconds

client = Client(API_KEY, API_SECRET)
balance = {'usd': 0.0}
positions = {}
TRADE_LOG_FILE = "trades_detailed.csv"

# --------- Load previous trades -----------
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

# ------------------------------------------

SYMBOLS = []

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

def round_qty(symbol, qty):
    step_size, min_qty = lot_step_size_for(symbol)
    step_dec = decimal.Decimal(str(step_size))
    qty_dec = decimal.Decimal(str(qty))
    rounded = float((qty_dec // step_dec) * step_dec)
    if rounded < min_qty:
        return 0.0
    return rounded

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
    state["log"] = trade_log[-100:]
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
            invest_gainers()
            performed.append(act)
        elif act["type"] == "sell_all":
            sell_results = sell_everything()
            state["last_sell_report"] = sell_results
            performed.append(act)
    state["actions"] = [a for a in actions if a not in performed]
    save_bot_state(state)

def fetch_usdc_balance():
    try:
        bal = client.get_asset_balance(asset=BASE_ASSET)
        balance['usd'] = float(bal['free'])
    except Exception:
        balance['usd'] = 0.0

def get_top_gainers(limit=10):
    try:
        tickers = client.get_ticker()
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
                    "timestamp": time.time(),
                    "trade_time": time.time()
                }
            except:
                continue
        return resumed
    except Exception as e:
        return {}

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
        qty = round_qty(symbol, qty)
        balance['usd'] -= trade_amount
        positions[symbol] = {'entry': price, 'qty': qty, 'timestamp': time.time(), 'trade_time': time.time()}
        return positions[symbol]
    except BinanceAPIException as e:
        print(f"[BUY ERROR] {symbol}: {e}")
        return None

def sell(symbol, qty):
    try:
        sell_qty = round_qty(symbol, qty)
        if sell_qty == 0:
            print(f"[SKIP] {symbol}: Qty after rounding is 0. Not attempting to sell anymore.")
            del positions[symbol]
            return None, 0, 0
        order = client.order_market_sell(symbol=symbol, quantity=sell_qty)
        price = float(order['fills'][0]['price'])
        fee = sum(float(f['commission']) for f in order['fills']) if "fills" in order else 0
        return price, fee, 0
    except BinanceAPIException as e:
        print(f"[SELL ERROR] {symbol}: {e}")
        return None, 0, 0

def log_trade(symbol, entry, exit_price, qty, trade_time, exit_time, fees=0, tax=0):
    pnl = (exit_price - entry) * qty
    duration_sec = int(exit_time - trade_time)
    trade = {
        'Time': datetime.fromtimestamp(trade_time).strftime("%Y-%m-%d %H:%M:%S"),
        'Symbol': symbol,
        'Entry': round(entry, 8),
        'Exit': round(exit_price, 8),
        'Qty': round(qty, 8),
        'PnL $': round(pnl, 8),
        'Duration (s)': duration_sec,
        'Fees': fees,
        'Tax': tax
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

def rotate_positions():
    not_sold = []
    for symbol in list(positions.keys()):
        qty = positions[symbol]["qty"]
        entry = positions[symbol]["entry"]
        trade_time = positions[symbol]["trade_time"]
        sell_qty = round_qty(symbol, qty)
        if sell_qty == 0:
            print(f"[SKIP] {symbol}: Qty after rounding is 0. Not attempting to sell anymore.")
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
    time.sleep(2)
    invest_gainers()
    return not_sold

def refresh_symbols():
    global SYMBOLS
    SYMBOLS = get_top_gainers(10)

def invest_gainers():
    refresh_symbols()
    gainers = SYMBOLS.copy()
    balance_to_spend = balance['usd'] * 0.98
    if not gainers:
        print("[INFO] No gainers to invest in.")
        return

    min_notionals = [(symbol, min_notional_for(symbol)) for symbol in gainers]
    affordable_symbols = []
    amount_per_coin = 0
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
            continue
        try:
            buy(symbol, amount=amount_per_coin)
        except Exception as e:
            print(f"[ERROR] Invest gainers failed for {symbol}: {e}")

def sell_everything():
    not_sold = []
    for symbol in list(positions.keys()):
        qty = positions[symbol]["qty"]
        entry = positions[symbol]["entry"]
        trade_time = positions[symbol]["trade_time"]
        sell_qty = round_qty(symbol, qty)
        if sell_qty == 0:
            print(f"[SKIP] {symbol}: Qty after rounding is 0. Not attempting to sell anymore.")
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
    return not_sold

def trading_loop():
    while True:
        try:
            fetch_usdc_balance()
            sold = False
            for symbol in list(positions.keys()):
                qty = positions[symbol]["qty"]
                entry = positions[symbol]["entry"]
                trade_time = positions[symbol]["trade_time"]
                sell_qty = round_qty(symbol, qty)
                if sell_qty == 0:
                    print(f"[SKIP] {symbol}: Qty after rounding is 0. Not attempting to sell anymore.")
                    del positions[symbol]
                    continue
                current_price = get_latest_price(symbol)
                # SELL: If profit ≥ 1% OR loss ≥ 0.10%
                if current_price >= entry * 1.01 or current_price <= entry * 0.999:
                    exit_price, fee, tax = sell(symbol, qty)
                    if exit_price:
                        log_trade(symbol, entry, exit_price, qty, trade_time, time.time(), fee, tax)
                        del positions[symbol]
                        sold = True
            sync_state()
            process_actions()
            # Only invest after sales/rotations, NOT at every app start!
            if (not positions) or sold:
                pass  # do not invest_gainers() automatically
        except Exception as e:
            print(f"[LOOP ERROR] {e}")
        time.sleep(TRADING_INTERVAL)

main_keyboard = [
    ["📊 Balance", "💼 Open Positions"],
    ["🔄 Rotate", "🟢 Invest", "🔴 Sell All"],
    ["📝 Trade Log"]
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
        state = get_bot_state()
        pos = state.get("positions", {})
        usdc = state.get("balance", 0)
        total_usdc_value = 0
        for s, p in pos.items():
            try:
                current = get_latest_price(s)
                total_usdc_value += current * float(p['qty'])
            except Exception:
                continue
        total_portfolio_value = usdc + total_usdc_value
        msg = (
            f"USDC Balance: ${usdc:.2f}\n"
            f"Portfolio value (incl. open positions): ${total_portfolio_value:.2f}"
        )
        update.message.reply_text(msg)

    elif text == "💼 Open Positions":
        pos = state.get("positions", {})
        usdc = state.get("balance", 0)
        rows = []
        total_usdc_value = 0
        for s, p in pos.items():
            try:
                current = get_latest_price(s)
                value = current * float(p['qty'])
                total_usdc_value += value
                pnl_pct = (current - float(p['entry'])) / float(p['entry']) * 100
                rows.append(
                    f"{s}\n"
                    f"  Qty: {float(p['qty']):.4f}   Entry: {float(p['entry']):.4f}\n"
                    f"  Now: {current:.4f}   "
                    f"Value: ${value:.2f} USDC   "
                    f"PnL: {pnl_pct:+.2f}%\n"
                )
            except Exception:
                rows.append(
                    f"{s}\n  Qty: {p['qty']:.4f}   Entry: {p['entry']:.4f}  [price error]\n"
                )
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
        log = trade_log  # <-- use full trade history!
        if not log:
            update.message.reply_text("No trades yet.")
        else:
            msg = (
                "Time                 Symbol       Entry      Exit       Qty        PnL($)\n"
                "-----------------------------------------------------------------------\n"
            )
            for tr in log[-10:]:
                msg += (
                    f"{tr['Time'][:16]:<19} "
                    f"{tr['Symbol']:<11} "
                    f"{float(tr['Entry']):<9.4f} "
                    f"{float(tr['Exit']):<9.4f} "
                    f"{float(tr['Qty']):<9.5f} "
                    f"{float(tr['PnL $']):<8.2f}\n"
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

def run_streamlit():
    return subprocess.Popen([sys.executable, "-m", "streamlit", "run", "streamlit_dashboard.py"])

if __name__ == "__main__":
    refresh_symbols()
    positions.update(resume_positions_from_binance())
    streamlit_proc = None
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
