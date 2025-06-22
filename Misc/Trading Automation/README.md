high_risk_telegram-gainers.py         # Main bot (do NOT import/run in Streamlit!)
streamlit_dashboard.py                # Dashboard ONLY
secret.py                             # Your secrets
bot_state.json                        # Shared state file

Requirements:  
pip install python-telegram-bot==13.7  

  

### How does it work
1. Generate symbols.yaml  
2. When the first symbols.yaml gets generated run the bot (python high_risk_autotrade_data-integration.py) while usdc_symbol_updater.py keeps running  