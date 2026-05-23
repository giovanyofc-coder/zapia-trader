import os
import time
from binance.client import Client
from dotenv import load_dotenv

# Carrega as chaves da Binance
load_dotenv()
api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')

# Tenta inicializar o cliente
try:
    client = Client(api_key, api_secret)
except Exception as e:
    print(f"❌ ERRO CRÍTICO NA CHAVE: {e}")

# Configurações
BANCA_TOTAL_BRL = 30.0
VALOR_POR_OPERACAO = 10.0
PROFIT_TARGET = 1.005 # Vende com 0.5% de lucro
BUY_THRESHOLD = 0.995 # Compra com 0.5% de queda

def get_price(symbol):
    try:
        return float(client.get_symbol_ticker(symbol=symbol)['price'])
    except:
        return None

def run_zapia_trader():
    print("--- 🦾 INICIANDO ROBÔ ZAPIA TRADER ---")
    
    # Teste de Conexão Real
    try:
        client.get_account()
        print("✅ Conexão com Binance: OK!")
    except Exception as e:
        print(f"❌ ERRO DE CONEXÃO: Verifique se suas chaves no Railway estão certas. Erro: {e}")
        return

    symbols = ['BTCBRL', 'ETHBRL', 'SOLBRL']
    state = {s: {'last_price': get_price(s), 'bought_at': None} for s in symbols}
    
    print(f"👀 Monitorando: {symbols}")

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
                            # Vende tudo o que comprou
                            client.order_market_sell(symbol=symbol, quantity=balance)
                            print(f"[ZAPIA_EVENTO] VENDA: {symbol} | Preço: R$ {current_price:.2f}")
                            s['bought_at'] = None
                            vagas += 1
                        except Exception as e:
                            print(f"❌ Erro na venda: {e}")

                elif vagas > 0:
                    if current_price <= s['last_price'] * BUY_THRESHOLD:
                        try:
                            client.order_market_buy(symbol=symbol, quoteOrderQty=VALOR_POR_OPERACAO)
                            s['bought_at'] = current_price
                            vagas -= 1
                            print(f"[ZAPIA_EVENTO] COMPRA: {symbol} | Preço: R$ {current_price:.2f}")
                        except Exception as e:
                            print(f"❌ Erro na compra: {e}")

                elif not s['bought_at'] and current_price > s['last_price']:
                    s['last_price'] = current_price

            time.sleep(30)
        except Exception as e:
            print(f"⚠️ Erro no ciclo: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_zapia_trader()
    
