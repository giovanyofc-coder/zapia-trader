import os
import time
from binance.client import Client
from dotenv import load_dotenv

# Carrega as chaves da Binance
load_dotenv()
api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')

# Configurações via Environment Variables (com fallbacks)
BANCA_TOTAL_BRL = float(os.getenv('BANCA_TOTAL_BRL', 30.0))
VALOR_POR_OPERACAO = float(os.getenv('VALOR_POR_OPERACAO', 10.0))

# No Railway: SELL_THRESHOLD=1.2 e BUY_THRESHOLD=-0.05
# Interpretamos como porcentagem
SELL_THRESHOLD_VAR = float(os.getenv('SELL_THRESHOLD', 0.5))
BUY_THRESHOLD_VAR = float(os.getenv('BUY_THRESHOLD', -0.5))

PROFIT_TARGET = 1 + (SELL_THRESHOLD_VAR / 100)
BUY_THRESHOLD = 1 + (BUY_THRESHOLD_VAR / 100)

CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 30))
PAIRS_STR = os.getenv('PAIRS', 'BTCBRL,ETHBRL,SOLBRL')
symbols = [s.strip() for s in PAIRS_STR.split(',')]

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
            # Conta quantas posições estão abertas (bought_at não é None)
            ativas = [s for s in state if state[s]['bought_at'] is not None]
            vagas = int((BANCA_TOTAL_BRL - (len(ativas) * VALOR_POR_OPERACAO)) // VALOR_POR_OPERACAO)

            for symbol in symbols:
                current_price = get_price(symbol)
                if not current_price: continue
                s = state[symbol]

                # Se já comprou, verifica se é hora de vender (PROFIT)
                if s['bought_at']:
                    if current_price >= s['bought_at'] * PROFIT_TARGET:
                        try:
                            asset = symbol.replace('BRL', '')
                            balance = float(client.get_asset_balance(asset=asset)['free'])
                            # Vende tudo o que tem do ativo
                            # Nota: Em produção real, precisaria ajustar a precisão (stepSize)
                            client.order_market_sell(symbol=symbol, quantity=balance)
                            print(f"[ZAPIA_EVENTO] VENDA: {symbol} | Preço: R$ {current_price:.2f} | Lucro!")
                            s['bought_at'] = None
                            vagas += 1
                        except Exception as e:
                            print(f"❌ Erro na venda {symbol}: {e}")

                # Se não comprou, verifica se houve a queda necessária e se tem banca
                elif vagas > 0:
                    if current_price <= s['last_price'] * BUY_THRESHOLD:
                        try:
                            client.order_market_buy(symbol=symbol, quoteOrderQty=VALOR_POR_OPERACAO)
                            s['bought_at'] = current_price
                            vagas -= 1
                            print(f"[ZAPIA_EVENTO] COMPRA: {symbol} | Preço: R$ {current_price:.2f}")
                        except Exception as e:
                            # Ignora erros de saldo insuficiente ou ordens mínimas para não travar
                            pass

                # Atualiza o preço de referência para a próxima queda
                # Se o preço sobe, o "last_price" sobe junto (trailing buy)
                if not s['bought_at'] and current_price > s['last_price']:
                    s['last_price'] = current_price

            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"⚠️ Erro no ciclo: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_zapia_trader()
