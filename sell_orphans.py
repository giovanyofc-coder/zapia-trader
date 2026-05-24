import os
import time
import hmac
import hashlib
import requests
import math

api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')
base_url = "https://api.binance.com"

def get_exchange_info():
    try:
        r = requests.get(f"{base_url}/api/v3/exchangeInfo")
        return r.json()
    except Exception as e:
        print(f"Error fetching exchange info: {e}")
        return {}

def sell_all():
    assets_to_sell = ["DOGE", "ETH", "SOL", "BTC"]
    print(f"--- 🦾 ZAPIA ORPHAN CLEANUP ---")
    
    if not api_key or not api_secret:
        print("❌ Error: BINANCE_API_KEY or BINANCE_API_SECRET not set in environment.")
        return

    # Get Precision info
    info = get_exchange_info()
    if 'symbols' not in info:
        print(f"❌ Could not get symbols from Binance: {info}")
        return
        
    symbols_info = {s['symbol']: s for s in info['symbols']}

    # 1. Get Account Info
    timestamp = int(time.time() * 1000)
    query = f"timestamp={timestamp}"
    signature = hmac.new(api_secret.encode('utf-8'), query.encode('utf-8'), hashlib.sha256).hexdigest()
    
    try:
        r = requests.get(f"{base_url}/api/v3/account", params={"timestamp": timestamp, "signature": signature}, headers={"X-MBX-APIKEY": api_key})
        account = r.json()
    except Exception as e:
        print(f"Error fetching account: {e}")
        return
    
    if 'balances' not in account:
        print(f"❌ Error fetching account details: {account}")
        return

    for asset in assets_to_sell:
        balance_info = next((b for b in account['balances'] if b['asset'] == asset), None)
        if not balance_info:
            continue
            
        free = float(balance_info['free'])
        # Check if balance is significant enough (Binance has min notionals, usually $5-10)
        # But we'll try to sell anything above a tiny threshold
        if free <= 0.00000001:
            continue
            
        symbol = f"{asset}BRL"
        if symbol not in symbols_info:
            print(f"⚠️ Symbol {symbol} not found on Binance.")
            continue

        # Handle Precision (LOT_SIZE)
        step_size = 0.00000001
        for f in symbols_info[symbol]['filters']:
            if f['filterType'] == 'LOT_SIZE':
                step_size = float(f['stepSize'])
                break
        
        # Calculate precision from stepSize
        precision = 0
        if step_size < 1:
            precision = int(round(-math.log10(step_size)))
        
        # Floor to precision
        factor = 10 ** precision
        quantity = math.floor(free * factor) / factor
        
        if quantity <= 0:
            continue

        print(f"🔍 Found {free} {asset}. Attempting to sell {quantity} {asset}...")
        
        timestamp = int(time.time() * 1000)
        sell_params = {
            "symbol": symbol,
            "side": "SELL",
            "type": "MARKET",
            "quantity": f"{quantity:.{precision}f}",
            "timestamp": timestamp
        }
        
        sell_query = '&'.join([f"{k}={v}" for k, v in sell_params.items()])
        sell_sig = hmac.new(api_secret.encode('utf-8'), sell_query.encode('utf-8'), hashlib.sha256).hexdigest()
        
        try:
            res = requests.post(f"{base_url}/api/v3/order", params={**sell_params, "signature": sell_sig}, headers={"X-MBX-APIKEY": api_key})
            result = res.json()
            if 'orderId' in result:
                print(f"✅ SUCCESS: Sold {quantity} {asset} on {symbol}")
            else:
                print(f"❌ FAILED to sell {asset}: {result}")
        except Exception as e:
            print(f"❌ Error during sell order for {asset}: {e}")

    print("--- Cleanup Process Finished ---")

if __name__ == "__main__":
    sell_all()
