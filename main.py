import os
import time
import hmac
import hashlib
import requests
import math
from binance.client import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv

# Carrega as chaves da Binance
load_dotenv()
api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')
base_url = "https://api.binance.com"

# Configurações via Environment Variables (com fallbacks)
BANCA_TOTAL_BRL = float(os.getenv('BANCA_TOTAL_BRL', 40.0))
VALOR_POR_OPERACAO = float(os.getenv('VALOR_POR_OPERACAO', 20.0))

SELL_THRESHOLD_VAR = float(os.getenv('SELL_THRESHOLD', 1.2))
BUY_THRESHOLD_VAR = float(os.getenv('BUY_THRESHOLD', -0.05))

PROFIT_TARGET = 1 + (SELL_THRESHOLD_VAR / 100)
BUY_THRESHOLD = 1 + (BUY_THRESHOLD_VAR / 100)

CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 5))
PAIRS_STR = os.getenv('PAIRS', 'BTCBRL,SOLBRL,ZECBRL')
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

def get_exchange_info():
    try:
        return client.get_exchange_info()
    except Exception as e:
        print(f"Error fetching exchange info: {e}")
        return {}

def sell_orphans():
    # Only sell assets that are NOT part of our main trading pairs
    # assets_to_sell = ["DOGE", "ETH", "SOL", "BTC", "ZEC"]
    # We remove SOL, BTC, ZEC from here to avoid selling active positions on restart
    assets_to_sell = ["DOGE", "ETH"]
    print(f"--- 🦾 ZAPIA ORPHAN CLEANUP START ---")
    
    try:
        account = client.get_account()
        info = get_exchange_info()
        symbols_info = {s['symbol']: s for s in info.get('symbols', [])}
    except Exception as e:
        print(f"❌ Error fetching account: {e}")
        return
    
    for asset in assets_to_sell:
        if asset == 'BRL': continue
        balance_info = next((b for b in account['balances'] if b['asset'] == asset), None)
        if not balance_info: continue
            
        free = float(balance_info['free'])
        if free <= 0: continue
            
        symbol = f"{asset}BRL"
        if symbol not in symbols_info: continue

        # Verify if value exceeds minNotional to avoid Filter failure: NOTIONAL
        price = get_price(symbol)
        if not price: continue
        
        min_notional = 10.0 # Default fallback
        for f in symbols_info[symbol]['filters']:
            if f['filterType'] == 'NOTIONAL':
                min_notional = float(f['minNotional'])
                break
        
        current_notional = free * price
        if current_notional < min_notional:
            # print(f"⚠️ Skipping {asset}: Notional {current_notional:.2f} < {min_notional}")
            continue

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
        
        try:
            result = client.order_market_sell(symbol=symbol, quantity=f"{quantity:.{precision}f}")
            if 'orderId' in result:
                print(f"✅ SUCCESS: Sold {quantity} {asset}")
            else:
                print(f"❌ FAILED: {result}")
        except Exception as e:
            print(f"❌ Error selling {asset}: {e}")

    print("--- 🦾 ZAPIA ORPHAN CLEANUP FINISHED ---")

