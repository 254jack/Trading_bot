# Gold Trading Bot (XAU/USD)

A risk-first, Python-based gold trading system connected to MetaTrader 5.

## Current stage

**Milestone 1: MT5 connectivity and market-data foundation.** This version is read-only: it connects to an already-running MT5 desktop terminal, inspects the account and XAUUSD symbol, and retrieves candles. It does not submit, modify, or close orders.

## Safety defaults

- Demo account is required for development.
- Order execution is not implemented or enabled.
- No credentials are stored in source control.
- A signal is not an instruction to trade.
- Position sizing rejects trades below the broker's minimum volume when the requested cash risk cannot be respected.

## Requirements

- Windows 10/11
- MetaTrader 5 desktop terminal installed and logged in
- Python 3.10–3.13 (use a version supported by the installed MetaTrader5 package)
- A broker-provided demo account with XAUUSD enabled

## Setup (PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open MT5, log into a **demo** account, ensure the gold instrument is visible in Market Watch, then run:

```powershell
python -m app.main
```

If your broker uses a suffix (for example `XAUUSDm` or `XAUUSD.`), set `MT5_SYMBOL` in `.env` to the exact Market Watch symbol.

## Configuration

See `.env.example`. Leave `MT5_PATH` blank to use the default terminal installation. Never commit `.env`, account passwords, investor passwords, or API tokens.

## Project layout

- `app/mt5_client.py`: MT5 connection, account/symbol diagnostics and candle retrieval.
- `app/market_data.py`: normalized OHLCV data.
- `app/risk.py`: cash-risk position sizing using broker contract metadata.
- `app/main.py`: read-only diagnostic entry point.
- `tests/`: offline tests that do not require MT5.

## Risk policy to validate before any future execution milestone

Initial research settings only: 0.25%–0.5% risk per trade, 1% daily loss stop, one open position, no martingale, no averaging down. These are not guarantees and must be tested against the broker's actual contract size, tick value, minimum volume, spread, commission and slippage.

**No live trading will be added until historical testing, demo forward testing, and explicit approval are complete.**
