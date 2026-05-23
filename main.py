import os
import time
from binance.client import Client
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')
client = Client(api_key, api_secret)

# --- CONFIGURAÇÕES DO GESTOR DE BANCA ---
BANCA_TOTAL_BRL = 30.0       # Sua banca total atualizada
VALOR_POR_OPERACAO = 10.0    # Valor de cada micro-trade (mínimo da Binance)
PROFIT_TARGET = 1.005        # Alvo de 0.5% de lucro
BUY_THRESHOLD = 0.995        # Compra com queda de 0.5%
TOP_N = 10                   # Escaneia as 10 moedas mais fortes em BRL

def get_brl_pairs():
    """Identifica as moedas com mais volume em Reais agora"""
    try:
        tickers = client.get_ticker()
        brl_pairs = [t for t in tickers if t['symbol'].endswith('BRL') and float(t['quoteVolume']) > 100000]
        brl_pairs.sort(key=lambda x: float(x['quoteVolume']), reverse=True)
        return [t['symbol'] for t in brl_pairs[:TOP_N]]
    except:
        return ['BTCBRL', 'ETHBRL', 'SOLBRL', 'BNBBRL']

def get_price(symbol):
    return float(client.get_symbol_ticker(symbol=symbol)['price'])

def run_micro_trader_v3():
    print(f"--- GESTOR DE BANCA ATIVADO (R$ {BANCA_TOTAL_BRL}) ---")
    print(f"Estratégia: Micro-trades de R$ {VALOR_POR_OPERACAO}")
    
    symbols = get_brl_pairs()
    # Inicializa o estado de monitoramento para cada moeda
    state = {s: {'last_price': get_price(s), 'bought_at': None} for s in symbols}
    
    while True:
        try:
            # Verifica quantas operações estão abertas
            ativas = [s for s in state if state[s]['bought_at'] is not None]
            qtd_ativas = len(ativas)
            dinheiro_em_uso = qtd_ativas * VALOR_POR_OPERACAO
            vagas_disponiveis = int((BANCA_TOTAL_BRL - dinheiro_em_uso) // VALOR_POR_OPERACAO)

            print(f"\n[Dashboard] Em uso: R$ {dinheiro_em_uso:.2f} | Vagas Livres: {vagas_disponiveis}")

            for symbol in symbols:
                current_price = get_price(symbol)
                s = state[symbol]
                
                # 1. CHECAR VENDA (REALIZAR LUCRO)
                if s['bought_at']:
                    if current_price >= s['bought_at'] * PROFIT_TARGET:
                        print(f"📈 {symbol}: Meta de lucro atingida! Vendendo...")
                        asset = symbol.replace('BRL', '')
                        balance = client.get_asset_balance(asset=asset)['free']
                        client.order_market_sell(symbol=symbol, quantity=balance)
                        
                        lucro_estimado = (current_price - s['bought_at']) / s['bought_at'] * 100
                        print(f"💰 {symbol}: Venda concluída! Lucro de aprox. {lucro_estimado:.2f}%")
                        
                        s['bought_at'] = None
                        s['last_price'] = current_price
                        vagas_disponiveis += 1 # Libera vaga imediatamente

                # 2. CHECAR COMPRA (APROVEITAR QUEDA)
                elif vagas_disponiveis > 0:
                    if current_price <= s['last_price'] * BUY_THRESHOLD:
                        print(f"📉 {symbol}: Oportunidade detectada! Abrindo micro-trade de R$ {VALOR_POR_OPERACAO}...")
                        client.order_market_buy(symbol=symbol, quoteOrderQty=VALOR_POR_OPERACAO)
                        
                        s['bought_at'] = current_price
                        vagas_disponiveis -= 1 # Ocupa a vaga
                        print(f"✅ {symbol}: Compra realizada a R$ {current_price:.2f}")

                # 3. ATUALIZAR PREÇO BASE (Se a moeda subir sem estarmos nela)
                elif not s['bought_at'] and current_price > s['last_price']:
                    s['last_price'] = current_price

            time.sleep(30) # Monitoramento constante

        except Exception as e:
            print(f"⚠️ Erro no ciclo: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_micro_trader_v3()