def run_zapia_trader():
    print("--- 🦾 ROBÔ ZAPIA TRADER V3 ---")
    
    # Teste de Conexão Real
    try:
        client.get_account()
        print("✅ Conexão com Binance: OK!")
    except Exception as e:
        print(f"❌ ERRO DE CONEXÃO: {e}")
        return

    # Detection of existing positions
    print("🔍 Verificando posições abertas...")
    state = {}
    for symbol in symbols:
        asset = symbol.replace('BRL', '')
        try:
            balance = float(client.get_asset_balance(asset=asset)['free'])
            price = get_price(symbol)
            bought_at = None
            if price and (balance * price) > 10.0:
                # Get last buy price from history
                trades = client.get_my_trades(symbol=symbol, limit=10)
                for t in reversed(trades):
                    if t['isBuyer']:
                        bought_at = float(t['price'])
                        break
                print(f"✅ Posição encontrada: {symbol} | Qtd: {balance} | Pago: R$ {bought_at}")
            
            state[symbol] = {
                'last_price': price if price else 0,
                'bought_at': bought_at
            }
        except Exception as e:
            print(f"⚠️ Erro ao inicializar {symbol}: {e}")
            state[symbol] = {'last_price': 0, 'bought_at': None}

    # Fetch minNotionals
    min_notionals = {}
    try:
        info = get_exchange_info()
        for s_info in info.get('symbols', []):
            if s_info['symbol'] in symbols:
                notional = [f for f in s_info['filters'] if f['filterType'] == 'NOTIONAL'][0]
                min_notionals[s_info['symbol']] = float(notional['minNotional'])
                print(f"ℹ️ {s_info['symbol']}: minNotional = {min_notionals[s_info['symbol']]}")
    except Exception as e:
        print(f"⚠️ Erro ao checar minNotional: {e}")

    print(f"💰 Banca: R$ {BANCA_TOTAL_BRL} | Ordem: R$ {VALOR_POR_OPERACAO}")
    print(f"📈 Estratégia: Compra em {BUY_THRESHOLD_VAR}% | Venda em +{SELL_THRESHOLD_VAR}%")
    print(f"⏱️ Intervalo: {CHECK_INTERVAL}s")

    while True:
        try:
            # 1. Check current status
            ativas = [s for s in state if state[s]['bought_at'] is not None]
            
            # 2. Get BRL Balance
            try:
                brl_balance = float(client.get_asset_balance(asset='BRL')['free'])
            except:
                brl_balance = 0
            
            # Vagas based on banca and current active trades
            vagas = int((BANCA_TOTAL_BRL - (len(ativas) * VALOR_POR_OPERACAO)) // VALOR_POR_OPERACAO)
            
            # Don't allow more than total slots even if BRL is high
            max_vagas = int(BANCA_TOTAL_BRL // VALOR_POR_OPERACAO) - len(ativas)
            vagas = min(vagas, max_vagas)

            if time.time() % 60 < CHECK_INTERVAL: # Log status every ~minute
                print(f"--- [STATUS] BRL: {brl_balance:.2f} | Ativas: {len(ativas)} | Vagas: {vagas}")

            for symbol in symbols:
                current_price = get_price(symbol)
                if not current_price: continue
                
                s = state[symbol]

                # LOGIC: SELL
                if s['bought_at']:
                    profit = (current_price / s['bought_at']) - 1
                    if current_price >= s['bought_at'] * PROFIT_TARGET:
                        print(f"🎯 ALVO ATINGIDO: {symbol} | Lucro: {profit*100:.2f}%")
                        try:
                            asset = symbol.replace('BRL', '')
                            balance = float(client.get_asset_balance(asset=asset)['free'])
                            
                            # Info for precision
                            # (Simplified: sell all free balance)
                            client.order_market_sell(symbol=symbol, quantity=balance)
                            print(f"[ZAPIA_EVENTO] VENDA: {symbol} | Preço: R$ {current_price:.2f} | Lucro!")
                            s['bought_at'] = None
                            vagas += 1
                        except Exception as e:
                            print(f"❌ Erro na venda {symbol}: {e}")

                # LOGIC: BUY
                elif vagas > 0:
                    if s['last_price'] > 0 and current_price <= s['last_price'] * BUY_THRESHOLD:
                        # Check if we have enough BRL
                        amount_to_spend = VALOR_POR_OPERACAO
                        
                        # Use available balance if slightly short but above minNotional
                        min_n = min_notionals.get(symbol, 10.0)
                        if brl_balance < amount_to_spend:
                            if brl_balance >= min_n:
                                amount_to_spend = brl_balance
                            else:
                                continue # Not enough BRL for this trade

                        try:
                            print(f"🚀 COMPRANDO: {symbol} | Valor: R$ {amount_to_spend:.2f} | Preço: R$ {current_price:.2f}")
                            client.order_market_buy(symbol=symbol, quoteOrderQty=round(amount_to_spend, 2))
                            s['bought_at'] = current_price
                            vagas -= 1
                            brl_balance -= amount_to_spend
                            print(f"[ZAPIA_EVENTO] COMPRA REALIZADA: {symbol}")
                        except BinanceAPIException as e:
                            print(f"❌ Erro Binance na compra {symbol}: {e.message}")
                            if "insufficient balance" in e.message.lower():
                                # Try to reduce amount slightly for fees?
                                pass
                        except Exception as e:
                            print(f"❌ Erro inesperado na compra {symbol}: {e}")

                # Update trailing price for buying
                if not s['bought_at']:
                    if current_price > s['last_price']:
                        s['last_price'] = current_price

            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"⚠️ Erro no ciclo: {e}")
            time.sleep(60)

if __name__ == "__main__":
    # Cleanup on start (optional but kept for compatibility with previous version)
    try:
        sell_orphans()
    except:
        pass
    run_zapia_trader()
