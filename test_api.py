import requests

symbol = "BTCUSDT"
base = "https://fapi.binance.com"

print("--- Liquidations (forceOrders) ---")
r = requests.get(f"{base}/fapi/v1/forceOrders", params={"symbol": symbol, "limit": 5})
print(r.status_code, r.text[:200])
