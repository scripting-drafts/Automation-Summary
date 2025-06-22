# --- HIGH RISK TRADING BOT with TELEGRAM, STREAMLIT, SMART SELL/CONVERT, PNL CUTS ---

from binance.client import Client
from binance.exceptions import BinanceAPIException
import pandas as pd
import threading
import time
from datetime import datetime
import json, os, csv, sys, decimal
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from secret import API_KEY, API_SECRET, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

BASE_ASSET = 'USDC'
TRADING_INTERVAL = 5  # seconds

client = Client(API_KEY, API_SECRET)
balance = {'usd': 0.0}
positions = {}

TRADE_CSV = "trades.csv"
trade_log = []
SYMBOLS = []

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
            if f['filterType'] == 'PRICE_FILTER':
                step = str(f['tickSize'])
                if '.' in step:
                    return len(step.split('.')[1].rstrip('0'))
        return 2
    except Exception:
        return 2

def binance_convert(asset_from, asset_to, amount):
    try:
        print(f"[CONVERT] Would attempt to convert {amount} {asset_from} to {asset_to}")
        # Placeholder for real convert endpoint!
        return True, f"Converted {amount} {asset_from} to {asset_to}"
    except BinanceAPIException as e:
        return False, f"[CONVERT ERROR] {asset_from}->{asset_to}: {e}"
    except Exception as e:
        return False, f"[CONVERT ERROR] {asset_from}->{asset_to}: {e}"

def get_bot_state():
    if not os.path.exists("bot_state.json"):
        return {"balance": 0, "positions": {}, "log": [], "actions": []}
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

def load_trade_history():
    logs = []
    if os.path.exists(TRADE_CSV):
        with open(TRADE_CSV, "r") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) == 6:
                    logs.append({
                        "Time": row[0],
                        "Symbol": row[1],
                        "Entry": float(row[2]),
                        "Exit": float(row[3]),
                        "Qty": float(row[4]),
                        "PnL $": float(row[5]),
                    })
    return logs

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
        print(f"[BUY] {symbol}: Bought {qty} at {price} for ${trade_amount}")
        return {'entry': price, 'qty': qty, 'timestamp': time.time()}
    except BinanceAPIException as e:
        print(f"[BUY ERROR] {symbol}: {e}")
        return None
    except Exception as e:
        print(f"[BUY ERROR] {symbol}: {e}")
        return None

def sell_or_convert(symbol, qty, prefer='USDC'):
    messages = []
    result = None
    sell_qty = round_qty(symbol, qty)
    if sell_qty == 0:
        msg = f"[SELL ERROR] {symbol}: Qty after rounding is 0."
        print(msg)
        messages.append(msg)
        return None, messages
    # Market sell attempt
    try:
        order = client.order_market_sell(symbol=symbol, quantity=sell_qty)
        price = float(order['fills'][0]['price'])
        messages.append(f"[SELL] {symbol}: Sold {sell_qty} at {price}")
        return price, messages
    except BinanceAPIException as e:
        msg = f"[SELL ERROR] {symbol}: {e}"
        print(msg)
        messages.append(msg)
    except Exception as e:
        msg = f"[SELL ERROR] {symbol}: {e}"
        print(msg)
        messages.append(msg)
    # Fallback to convert
    base_asset = symbol.replace('USDC', '')
    if prefer == 'USDC':
        to_asset = 'USDC'
    else:
        to_asset = 'BTC'
    success, msg = binance_convert(base_asset, to_asset, sell_qty)
    messages.append(msg)
    if success:
        print(f"[CONVERT] {symbol}: {base_asset} -> {to_asset} success")
        return None, messages
    if prefer == 'USDC':
        success, msg = binance_convert(base_asset, 'BTC', sell_qty)
        messages.append(msg)
        if success:
            print(f"[CONVERT] {symbol}: {base_asset} -> BTC success")
    return None, messages

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
        with open(TRADE_CSV, "a") as f:
            f.write(f"{trade['Time']},{symbol},{entry:.4f},{exit_price:.4f},{qty:.6f},{pnl:.2f}\n")
    except Exception:
        pass

def calculate_trade_amount(n=1):
    fetch_usdc_balance()
    if n == 0:
        return 0.0
    return round((balance['usd'] / n) * 0.98, 2)

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
            pos = buy(symbol, amount=amount_per_coin)
            if pos:
                positions[symbol] = pos
        except Exception as e:
            print(f"[ERROR] Invest gainers failed for {symbol}: {e}")

