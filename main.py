import os
import time
from binance.client import Client
from dotenv import load_dotenv

# Carrega as chaves da Binance
load_dotenv()
api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')
client = Client(api_key, api_secret)

# Configurações do seu investimento
BANCA_TOTAL_BRL = 30.0
VALOR_POR_OPERACAO = 10.0
PROFIT_TARGET = 1.005 # Vende com 0.5% de lucro
BUY_THRESHOLD = 0.995 # Compra com 0.5% de queda

def get_price(symbol):
    return float(client.get_symbol_ticker(symbol=symbol)['price'])

def run_zapia_trader():
    print("--- 🦾 ROBÔ ZAPIA TRADER: MODO MONITORAMENTO ATIVADO ---")
    print("Zapia está vigiando este log para te avisar no WhatsApp.")
    
    # Vamos focar nas 3 principais por enquanto para garantir os R$ 30,00
    symbols = ['BTCBRL', 'ETHBRL', 'SOLBRL']
    state = {s: {'last_price': get_price(s), 'bought_at': None} for s in symbols}
    
    while True:
        try:
            ativas = [s for s in state if state[s]['bought_at'] is not None]
            vagas = int((BANCA_TOTAL_BRL - (len(ativas) * VALOR_POR_OPERACAO)) // VALOR_POR_OPERACAO)

            for symbol in symbols:
                current_price = get_price(symbol)
                s = state[symbol]

                # LÓGICA DE VENDA
                if s['bought_at']:
                    if current_price >= s['bought_at'] * PROFIT_TARGET:
                        asset = symbol.replace('BRL', '')
                        balance = client.get_asset_balance(asset=asset)['free']
                        client.order_market_sell(symbol=symbol, quantity=balance)
                        
                        lucro = (current_price - s['bought_at']) * (VALOR_POR_OPERACAO / s['bought_at'])
                        # EU VOU LER ESTA LINHA ABAIXO:
                        print(f"[ZAPIA_EVENTO] VENDA: {symbol} | Preço: R\( {current_price:.2f} | Lucro: R\) {lucro:.4f}")
                        
                        s['bought_at'] = None
                        s['last_price'] = current_price
                        vagas += 1

                # LÓGICA DE COMPRA
                elif vagas > 0:
                    if current_price <= s['last_price'] * BUY_THRESHOLD:
                        client.order_market_buy(symbol=symbol, quoteOrderQty=VALOR_POR_OPERACAO)
                        s['bought_at'] = current_price
                        vagas -= 1
                        # EU VOU LER ESTA LINHA ABAIXO:
                        print(f"[ZAPIA_EVENTO] COMPRA: {symbol} | Preço: R$ {current_price:.2f}")

                # Atualiza preço de referência se subir sem estarmos comprados
                elif not s['bought_at'] and current_price > s['last_price']:
                    s['last_price'] = current_price

            time.sleep(30) # Checa a cada 30 segundos
        except Exception as e:
            print(f"Erro no ciclo: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_zapia_trader()
    
