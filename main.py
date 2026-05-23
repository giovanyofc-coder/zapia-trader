import os
import time
import subprocess
from binance.client import Client
from dotenv import load_dotenv

# 1. CARREGA AS CONFIGURAÇÕES
load_dotenv()

api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')
# IMPORTANTE: Adicione a variável MEU_NUMERO no Railway com seu número (ex: 5513997282279)
meu_numero = os.getenv('MEU_NUMERO')

client = Client(api_key, api_secret)

# 2. CONFIGURAÇÕES DO TRADER
BANCA_TOTAL_BRL = 30.0       # Seu limite total
VALOR_POR_OPERACAO = 10.0    # Valor de cada micro-trade
PROFIT_TARGET = 1.005        # Meta de 0.5% de lucro
BUY_THRESHOLD = 0.995        # Compra com queda de 0.5%
TOP_N = 10                   # Monitora as 10 melhores moedas

def notificar(mensagem):
    """Envia mensagem para o seu WhatsApp pessoal"""
    if meu_numero:
        try:
            # Comando que o Zapia usa para enviar WhatsApp
            subprocess.run(['wpp-cli', 'send', meu_numero, mensagem])
            print(f"📢 Log de Notificação: {mensagem}")
        except Exception as e:
            print(f"❌ Erro ao enviar WhatsApp: {e}")
    else:
        print("⚠️ Aviso: Variável MEU_NUMERO não configurada no Railway.")

def get_brl_pairs():
    """Busca as criptos mais ativas em Reais (Volume > 100k)"""
    try:
        tickers = client.get_ticker()
        brl_pairs = [t for t in tickers if t['symbol'].endswith('BRL') and float(t['quoteVolume']) > 100000]
        brl_pairs.sort(key=lambda x: float(x['quoteVolume']), reverse=True)
        return [t['symbol'] for t in brl_pairs[:TOP_N]]
    except:
        return ['BTCBRL', 'ETHBRL', 'SOLBRL']

def get_price(symbol):
    """Pega o preço atual de uma moeda"""
    return float(client.get_symbol_ticker(symbol=symbol)['price'])

def run_zapia_trader():
    print("--- 🦾 INICIANDO ROBÔ ZAPIA TRADER ---")
    notificar("🤖 Robô Zapia Trader ONLINE!\nMonitorando o mercado com R$ 30,00 de banca.")
    
    symbols = get_brl_pairs()
    # Inicializa estado de monitoramento
    state = {s: {'last_price': get_price(s), 'bought_at': None} for s in symbols}
    total_lucro_hoje = 0.0
    ciclos = 0

    while True:
        try:
            ciclos += 1
            # Calcula status da banca
            ativas = [s for s in state if state[s]['bought_at'] is not None]
            qtd_ativas = len(ativas)
            dinheiro_em_uso = qtd_ativas * VALOR_POR_OPERACAO
            vagas = int((BANCA_TOTAL_BRL - dinheiro_em_uso) // VALOR_POR_OPERACAO)

            # Log de resumo a cada 5 minutos
            if ciclos % 10 == 0:
                print(f"\n[DASHBOARD] Em uso: R$ {dinheiro_em_uso:.2f} | Vagas: {vagas}")

            for symbol in symbols:
                current_price = get_price(symbol)
                s = state[symbol]

                # --- LÓGICA DE VENDA ---
                if s['bought_at']:
                    if current_price >= s['bought_at'] * PROFIT_TARGET:
                        asset = symbol.replace('BRL', '')
                        # Pega saldo real de cripto para vender
                        balance = client.get_asset_balance(asset=asset)['free']
                        client.order_market_sell(symbol=symbol, quantity=balance)
                        
                        lucro_brl = (current_price - s['bought_at']) * (VALOR_POR_OPERACAO / s['bought_at'])
                        total_lucro_hoje += lucro_brl

                        notificar(
                            f"💰 LUCRO NO BOLSO!\n"
                            f"Moeda: {symbol}\n"
                            f"Vendido a: R$ {current_price:.2f}\n"
                            f"Rendimento: R$ {lucro_brl:.4f}\n"
                            f"Total Lucrado Hoje: R$ {total_lucro_hoje:.4f}"
                        )
                        s['bought_at'] = None
                        s['last_price'] = current_price
                        vagas += 1

                # --- LÓGICA DE COMPRA ---
                elif vagas > 0:
                    if current_price <= s['last_price'] * BUY_THRESHOLD:
                        client.order_market_buy(symbol=symbol, quoteOrderQty=VALOR_POR_OPERACAO)
                        s['bought_at'] = current_price
                        vagas -= 1

                        notificar(
                            f"📉 COMPRA REALIZADA!\n"
                            f"Moeda: {symbol}\n"
                            f"Entrada: R$ {current_price:.2f}\n"
                            f"Alvo de Venda: R$ {current_price * PROFIT_TARGET:.2f}"
                        )

                # Segue o preço se ele estiver subindo sem estarmos comprados
                elif not s['bought_at'] and current_price > s['last_price']:
                    s['last_price'] = current_price

            time.sleep(30) # Checa a cada 30 segundos

        except Exception as e:
            print(f"⚠️ Erro no ciclo: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_zapia_trader()
    
