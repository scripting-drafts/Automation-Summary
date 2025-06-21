import requests

def get_binance_usdc_symbols():
    resp = requests.get("https://api.binance.com/api/v3/exchangeInfo")
    resp.raise_for_status()
    data = resp.json()
    return [
        s["symbol"] for s in data["symbols"]
        if s["status"] == "TRADING" and s["quoteAsset"] == "USDC"
    ]

if __name__ == "__main__":
    symbols = get_binance_usdc_symbols()
    print("usdc_symbols = [")
    for s in symbols:
        print(f'    "{s}",')
    print("]")