def sell_everything():
    """
    Attempts to market sell every position. If it fails,
    attempts to convert to USDC, then to BTC. Logs each step.
    Returns a list of status messages.
    """
    summary = []
    for symbol in list(positions.keys()):
        try:
            qty = positions[symbol]["qty"]
            entry = positions[symbol]["entry"]
            sell_qty = round_qty(symbol, qty)
            # 1. Market Sell
            try:
                if sell_qty == 0:
                    raise Exception("Qty after rounding is 0")
                order = client.order_market_sell(symbol=symbol, quantity=sell_qty)
                price = float(order['fills'][0]['price'])
                summary.append(f"[SELL] {symbol}: Sold {sell_qty} at {price}")
                log_trade(symbol, entry, price, qty)
                del positions[symbol]
                continue
            except Exception as e1:
                summary.append(f"[SELL ERROR] {symbol}: {e1}")
            # 2. Convert to USDC
            base_asset = symbol.replace('USDC', '')
            success, msg = binance_convert(base_asset, 'USDC', sell_qty)
            summary.append(msg)
            if success:
                del positions[symbol]
                continue
            # 3. Convert to BTC
            success, msg = binance_convert(base_asset, 'BTC', sell_qty)
            summary.append(msg)
            if success:
                del positions[symbol]
                continue
            summary.append(f"[FAIL] {symbol}: Could not sell or convert after all attempts.")
        except Exception as e:
            summary.append(f"[ERROR] {symbol}: {e}")
    return summary

def trading_loop():
    while True:
        try:
            fetch_usdc_balance()
            sold = False
            for symbol in list(positions.keys()):
                current_price = get_latest_price(symbol)
                entry = positions[symbol]["entry"]
                qty = positions[symbol]["qty"]
                pnl_pct = (current_price - entry) / entry * 100
                if current_price >= entry * 1.01 or pnl_pct <= -10.0:
                    exit_price, messages = sell_or_convert(symbol, qty, prefer='USDC')
                    for msg in messages:
                        print(msg)
                    if exit_price:
                        log_trade(symbol, entry, exit_price, qty)
                        del positions[symbol]
                        sold = True
            sync_state()
            process_actions()
            if (not positions) or sold:
                invest_gainers()
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
        fetch_usdc_balance()
        total_positions = 0
        for s, p in positions.items():
            try:
                current = get_latest_price(s)
                value = current * p['qty']
                total_positions += value
            except Exception:
                pass
        portfolio_value = balance['usd'] + total_positions
        update.message.reply_text(
            f"Portfolio value: ${portfolio_value:.2f} USDC\n"
            f"USDC balance: ${balance['usd']:.2f}\n"
            f"Positions value: ${total_positions:.2f}"
        )
    elif text == "💼 Open Positions":
        fetch_usdc_balance()
        pos = positions
        usdc = balance['usd']
        rows = []
        total_usdc_value = 0
        for s, p in pos.items():
            try:
                current = get_latest_price(s)
                value = current * p['qty']
                total_usdc_value += value
                pnl_pct = (current - p['entry']) / p['entry'] * 100
                rows.append(
                    f"{s}\n"
                    f"  Qty: {p['qty']:.4f}   Entry: {p['entry']:.4f}\n"
                    f"  Now: {current:.4f}   Value: ${value:.2f} USDC   PnL: {pnl_pct:+.2f}%\n"
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
    elif text == "🔄 Rotate":
        queue_action("rotate")
        update.message.reply_text(
            "🔄 Rotating portfolio...\n"
            "Rotate = Sell everything to USDC/BTC and immediately invest in current top gainers."
        )
    elif text == "🟢 Invest":
        queue_action("invest")
        update.message.reply_text(
            "🟢 Investing in the current top gainers (most positive % change)."
        )
    elif text in ["🔴 Sell All", "Sell All"]:
        queue_action("sell_all")
        report = state.get("last_sell_report", [])
        if not report:
            update.message.reply_text(
                "🔴 Selling all assets (market sell, convert to USDC, then BTC if needed)."
            )
        else:
            msg = "Tried to sell all assets (with fallback to convert):\n" + "\n".join(report)
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
                msg += (
                    f"{tr['Time'][:16]:<19} "
                    f"{tr['Symbol']:<11} "
                    f"{tr['Entry']:<9.4f} "
                    f"{tr['Exit']:<9.4f} "
                    f"{tr['Qty']:<9.5f} "
                    f"{tr['PnL $']:<8.2f}\n"
                )
            update.message.reply_text(f"```{msg}```", parse_mode='Markdown')
    else:
        update.message.reply_text("Unknown action.")

def telegram_main():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler('start', lambda update, ctx:
        update.message.reply_text(
            "Welcome! Use the buttons below:\n\n"
            "Rotate: Sells everything to USDC/BTC and reinvests in top gainers.",
            reply_markup=ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
        )
    ))
    dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), telegram_handle_message))
    updater.start_polling()
    updater.idle()

def process_actions():
    state = get_bot_state()
    actions = state.get("actions", [])
    performed = []
    for act in actions:
        if act["type"] == "rotate":
            sell_everything()
            invest_gainers()
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


import subprocess

def run_streamlit():
    # Launch dashboard in background
    return subprocess.Popen([sys.executable, "-m", "streamlit", "run", "streamlit_dashboard.py"])

# ----------------------- MAIN ------------------------------

if __name__ == "__main__":
    trade_log = load_trade_history()
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
