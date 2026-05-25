import os
import time
from zapia_trader_pro import ZapiaTraderPro

# Zapia-Trader PRO Entry Point
# This file initializes the PRO bot and starts the main loop.

def main():
    print("--- 🚀 STARTING ZAPIA-TRADER PRO ---")
    
    # Determine if we should run in dry run mode
    # Defaulting to False (Live) if intended for production on Railway
    dry_run_env = os.getenv('DRY_RUN', 'False').lower() == 'true'
    
    # Initialize the Bot
    bot = ZapiaTraderPro(dry_run=dry_run_env)
    
    # Start the execution loop
    try:
        bot.run()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")
    except Exception as e:
        print(f"❌ Critical Error: {e}")
        time.sleep(60) # Wait before Railway restarts

if __name__ == "__main__":
    main()
