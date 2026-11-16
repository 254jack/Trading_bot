"""Opt-in, demo-account-only XAUUSD execution loop."""

from __future__ import annotations

from datetime import datetime, time, timezone
import math
import sys
import time as time_module

from app.config import load_settings
from app.market_data import rates_to_frame
from app.mt5_client import MT5Client, MT5Error
from app.risk import calculate_position_size
from app.strategy import generate_signal


MAGIC = 26111601
COMMENT = "GOLD_DEMO_BOT"


def _timeframe_constant(mt5, name: str):
    return {
        "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1,
    }[name]


def _daily_realised_loss(mt5, currency: str) -> float:
    now = datetime.now(timezone.utc)
    start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    deals = mt5.history_deals_get(start, now)
    if deals is None:
        raise MT5Error(f"Could not read today's deal history: {mt5.last_error()}")
    pnl = sum(
        float(getattr(deal, "profit", 0.0))
        + float(getattr(deal, "commission", 0.0))
        + float(getattr(deal, "swap", 0.0))
        + float(getattr(deal, "fee", 0.0))
        for deal in deals
        if getattr(deal, "magic", None) == MAGIC
    )
    return max(0.0, -pnl)


def _already_traded_this_candle(mt5, candle_epoch: int) -> bool:
    now = datetime.now(timezone.utc)
    start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    orders = mt5.history_orders_get(start, now)
    if orders is None:
        raise MT5Error(f"Could not read order history: {mt5.last_error()}")
    return any(
        getattr(order, "magic", None) == MAGIC
        and int(getattr(order, "time_setup", 0)) >= candle_epoch
        for order in orders
    )


def _normalise_price(price: float, digits: int) -> float:
    return round(price, digits)


def _filling_mode(mt5, info):
    flags = int(getattr(info, "filling_mode", 0))
    if flags & getattr(mt5, "SYMBOL_FILLING_IOC", 2):
        return mt5.ORDER_FILLING_IOC
    if flags & getattr(mt5, "SYMBOL_FILLING_FOK", 1):
        return mt5.ORDER_FILLING_FOK
    return mt5.ORDER_FILLING_RETURN


def _try_trade(mt5, client, settings, symbol: str, last_candle_epoch: int) -> None:
    account = client.account_summary()
    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    if info is None or tick is None:
        raise MT5Error(f"Missing symbol/tick data: {mt5.last_error()}")

    if float(tick.ask) - float(tick.bid) > settings.max_spread_price:
        print(f"NO TRADE: spread {tick.ask - tick.bid:.3f} exceeds limit {settings.max_spread_price:.3f}")
        return

    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        raise MT5Error(f"Could not inspect open positions: {mt5.last_error()}")
    if len(positions) > 0:
        print("NO TRADE: an open position already exists on this gold symbol.")
        return

    if _already_traded_this_candle(mt5, last_candle_epoch):
        print("NO TRADE: this candle already has a bot order.")
        return

    daily_loss = _daily_realised_loss(mt5, account["currency"])
    daily_limit = account["equity"] * settings.daily_loss_fraction
    if daily_loss >= daily_limit:
        print(f"DAILY STOP: realised loss {daily_loss:.2f} reached limit {daily_limit:.2f} {account['currency']}.")
        return

    rates = client.candles(symbol, settings.timeframe, settings.candle_count)
    frame = rates_to_frame(rates)
    signal = generate_signal(frame)
    if signal is None:
        print("NO SIGNAL: strategy conditions are not aligned.")
        return

    is_buy = signal.side == "BUY"
    entry = float(tick.ask if is_buy else tick.bid)
    stop_distance = signal.atr * 1.5
    target_distance = stop_distance * 2.0
    stop = entry - stop_distance if is_buy else entry + stop_distance
    target = entry + target_distance if is_buy else entry - target_distance

    tick_size = float(info.trade_tick_size)
    tick_value = float(getattr(info, "trade_tick_value_loss", 0.0) or info.trade_tick_value)
    if tick_size <= 0 or tick_value <= 0:
        print("REJECTED: broker tick size/value is unavailable.")
        return

    size = calculate_position_size(
        equity=account["equity"],
        risk_fraction=settings.risk_fraction,
        entry_price=entry,
        stop_price=stop,
        tick_size=tick_size,
        tick_value_per_lot=tick_value,
        volume_min=float(info.volume_min),
        volume_max=float(info.volume_max),
        volume_step=float(info.volume_step),
    )
    if not size.accepted:
        print(f"REJECTED: {size.reason}. Estimated minimum-lot risk may exceed the budget.")
        return

    digits = int(info.digits)
    stop = _normalise_price(stop, digits)
    target = _normalise_price(target, digits)
    min_stop = float(getattr(info, "trade_stops_level", 0)) * float(info.point)
    if abs(entry - stop) < min_stop or abs(target - entry) < min_stop:
        print("REJECTED: calculated stop/target is inside the broker's minimum stop distance.")
        return

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": size.volume,
        "type": mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
        "price": _normalise_price(entry, digits),
        "sl": stop,
        "tp": target,
        "deviation": 30,
        "magic": MAGIC,
        "comment": COMMENT,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": _filling_mode(mt5, info),
    }
    checked = mt5.order_check(request)
    if checked is None or getattr(checked, "retcode", None) not in (0, mt5.TRADE_RETCODE_DONE):
        print(f"ORDER CHECK REJECTED: {getattr(checked, 'comment', None) or mt5.last_error()}")
        return

    result = mt5.order_send(request)
    if result is None:
        print(f"ORDER FAILED: {mt5.last_error()}")
        return
    if result.retcode not in (mt5.TRADE_RETCODE_DONE, getattr(mt5, "TRADE_RETCODE_PLACED", -1)):
        print(f"ORDER REJECTED: retcode={result.retcode}, comment={result.comment}")
        return

    print(
        f"DEMO ORDER {signal.side} accepted: ticket={result.order}, volume={size.volume:.2f}, "
        f"entry={entry:.{digits}f}, SL={stop:.{digits}f}, TP={target:.{digits}f}, "
        f"estimated risk={size.estimated_risk:.2f} {account['currency']}. "
        f"Signal: {signal.reason}"
    )


