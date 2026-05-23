import os
import time
from binance.client import Client
from dotenv import load_dotenv

# Carrega as chaves de API configuradas no Railway
load_dotenv()

api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')

def run_bot():
    try:
        # Inicializa o cliente da Binance
        client = Client(api_key, api_secret)
        print("--- Robô Zapia-Trader Online ---")
        
        while True:
            # Pega o preço atual do Bitcoin (BTC) em Dólar (USDT)
            ticker = client.get_symbol_ticker(symbol="BTCUSDT")
            price = ticker['price']
            print(f"Monitorando BTC: ${price}")
            
            # Aguarda 60 segundos para a próxima verificação
            time.sleep(60)
            
    except Exception as e:
        print(f"Erro no robô: {e}")

if __name__ == "__main__":
    run_bot()
