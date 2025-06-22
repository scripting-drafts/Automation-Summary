import time
import yaml
from datetime import datetime
from statistics import stdev
from binance.client import Client
from binance.exceptions import BinanceAPIException
from pycoingecko import CoinGeckoAPI

from secret import API_KEY, API_SECRET
YAML_FILE = "symbols.yaml"

cg = CoinGeckoAPI()

def fetch_usdc_symbols(client):
    info = client.get_exchange_info()
    usdc_pairs = [s for s in info['symbols'] if s['quoteAsset'] == 'USDC' and s['status'] == 'TRADING']
    print(f"Found {len(usdc_pairs)} USDC pairs")
    return usdc_pairs

def calc_volatility(closes):
    if len(closes) < 2:
        return 0.0
    returns = [(closes[i]/closes[i-1]) - 1 for i in range(1, len(closes))]
    return float(stdev(returns)) if len(returns) > 1 else 0.0

def build_coingecko_mapping(binance_base_assets):
    all_coins = cg.get_coins_list()
    symbol_map = {c['symbol'].upper(): c['id'] for c in all_coins}
    mapping = {}
    for asset in binance_base_assets:
        cg_id = symbol_map.get(asset.upper())
        if cg_id:
            mapping[asset.upper()] = cg_id
    return mapping

def fetch_cg_marketcaps_and_supply(cg_ids):
    data = {}
    batch_size = 250  # CoinGecko max per call
    for i in range(0, len(cg_ids), batch_size):
        sublist = cg_ids[i:i + batch_size]
        resp = cg.get_coins_markets(vs_currency='usd', ids=','.join(sublist))
        for coin in resp:
            symbol_uc = coin['symbol'].upper()
            data[symbol_uc] = {
                "market_cap": coin.get('market_cap'),
                "circulating_supply": coin.get('circulating_supply')
            }
    return data

def fetch_symbol_data(client, symbol_info, cg_entry):
    symbol = symbol_info['symbol']
    base_asset = symbol_info['baseAsset']
    try:
        ticker = client.get_ticker(symbol=symbol)
        last_price = float(ticker['lastPrice'])

        # Get CoinGecko market cap and circulating supply if available
        market_cap = cg_entry.get("market_cap")
        circulating_supply = cg_entry.get("circulating_supply")

        # Volatility
        closes_15m = [float(k[4]) for k in client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1MINUTE, limit=15)]
        closes_1h  = [float(k[4]) for k in client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1MINUTE, limit=60)]
        closes_1d  = [float(k[4]) for k in client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_15MINUTE, limit=96)]

        vol_15m = calc_volatility(closes_15m)
        vol_1h  = calc_volatility(closes_1h)
        vol_1d  = calc_volatility(closes_1d)

        # Volumes
        klines_15m = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_15MINUTE, limit=1)
        klines_1h = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1HOUR, limit=1)
        klines_1d = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1DAY, limit=1)
        depth = client.get_order_book(symbol=symbol, limit=5)

        data = {
            "market_cap": market_cap,
            "circulating_supply": circulating_supply,
            "last_price": last_price,
            "volatility": {
                "15m": vol_15m,
                "1h": vol_1h,
                "1d": vol_1d
            },
            "stop_loss": 0.02,
            "target_pnl": 0.03,
            "trailing_stop": 0.01,
            "max_hold_time": 600,
            "taxes": 0.0,
            "volume_15m": float(klines_15m[0][5]) if klines_15m else 0,
            "volume_1h": float(klines_1h[0][5]) if klines_1h else 0,
            "volume_1d": float(klines_1d[0][5]) if klines_1d else 0,
            "arbitrage": {
                "bid_ask_spread": float(depth['asks'][0][0]) - float(depth['bids'][0][0]),
                "top_bid": float(depth['bids'][0][0]),
                "top_ask": float(depth['asks'][0][0]),
                "order_book_depth": sum(float(x[1]) for x in depth['bids']) + sum(float(x[1]) for x in depth['asks'])
            }
        }
        print(f"OK: {symbol} [CG: {'yes' if market_cap else 'no'}]")
        return data
    except Exception as e:
        print(f"[ERROR] {symbol}: {e}")
        return None

def update_yaml(client):
    print(f"\n[{datetime.now()}] Updating {YAML_FILE} ...")
    usdc_symbols = fetch_usdc_symbols(client)
    if not usdc_symbols:
        print("[WARNING] No USDC pairs found!")
        return

    binance_base_assets = list(set(s['baseAsset'] for s in usdc_symbols))
    cg_mapping = build_coingecko_mapping(binance_base_assets)
    cg_ids = list(set(cg_mapping.values()))
    print(f"Fetching CG market data for {len(cg_ids)} assets.")
    cg_market_data = fetch_cg_marketcaps_and_supply(cg_ids)

    data = {}
    for i, symbol_info in enumerate(usdc_symbols):
        symbol = symbol_info['symbol']
        base_asset = symbol_info['baseAsset'].upper()
        cg_entry = cg_market_data.get(base_asset, {})
        symbol_data = fetch_symbol_data(client, symbol_info, cg_entry)
        if symbol_data:
            data[symbol] = symbol_data
        time.sleep(0.25)  # minimal sleep to avoid Binance bans
        if i % 10 == 0:
            print(f"Processed {i+1}/{len(usdc_symbols)} symbols")

    with open(YAML_FILE, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    print(f"[{datetime.now()}] {YAML_FILE} updated. {len(data)} USDC pairs.")

if __name__ == "__main__":
    client = Client(API_KEY, API_SECRET)
    while True:
        start = datetime.now()
        update_yaml(client)
        print(f"Completed update at {datetime.now()} (took {datetime.now() - start})\n")
        # No sleep here: loops as fast as allowed by API speed
