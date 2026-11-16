# Gold Trading Bot (XAU/USD)

Python trading system connected to MetaTrader 5. Current execution is demo-account-only.

## Small-account demo plan

Defaults are for a dedicated USD $50 demo account:
- Stop opening trades for the day after $20 net realised profit from this bot.
- Stop the bot if account equity reaches $20, $30 below the configured $50 starting balance.
- Stop the bot when account balance reaches $300.
- Estimated risk is capped at $5 per trade and further limited by remaining room above the $20 equity floor.
- One open XAUUSD position at a time, spread filter, one entry per candle, mandatory broker-side SL and TP.

The $20 daily target is not guaranteed. A $5 per-trade cap is 10% of the initial $50 and is highly aggressive. Slippage, gaps, commissions, swaps, execution failures, or broker stop handling can cause actual losses to exceed estimates. The equity floor cannot guarantee a maximum loss during fast markets.

This configuration is for demo testing only and must not be copied to a live account.

## Demo execution safety

Orders are submitted only when both TRADING_MODE=DEMO and ENABLE_DEMO_TRADING=true are set. MT5 demo-account mode is independently verified, and the plan requires USD account currency. Read-only diagnostics: python -m app.main. Demo execution: python -m app.demo_trader.

## Setup

Windows 10/11, MetaTrader 5 desktop demo account, XAUUSD visible in Market Watch. Python 3.12 is a tested package target.

```powershell
py -3.12 -m venv env
.\env\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set the exact broker symbol in .env if it has a suffix. To enable demo orders set TRADING_MODE=DEMO, ENABLE_DEMO_TRADING=true, REQUIRE_DEMO_ACCOUNT=true, then run python -m app.demo_trader. The bot evaluates completed candles and does not force entries. Press Ctrl+C to stop.

## Strategy

Experimental EMA 20/50 trend alignment, RSI 14 momentum, ATR 14 stop distance; completed candles only. Initial exits target 2R against a 1.5 ATR stop. This is not a proven profitable strategy.

Never commit .env, passwords, or tokens. No live trading mode is implemented.
