import os
import time
from binance.client import Client

api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')

def run_bot():
    client = Client(api_key, api_secret)
    print("--- Robô Zapia-Trader Online ---")
    while True:
        price = client.get_symbol_ticker(symbol="BTCUSDT")['price']
        print(f"Monitorando BTC: ${price}")
        time.sleep(60)

if __name__ == "__main__":
    run_bot()
  
