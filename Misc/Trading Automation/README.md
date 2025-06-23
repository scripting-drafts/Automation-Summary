# High Risk Auto Trade
  
high_risk_autotrade.py                # Main bot (do NOT import/run in Streamlit!)
streamlit_dashboard.py                # Dashboard ONLY
secret.py                             # API Keys
bot_state.json                        # Shared state file
usdc_symbol_updater.py                # Fetches USDC crypto state
symbols.yaml                          # USDC crypto state

Requirements:  
pip install python-telegram-bot==13.7  
  <br />  

### How does it work
1. Generate symbols.yaml  
2. When the first symbols.yaml gets generated run the bot (python high_risk_autotrade_data-integration.py) while usdc_symbol_updater.py keeps running  
  
  <br />

## Momentum Detection  
The function has_recent_momentum() requires positive price changes on 1m, 5m, and 15m candles (default: +0.3%, +0.6%, +1.0%).
  <br />

## Entry  
The bot will consider buying only if all these timeframes show strong upward movement. This is like what’s shown on the chart—buying during the clear uptrend.
  <br />

## Auto-Sell  
The bot uses both trailing stop logic and a maximum hold time, so if the price reverses sharply (like those red candles after the top in the image), the bot should try to exit quickly.
  <br />

[!(https://i.imgur.com/7oMaPLM.jpeg)]