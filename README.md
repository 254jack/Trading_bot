# Gold Trading Bot (XAU/USD)

A risk-first Python trading system connected to MetaTrader 5.

## Current stages

- MT5 account and market-data connectivity.
- Closed-candle EMA/RSI/ATR strategy research.
- Opt-in demo execution with broker-side stop-loss and take-profit.
- Historical backtesting and forward-demo evaluation remain necessary before any live-money consideration.

## Demo execution safety

The bot will only submit orders when **both** `TRADING_MODE=DEMO` and `ENABLE_DEMO_TRADING=true` are set. It independently verifies that MT5 identifies the connected account as a demo account. The read-only diagnostic command remains `python -m app.main`; the separate execution command is `python -m app.demo_trader`.

Initial limits: maximum 0.5% estimated equity risk per trade, 1% daily realised-loss stop, one position on the gold symbol, spread filter, one entry per candle, mandatory stop-loss and take-profit. Trades below broker minimum volume are rejected rather than rounded up. No martingale, grid, averaging down, or forced entries.

These controls reduce risk but do not guarantee profits or prevent slippage, gaps, rejected stops, terminal/network failures, or losses. Demo results do not predict live performance. Keep the terminal on a demo account and stop the process with Ctrl+C whenever you want.

## Requirements

- Windows 10/11
- MetaTrader 5 desktop terminal installed and logged into a broker demo account
- Python version supported by the installed MetaTrader5 package (Python 3.12 is a tested package target)
- XAUUSD available in Market Watch

## Setup (PowerShell)

```powershell
py -3.12 -m venv env
.\env\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open MT5, log into a **demo** account, and ensure gold is visible in Market Watch. Set the exact symbol name in `.env` if your broker uses a suffix.

Run diagnostics (read-only):

```powershell
python -m app.main
```

To explicitly opt into demo execution, edit `.env` and set:

```env
TRADING_MODE=DEMO
ENABLE_DEMO_TRADING=true
REQUIRE_DEMO_ACCOUNT=true
```

Then run:

```powershell
python -m app.demo_trader
```

The process monitors closed M15 candles and checks for a signal. It does not promise a trade on demand; no-trade is a valid outcome. Keep MT5 open and connected. Press Ctrl+C to stop the bot.

## Strategy

The initial experimental strategy uses EMA 20/50 trend alignment, RSI 14 momentum confirmation, and ATR 14 for stop distance. It trades only on a completed candle. Initial exits target 2R against a 1.5 ATR stop. This is a testable starting hypothesis, not a proven profitable strategy.

## Project layout

- `app/mt5_client.py`: MT5 connection and account/symbol/candle diagnostics.
- `app/market_data.py`: normalized OHLCV data.
- `app/risk.py`: broker-metadata-based position sizing.
- `app/strategy.py`: closed-candle signal calculation.
- `app/demo_trader.py`: guarded demo-only execution loop.
- `app/main.py`: read-only diagnostics.
- `tests/`: offline tests.

Never commit `.env`, account passwords, investor passwords, or API tokens. No live trading mode is implemented.