def main() -> int:
    try:
        settings = load_settings()
        if settings.trading_mode != "DEMO" or not settings.enable_demo_trading:
            raise ValueError(
                "Trading is disabled. Set TRADING_MODE=DEMO and ENABLE_DEMO_TRADING=true "
                "in .env to explicitly enable demo orders."
            )
        if not settings.require_demo_account:
            raise ValueError("REQUIRE_DEMO_ACCOUNT must remain true for this demo trading build.")

        import MetaTrader5 as mt5

        with MT5Client(settings.mt5_path, require_demo=True) as client:
            account = client.account_summary()
            if account["trade_mode"] != mt5.ACCOUNT_TRADE_MODE_DEMO:
                raise MT5Error("Hard safety stop: MT5 does not identify this as a demo account.")
            symbol = client.resolve_symbol(settings.symbol)
            print(
                f"DEMO TRADING ACTIVE | server={account['server']} | currency={account['currency']} "
                f"| equity={account['equity']:.2f} | symbol={symbol} | timeframe={settings.timeframe}"
            )
            print(
                f"Risk/trade <= {settings.risk_fraction:.2%}; daily realised-loss stop="
                f"{settings.daily_loss_fraction:.2%}; max spread={settings.max_spread_price:.2f}. "
                "Ctrl+C stops new entries."
            )
            timeframe_seconds = {
                "M5": 300, "M15": 900, "M30": 1800,
                "H1": 3600, "H4": 14400, "D1": 86400,
            }[settings.timeframe]
            last_checked_candle = None
            while True:
                rates = client.candles(symbol, settings.timeframe, settings.candle_count)
                frame = rates_to_frame(rates)
                # Last row is forming; second-last row is the latest closed candle.
                candle_epoch = int(frame.iloc[-2]["time"].timestamp())
                if candle_epoch != last_checked_candle:
                    last_checked_candle = candle_epoch
                    print(f"\nChecking completed candle: {frame.iloc[-2]['time']}")
                    _try_trade(mt5, client, settings, symbol, candle_epoch + timeframe_seconds)
                time_module.sleep(settings.poll_seconds)
    except KeyboardInterrupt:
        print("\nDemo trader stopped by user. Any open position retains its broker-side SL/TP.")
        return 0
    except (MT5Error, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
