"""Read-only MetaTrader 5 client. No order functions are exposed here."""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime, timezone
from typing import Any


class MT5Error(RuntimeError):
    pass


class MT5Client(AbstractContextManager):
    def __init__(self, terminal_path: str | None = None, require_demo: bool = True):
        self.terminal_path = terminal_path
        self.require_demo = require_demo
        self.mt5: Any = None

    def connect(self) -> None:
        try:
            import MetaTrader5 as mt5
        except ImportError as exc:
            raise MT5Error(
                "MetaTrader5 package is unavailable. Install dependencies on Windows "
                "and run this application on the computer with the MT5 terminal."
            ) from exc

        self.mt5 = mt5
        initialized = mt5.initialize(path=self.terminal_path) if self.terminal_path else mt5.initialize()
        if not initialized:
            error = mt5.last_error()
            self.mt5 = None
            raise MT5Error(f"Could not initialize MT5: {error}")

        account = mt5.account_info()
        if account is None:
            error = mt5.last_error()
            self.close()
            raise MT5Error(f"Could not read MT5 account information: {error}")

        # MT5 ACCOUNT_TRADE_MODE_DEMO is 0. Do not infer demo status from server name.
        if self.require_demo and account.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
            self.close()
            raise MT5Error(
                "Safety check stopped the application: the connected MT5 account is not "
                "identified by MT5 as a demo account. Use a demo account for development."
            )

    def close(self) -> None:
        if self.mt5 is not None:
            self.mt5.shutdown()
            self.mt5 = None

    def __enter__(self) -> "MT5Client":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def account_summary(self) -> dict[str, Any]:
        self._ensure_connected()
        account = self.mt5.account_info()
        if account is None:
            raise MT5Error(f"Could not read account: {self.mt5.last_error()}")
        return {
            "login": account.login,
            "server": account.server,
            "company": account.company,
            "currency": account.currency,
            "balance": float(account.balance),
            "equity": float(account.equity),
            "margin_free": float(account.margin_free),
            "trade_mode": int(account.trade_mode),
        }

    def resolve_symbol(self, requested: str) -> str:
        self._ensure_connected()
        info = self.mt5.symbol_info(requested)
        if info is not None:
            if not info.visible and not self.mt5.symbol_select(requested, True):
                raise MT5Error(f"Could not enable symbol {requested}: {self.mt5.last_error()}")
            return requested

        matches = [s.name for s in self.mt5.symbols_get() or [] if requested.upper() in s.name.upper()]
        if len(matches) == 1:
            if not self.mt5.symbol_select(matches[0], True):
                raise MT5Error(f"Could not enable symbol {matches[0]}: {self.mt5.last_error()}")
            return matches[0]
        if matches:
            raise MT5Error(f"Multiple symbols match {requested}: {', '.join(matches)}. Set MT5_SYMBOL exactly in .env.")
        raise MT5Error(f"Symbol {requested} was not found. Check Market Watch and MT5_SYMBOL.")

    def symbol_summary(self, symbol: str) -> dict[str, Any]:
        self._ensure_connected()
        info = self.mt5.symbol_info(symbol)
        tick = self.mt5.symbol_info_tick(symbol)
        if info is None or tick is None:
            raise MT5Error(f"Could not retrieve symbol metadata/tick for {symbol}: {self.mt5.last_error()}")
        return {
            "symbol": info.name,
            "description": info.description,
            "digits": int(info.digits),
            "point": float(info.point),
            "trade_contract_size": float(info.trade_contract_size),
            "volume_min": float(info.volume_min),
            "volume_max": float(info.volume_max),
            "volume_step": float(info.volume_step),
            "trade_tick_size": float(info.trade_tick_size),
            "trade_tick_value": float(info.trade_tick_value),
            "bid": float(tick.bid),
            "ask": float(tick.ask),
            "spread_price": float(tick.ask - tick.bid),
            "tick_time_utc": datetime.fromtimestamp(tick.time, timezone.utc).isoformat(),
        }

    def candles(self, symbol: str, timeframe: str, count: int):
        self._ensure_connected()
        constants = {
            "M5": self.mt5.TIMEFRAME_M5,
            "M15": self.mt5.TIMEFRAME_M15,
            "M30": self.mt5.TIMEFRAME_M30,
            "H1": self.mt5.TIMEFRAME_H1,
            "H4": self.mt5.TIMEFRAME_H4,
            "D1": self.mt5.TIMEFRAME_D1,
        }
        if timeframe not in constants:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        rates = self.mt5.copy_rates_from_pos(symbol, constants[timeframe], 0, count)
        if rates is None:
            raise MT5Error(f"Could not retrieve {timeframe} candles: {self.mt5.last_error()}")
        if len(rates) == 0:
            raise MT5Error(f"MT5 returned no {timeframe} candles for {symbol}")
        return rates

    def _ensure_connected(self) -> None:
        if self.mt5 is None:
            raise MT5Error("MT5 client is not connected")
