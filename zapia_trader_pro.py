import os
import time
import hmac
import hashlib
import requests
import json
import pandas as pd
import numpy as np
from binance.client import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv

# Zapia-Trader PRO - Rebuilt from scratch
# Features: Trailing Take Profit, 90-day History, Clean Architecture, Persistence

load_dotenv()

class ZapiaTraderPro:
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        self.api_key = os.getenv('BINANCE_API_KEY')
        self.api_secret = os.getenv('BINANCE_API_SECRET')
        
        # Initialize client
        try:
            self.client = Client(self.api_key or "", self.api_secret or "")
        except Exception as e:
            print(f"⚠️ Binance Client Init Warning: {e}")
            self.client = None
        
        # Configuration
        self.banca_total = float(os.getenv('BANCA_TOTAL_BRL', 40.0))
        self.valor_por_operacao = float(os.getenv('VALOR_POR_OPERACAO', 20.0))
        self.pairs = [s.strip() for s in os.getenv('PAIRS', 'BTCBRL,SOLBRL').split(',')]
        
        # Trailing Take Profit Settings
        self.target_profit_pct = float(os.getenv('TARGET_PROFIT_PCT', 1.2)) # Start trailing at 1.2%
        self.trailing_dist_pct = float(os.getenv('TRAILING_DIST_PCT', 0.3)) # Trailing distance
        
        # State & Persistence
        self.state_file = 'trader_state.json'
        self.positions = self.load_state()
        
        # history_days
        self.history_days = 90
        
        # Buy Trigger Logic
        self.buy_trigger_pct = float(os.getenv('BUY_TRIGGER_PCT', -0.25))
        self.last_prices = {}
        
        # Initialize existing positions
        self.initialize_existing_positions()
        
        print(f"🚀 Zapia-Trader PRO Initialized {'(DRY RUN)' if self.dry_run else '(LIVE)'}")
        print(f"💰 Banca: R$ {self.banca_total} | Alocação: R$ {self.valor_por_operacao}")

    def load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_state(self):
        with open(self.state_file, 'w') as f:
            json.dump(self.positions, f, indent=4)

    def get_price(self, symbol):
        # Primary: Binance Client
        if self.client:
            try:
                ticker = self.client.get_symbol_ticker(symbol=symbol)
                return float(ticker['price'])
            except Exception as e:
                print(f"⚠️ Binance Client Price Error for {symbol}: {e}")
        
        # Fallback: Coingecko (for local testing/451 errors)
        try:
            # Simple fallback for BTC/SOL in BRL
            r = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,solana&vs_currencies=brl", timeout=10)
            data = r.json()
            if 'BTC' in symbol.upper(): return float(data['bitcoin']['brl'])
            if 'SOL' in symbol.upper(): return float(data['solana']['brl'])
        except Exception as e:
            print(f"❌ Fallback Price Error for {symbol}: {e}")
        
        return None

    def get_history(self, symbol):
        """Fetch daily history for trend analysis"""
        if self.client:
            try:
                klines = self.client.get_historical_klines(
                    symbol, 
                    Client.KLINE_INTERVAL_1DAY, 
                    f"{self.history_days} days ago UTC"
                )
                df = pd.DataFrame(klines, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_asset_volume', 'number_of_trades',
                    'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
                ])
                df['close'] = df['close'].astype(float)
                return df
            except Exception as e:
                print(f"⚠️ Binance Client History Error for {symbol}: {e}")
        
        # Mock/Simulated history for Dry Run if client fails
        if self.dry_run:
            print(f"📝 Simulating history for {symbol} (Bullish trend)")
            dates = pd.date_range(end=pd.Timestamp.now(), periods=self.history_days)
            prices = np.linspace(100, 150, self.history_days) + np.random.normal(0, 2, self.history_days)
            return pd.DataFrame({'close': prices}, index=dates)
            
        return None

    def analyze_trend(self, symbol):
        """Technical Analysis based on history"""
        df = self.get_history(symbol)
        if df is None or len(df) < 20:
            return "neutral"
        
        # SMA 20 (Short term)
        df['sma20'] = df['close'].rolling(window=20).mean()
        
        last_price = df['close'].iloc[-1]
        last_sma20 = df['sma20'].iloc[-1]
        
        if last_price > last_sma20:
            return "bullish"
        elif last_price < last_sma20:
            return "bearish"
            
        return "neutral"

    def run(self):
        print("🤖 Zapia-Trader PRO: Bot started loop...")
        count = 0
        while True:
            try:
                for symbol in self.pairs:
                    current_price = self.get_price(symbol)
                    if not current_price: 
                        print(f"⚠️ Skipped {symbol} due to missing price.")
                        continue
                    
                    # 1. Manage Active Positions
                    if symbol in self.positions:
                        pos = self.positions[symbol]
                        entry_price = pos['bought_at']
                        max_price = pos.get('max_price', entry_price)
                        
                        # Update peak price if current price is higher
                        if current_price > max_price:
                            self.positions[symbol]['max_price'] = current_price
                            self.save_state()
                            max_price = current_price
                            print(f"📈 {symbol} New High: R$ {max_price:.2f}")
                        
                        # Calculate current profit %
                        profit_pct = (current_price - entry_price) / entry_price * 100
                        
                        print(f"📊 {symbol}: R$ {current_price:.2f} | Lucro: {profit_pct:.2f}% | Topo: R$ {max_price:.2f}")

                        # Trailing Sell Logic
                        if profit_pct >= self.target_profit_pct:
                            # Calculate drop from peak
                            drop_from_peak = (max_price - current_price) / max_price * 100
                            
                            print(f"🎯 {symbol} Target hit! Drop: {drop_from_peak:.2f}% (Limit: {self.trailing_dist_pct}%)")
                            
                            if drop_from_peak >= self.trailing_dist_pct:
                                print(f"[ZAPIA_EVENTO] VENDA TRAILING: {symbol} @ {current_price} | Lucro Final: {profit_pct:.2f}%")
                                success = self.execute_sell(symbol)
                                if success or self.dry_run:
                                    del self.positions[symbol]
                                    self.save_state()
                        
                        # Safety Stop Loss
                        elif profit_pct <= -5.0:
                            print(f"[ZAPIA_EVENTO] STOP LOSS: {symbol} @ {current_price} | Perda: {profit_pct:.2f}%")
                            success = self.execute_sell(symbol)
                            if success or self.dry_run:
                                del self.positions[symbol]
                                self.save_state()

                    # 2. Look for New Opportunities
                    else:
                        # Update peak for buy trigger
                        if symbol not in self.last_prices or current_price > self.last_prices[symbol]:
                            self.last_prices[symbol] = current_price
                        
                        last_max = self.last_prices[symbol]
                        drop_pct = (current_price - last_max) / last_max * 100
                        
                        trend = self.analyze_trend(symbol)
                        
                        # Only buy if trend is bullish AND price has dropped from local peak
                        if trend == "bullish" and drop_pct <= self.buy_trigger_pct:
                            print(f"[ZAPIA_EVENTO] COMPRA INDICADA: {symbol} @ {current_price} | Trend: {trend} | Drop: {drop_pct:.2f}%")
                            success = self.execute_buy(symbol)
                            if success or self.dry_run:
                                self.positions[symbol] = {'bought_at': current_price, 'max_price': current_price}
                                self.save_state()
                                # Clear last_price tracking
                                del self.last_prices[symbol]
                        else:
                            if trend == "bullish":
                                print(f"🔍 {symbol} Bullish but waiting for drop. Current: {current_price:.2f} | Max: {last_max:.2f} | Drop: {drop_pct:.2f}% (Target: {self.buy_trigger_pct}%)")

                count += 1
                if self.dry_run and count >= 1: break # Exit after one loop in dry run
                time.sleep(10)
            except Exception as e:
                print(f"⚠️ Main loop error: {e}")
                time.sleep(60)

    def initialize_existing_positions(self):
        """Transition logic: Load open positions from V3 if available"""
        print("🔍 Checking for existing positions...")
        
        # Hardcoded transition for Giovany
        current_positions = {
            'SOLBRL': 427.40,
            'BTCBRL': 386243.00
        }
        
        for symbol, entry in current_positions.items():
            if symbol not in self.positions:
                has_balance = False
                if self.client:
                    try:
                        balance = self.client.get_asset_balance(asset=symbol.replace('BRL', ''))
                        if balance and (float(balance['free']) > 0 or float(balance['locked']) > 0):
                            has_balance = True
                    except:
                        pass
                
                if has_balance or self.dry_run:
                    print(f"✅ Position for {symbol} active (Entry: {entry})")
                    self.positions[symbol] = {
                        'bought_at': entry,
                        'max_price': entry
                    }
                    self.save_state()

    def execute_buy(self, symbol):
        try:
            print(f"🛒 Executing BUY for {symbol}")
            if self.dry_run:
                print("SIMULATED BUY (Dry Run)")
                return True
            
            if not self.client: return False
            order = self.client.order_market_buy(symbol=symbol, quoteOrderQty=self.valor_por_operacao)
            print(f"[ZAPIA_EVENTO] COMPRA REALIZADA: {symbol} | Order ID: {order['orderId']}")
            return True
        except Exception as e:
            print(f"❌ Buy failed for {symbol}: {e}")
            return False

    def execute_sell(self, symbol):
        try:
            print(f"💰 Executing SELL for {symbol}")
            if self.dry_run:
                print("SIMULATED SELL (Dry Run)")
                return True
            
            if not self.client: return False
            asset = symbol.replace('BRL', '')
            balance = self.client.get_asset_balance(asset=asset)
            qty = float(balance['free'])
            if qty > 0:
                order = self.client.order_market_sell(symbol=symbol, quantity=qty)
                print(f"[ZAPIA_EVENTO] VENDA REALIZADA: {symbol} | Order ID: {order['orderId']}")
                return True
            else:
                print(f"⚠️ No balance to sell for {symbol}")
                return False
        except Exception as e:
            print(f"❌ Sell failed for {symbol}: {e}")
            return False

if __name__ == "__main__":
    bot = ZapiaTraderPro(dry_run=True)
    bot.run()
