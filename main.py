import os
import time
import hmac
import hashlib
import requests
import math
from binance.client import Client
from dotenv import load_dotenv

# Carrega as chaves da Binance
load_dotenv()
api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')
base_url = "https://api.binance.com"

# Configurações via Environment Variables (com fallbacks)
BANCA_TOTAL_BRL = float(os.getenv('BANCA_TOTAL_BRL', 40.0))
VALOR_POR_OPERACAO = float(os.getenv('VALOR_POR_OPERACAO', 13.33))

SELL_THRESHOLD_VAR = float(os.getenv('SELL_THRESHOLD', 1.2))
BUY_THRESHOLD_VAR = float(os.getenv('BUY_THRESHOLD', -0.05))

PROFIT_TARGET = 1 + (SELL_THRESHOLD_VAR / 100)
BUY_THRESHOLD = 1 + (BUY_THRESHOLD_VAR / 100)

CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 5))
PAIRS_STR = os.getenv('PAIRS', 'BTCBRL,SOLBRL,ZECBRL')
symbols = [s.strip() for s in PAIRS_STR.split(',')]

def get_exchange_info():
    try:
        r = requests.get(f"{base_url}/api/v3/exchangeInfo")
        return r.json()
    except Exception as e:
        print(f"Error fetching exchange info: {e}")
        return {}

def sell_orphans():
    assets_to_sell = ["DOGE", "ETH", "SOL", "BTC"]
    print(f"--- 🦾 ZAPIA ORPHAN CLEANUP START ---")
    
    if not api_key or not api_secret:
        print("❌ Error: API keys not set.")
        return

    info = get_exchange_info()
    if 'symbols' not in info:
        print(f"❌ Could not get symbols from Binance")
        return
        
    symbols_info = {s['symbol']: s for s in info['symbols']}

    timestamp = int(time.time() * 1000)
    query = f"timestamp={timestamp}"
    signature = hmac.new(api_secret.encode('utf-8'), query.encode('utf-8'), hashlib.sha256).hexdigest()
    
    try:
        r = requests.get(f"{base_url}/api/v3/account", params={"timestamp": timestamp, "signature": signature}, headers={"X-MBX-APIKEY": api_key})
        account = r.json()
    except Exception as e:
        print(f"❌ Error fetching account: {e}")
        return
    
    if 'balances' not in account:
        print(f"❌ Error fetching account details: {account}")
        return

    for asset in assets_to_sell:
        balance_info = next((b for b in account['balances'] if b['asset'] == asset), None)
        if not balance_info: continue
            
        free = float(balance_info['free'])
        if free <= 0.00000001: continue
            
        symbol = f"{asset}BRL"
        if symbol not in symbols_info: continue

        step_size = 0.00000001
        for f in symbols_info[symbol]['filters']:
            if f['filterType'] == 'LOT_SIZE':
                step_size = float(f['stepSize'])
                break
        
        precision = 0
        if step_size < 1:
            precision = int(round(-math.log10(step_size)))
        
        factor = 10 ** precision
        quantity = math.floor(free * factor) / factor
        
        if quantity <= 0: continue

        print(f"🔍 Found {free} {asset}. Selling {quantity}...")
        
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
                print(f"✅ SUCCESS: Sold {quantity} {asset}")
            else:
                print(f"❌ FAILED: {result}")
        except Exception as e:
            print(f"❌ Error: {e}")

    print("--- 🦾 ZAPIA ORPHAN CLEANUP FINISHED ---")

# Tenta inicializar o cliente
try:
    client = Client(api_key, api_secret)
except Exception as e:
    print(f"❌ ERRO CRÍTICO NA CHAVE: {e}")

def get_price(symbol):
    try:
        return float(client.get_symbol_ticker(symbol=symbol)['price'])
    except:
        return None

def run_zapia_trader():
    # Run cleanup first
    sell_orphans()
    
    print("--- 🦾 ROBÔ ZAPIA TRADER ATUALIZADO ---")
    
    # Teste de Conexão Real
    try:
        client.get_account()
        print("✅ Conexão com Binance: OK!")
    except Exception as e:
        print(f"❌ ERRO DE CONEXÃO: {e}")
        return

    state = {s: {'last_price': get_price(s), 'bought_at': None} for s in symbols}
    
    print(f"💰 Banca: R$ {BANCA_TOTAL_BRL} | Ordem: R$ {VALOR_POR_OPERACAO}")
    print(f"📈 Estratégia: Compra em {BUY_THRESHOLD_VAR}% | Venda em +{SELL_THRESHOLD_VAR}%")
    print(f"👀 Monitorando {len(symbols)} pares: {symbols}")
    print(f"⏱️ Intervalo: {CHECK_INTERVAL}s")

    while True:
        try:
            ativas = [s for s in state if state[s]['bought_at'] is not None]
            vagas = int((BANCA_TOTAL_BRL - (len(ativas) * VALOR_POR_OPERACAO)) // VALOR_POR_OPERACAO)

            for symbol in symbols:
                current_price = get_price(symbol)
                if not current_price: continue
                s = state[symbol]

                if s['bought_at']:
                    if current_price >= s['bought_at'] * PROFIT_TARGET:
                        try:
                            asset = symbol.replace('BRL', '')
                            balance = float(client.get_asset_balance(asset=asset)['free'])
                            client.order_market_sell(symbol=symbol, quantity=balance)
                            print(f"[ZAPIA_EVENTO] VENDA: {symbol} | Preço: R$ {current_price:.2f} | Lucro!")
                            s['bought_at'] = None
                            vagas += 1
                        except Exception as e:
                            print(f"❌ Erro na venda {symbol}: {e}")

                elif vagas > 0:
                    if current_price <= s['last_price'] * BUY_THRESHOLD:
                        try:
                            client.order_market_buy(symbol=symbol, quoteOrderQty=VALOR_POR_OPERACAO)
                            s['bought_at'] = current_price
                            vagas -= 1
                            print(f"[ZAPIA_EVENTO] COMPRA: {symbol} | Preço: R$ {current_price:.2f}")
                        except Exception as e:
                            pass

                if not s['bought_at'] and current_price > s['last_price']:
                    s['last_price'] = current_price

            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"⚠️ Erro no ciclo: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_zapia_trader()
