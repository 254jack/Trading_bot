"""Opt-in, demo-account-only XAUUSD execution loop."""
from __future__ import annotations
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
import sys
import math
import time as time_module
from app.config import load_settings
from app.market_data import rates_to_frame
from app.mt5_client import MT5Client, MT5Error
from app.risk import calculate_position_size_from_profit
from app.strategy import generate_signal
MAGIC = 26111601
COMMENT = "GOLD_DEMO_BOT"

def _daily_net_profit(mt5) -> float:
    """Today's realised net P/L for this bot, including trading costs."""
    now_local = datetime.now(ZoneInfo("Africa/Nairobi"))
    local_start = datetime.combine(now_local.date(), time.min, tzinfo=now_local.tzinfo)
    start = local_start.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    deals = mt5.history_deals_get(start, now)
    if deals is None:
        raise MT5Error(f"Could not read today's deal history: {mt5.last_error()}")
    return sum(float(getattr(d, "profit", 0.0)) + float(getattr(d, "commission", 0.0))
        + float(getattr(d, "swap", 0.0)) + float(getattr(d, "fee", 0.0))
        for d in deals if getattr(d, "magic", None) == MAGIC)

def _already_traded_this_candle(mt5, candle_epoch: int) -> bool:
    now = datetime.now(timezone.utc)
    start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    orders = mt5.history_orders_get(start, now)
    if orders is None:
        raise MT5Error(f"Could not read order history: {mt5.last_error()}")
    return any(getattr(o, "magic", None) == MAGIC and int(getattr(o, "time_setup", 0)) >= candle_epoch for o in orders)

def _normalise_price(price: float, digits: int) -> float:
    return round(price, digits)


TRAILING_TRIGGER_USD = 2.00
TRAILING_GIVEBACK_USD = 1.00


def _profit_at_close_price(mt5, position, symbol: str, close_price: float) -> float:
    order_type = (mt5.ORDER_TYPE_BUY if position.type == mt5.POSITION_TYPE_BUY
        else mt5.ORDER_TYPE_SELL)
    result = mt5.order_calc_profit(
        order_type, symbol, float(position.volume), float(position.price_open), close_price)
    if result is None:
        raise MT5Error(f"Could not calculate trailing-stop P/L: {mt5.last_error()}")
    value = float(result)
    if not math.isfinite(value):
        raise MT5Error("Broker returned a non-finite trailing-stop P/L")
    return value


def _trailing_stop_price(mt5, position, symbol: str, tick, info,
                         target_profit: float) -> float | None:
    """Find a broker-calculated stop price that locks at least target_profit USD."""
    digits = int(info.digits)
    min_distance = float(getattr(info, "trade_stops_level", 0)) * float(info.point)
    if position.type == mt5.POSITION_TYPE_BUY:
        low = float(position.price_open)
        high = float(tick.bid) - min_distance
        if high <= low:
            return None
        if _profit_at_close_price(mt5, position, symbol, high) < target_profit:
            return None
        for _ in range(60):
            mid = (low + high) / 2
            if _profit_at_close_price(mt5, position, symbol, mid) >= target_profit:
                high = mid
            else:
                low = mid
        candidate = _normalise_price(high, digits)
        if candidate > float(tick.bid) - min_distance + float(info.point) / 2:
            return None
    else:
        low = float(tick.ask) + min_distance
        high = float(position.price_open)
        if low >= high:
            return None
        if _profit_at_close_price(mt5, position, symbol, low) < target_profit:
            return None
        for _ in range(60):
            mid = (low + high) / 2
            if _profit_at_close_price(mt5, position, symbol, mid) >= target_profit:
                low = mid
            else:
                high = mid
        candidate = _normalise_price(low, digits)
        if candidate < float(tick.ask) + min_distance - float(info.point) / 2:
            return None
    if _profit_at_close_price(mt5, position, symbol, candidate) + 1e-8 < target_profit:
        return None
    return candidate


def _manage_trailing_stops(mt5, symbol: str) -> None:
    """After +$2 floating P/L, trail the broker-side SL with a $1 cash giveback.

    No fixed take-profit is used: the stop progressively locks more profit
    while allowing a winning position to continue running.
    """
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        raise MT5Error(f"Could not inspect positions for trailing stops: {mt5.last_error()}")
    owned = [p for p in positions if getattr(p, "magic", None) == MAGIC]
    if not owned:
        return
    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    if info is None or tick is None:
        raise MT5Error(f"Missing symbol/tick data for trailing stop: {mt5.last_error()}")
    for position in owned:
        floating_profit = float(getattr(position, "profit", 0.0))
        if floating_profit < TRAILING_TRIGGER_USD:
            continue
        # At +$2, aim to protect +$1; increase the protected amount as
        # floating profit grows, while keeping the broker-side TP disabled.
        lock_target = max(0.0, floating_profit - TRAILING_GIVEBACK_USD)
        new_stop = _trailing_stop_price(mt5, position, symbol, tick, info, lock_target)
        if new_stop is None:
            print(f"TRAILING WAIT: ticket={position.ticket}; +{floating_profit:.2f} USD reached, "
                  "but broker stop-distance rules do not yet allow the protective stop.")
            continue
        old_stop = float(getattr(position, "sl", 0.0))
        point = float(info.point)
        improves = (new_stop > old_stop + point / 2 if position.type == mt5.POSITION_TYPE_BUY
            else old_stop == 0.0 or new_stop < old_stop - point / 2)
        if not improves:
            continue
        request = {"action": mt5.TRADE_ACTION_SLTP, "symbol": symbol,
            "position": int(position.ticket), "sl": new_stop,
            "tp": float(getattr(position, "tp", 0.0))}
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"TRAILING UPDATE FAILED: ticket={position.ticket}; "
                  f"response={getattr(result, 'comment', None) or mt5.last_error()}")
            continue
        locked = _profit_at_close_price(mt5, position, symbol, new_stop)
        print(f"TRAILING STOP UPDATED: ticket={position.ticket}; floating=+{floating_profit:.2f} USD; "
              f"SL={new_stop:.{int(info.digits)}f}; approx. price P/L protected=+{locked:.2f} USD; "
              "fixed TP disabled.")


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
    daily_profit = _daily_net_profit(mt5)
    if daily_profit >= settings.daily_profit_target_usd:
        print(f"DAILY TARGET REACHED: realised net profit {daily_profit:.2f} USD; no more entries today.")
        return
    floor = settings.starting_balance_usd - settings.max_cumulative_loss_usd
    if account["equity"] <= floor:
        print(f"MAXIMUM CUMULATIVE LOSS REACHED: equity {account['equity']:.2f}; hard floor {floor:.2f}. Bot stopped.")
        raise SystemExit(0)
    if account["balance"] >= settings.target_balance_usd:
        print(f"GROWTH TARGET REACHED: balance {account['balance']:.2f}; bot stopped.")
        raise SystemExit(0)
    spread = float(tick.ask) - float(tick.bid)
    if spread > settings.max_spread_price:
        print(f"NO TRADE: spread {spread:.3f} exceeds limit {settings.max_spread_price:.3f}")
        return
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        raise MT5Error(f"Could not inspect open positions: {mt5.last_error()}")
    if len(positions):
        print("NO TRADE: an open position already exists on this gold symbol.")
        return
    if _already_traded_this_candle(mt5, last_candle_epoch):
        print("NO TRADE: this candle already has a bot order.")
        return
    frame = rates_to_frame(client.candles(symbol, settings.timeframe, settings.candle_count))
    signal = generate_signal(frame)
    if signal is None:
        print("NO SIGNAL: strategy conditions are not aligned.")
        return
    is_buy = signal.side == "BUY"
    entry = float(tick.ask if is_buy else tick.bid)
    stop_distance = signal.atr * 0.5
    stop = entry - stop_distance if is_buy else entry + stop_distance
    # $5 max estimated risk per position, further capped by remaining room above $20.
    remaining_loss = account["equity"] - floor
    cash_budget = min(settings.max_trade_risk_usd, remaining_loss)
    if cash_budget <= 0:
        print("MAXIMUM CUMULATIVE LOSS REACHED: no risk budget remains.")
        raise SystemExit(0)
    order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL

    def broker_stop_loss_cash(candidate_volume: float) -> float:
        result = mt5.order_calc_profit(order_type, symbol, candidate_volume, entry, stop)
        if result is None:
            raise RuntimeError(f"MT5 order_calc_profit failed: {mt5.last_error()}")
        result = float(result)
        if not result < 0:
            raise RuntimeError(f"MT5 returned a non-loss value for the stop price: {result}")
        return abs(result)

    size = calculate_position_size_from_profit(
        volume_min=float(info.volume_min), volume_max=float(info.volume_max),
        volume_step=float(info.volume_step), risk_budget_cash=cash_budget,
        loss_at_stop=broker_stop_loss_cash)
    if not size.accepted:
        print(f"REJECTED: {size.reason}. No order was sent.")
        return
    digits = int(info.digits)
    stop = _normalise_price(stop, digits)
    min_stop = float(getattr(info, "trade_stops_level", 0)) * float(info.point)
    if abs(entry - stop) < min_stop:
        print("REJECTED: calculated stop is inside the broker's minimum stop distance.")
        return
    # Independently verify both monetary outcomes with the broker calculator.
    verified_risk = broker_stop_loss_cash(size.volume)
    if verified_risk > cash_budget + 1e-8:
        print(f"REJECTED: broker-calculated stop risk {verified_risk:.2f} exceeds budget {cash_budget:.2f}.")
        return
    # TP=0 disables a fixed broker-side take-profit. The trailing manager
    # progressively adjusts the broker-side SL as the position gains.
    request = {"action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": size.volume,
        "type": order_type,
        "price": _normalise_price(entry, digits), "sl": stop, "tp": 0.0,
        "deviation": 30, "magic": MAGIC, "comment": COMMENT,
        "type_time": mt5.ORDER_TIME_GTC, "type_filling": _filling_mode(mt5, info)}
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
    print(f"DEMO ORDER {signal.side} accepted: ticket={result.order}, volume={size.volume:.2f}, "
        f"entry={entry:.{digits}f}, SL={stop:.{digits}f}, fixed TP=disabled, "
        f"broker-calculated risk={verified_risk:.2f} USD. Daily net={daily_profit:.2f}; "
        f"daily target={settings.daily_profit_target_usd:.2f}. Signal: {signal.reason}")

def main() -> int:
    try:
        settings = load_settings()
        if settings.trading_mode != "DEMO" or not settings.enable_demo_trading:
            raise ValueError("Trading is disabled. Set TRADING_MODE=DEMO and ENABLE_DEMO_TRADING=true in .env.")
        if not settings.require_demo_account:
            raise ValueError("REQUIRE_DEMO_ACCOUNT must remain true for this demo trading build.")
        import MetaTrader5 as mt5
        with MT5Client(settings.mt5_path, require_demo=True) as client:
            account = client.account_summary()
            if account["trade_mode"] != mt5.ACCOUNT_TRADE_MODE_DEMO:
                raise MT5Error("Hard safety stop: MT5 does not identify this as a demo account.")
            if account["currency"] != "USD":
                raise MT5Error(f"This small-account plan requires a USD account, not {account['currency']}.")
            symbol = client.resolve_symbol(settings.symbol)
            floor = settings.starting_balance_usd - settings.max_cumulative_loss_usd
            print(f"DEMO TRADING ACTIVE | server={account['server']} | balance={account['balance']:.2f} "
                f"| equity={account['equity']:.2f} USD | symbol={symbol} | timeframe={settings.timeframe}")
            print(f"Small-account plan: max trade risk USD {settings.max_trade_risk_usd:.2f}; "
                f"daily realised net target USD {settings.daily_profit_target_usd:.2f}; "
                f"hard equity floor USD {floor:.2f}; stop at balance USD {settings.target_balance_usd:.2f}.")
            print("Demo account only. Every order requires a broker-side SL; fixed TP is disabled. "
                  "Trailing protection starts at +$2 floating profit with a $1 giveback. Ctrl+C stops new entries.")
            timeframe_seconds = {"M5": 300, "M15": 900, "M30": 1800,
                "H1": 3600, "H4": 14400, "D1": 86400}[settings.timeframe]
            last_checked_candle = None
            while True:
                account = client.account_summary()
                _manage_trailing_stops(mt5, symbol)
                if account["equity"] <= floor:
                    print(f"MAXIMUM CUMULATIVE LOSS REACHED: equity {account['equity']:.2f}; floor {floor:.2f}. Bot stopped.")
                    break
                if account["balance"] >= settings.target_balance_usd:
                    print(f"GROWTH TARGET REACHED: balance {account['balance']:.2f} USD. Bot stopped.")
                    break
                frame = rates_to_frame(client.candles(symbol, settings.timeframe, settings.candle_count))
                candle_epoch = int(frame.iloc[-2]["time"].timestamp())
                if candle_epoch != last_checked_candle:
                    last_checked_candle = candle_epoch
                    print(f"\nChecking completed candle: {frame.iloc[-2]['time']}")
                    _try_trade(mt5, client, settings, symbol, candle_epoch + timeframe_seconds)
                time_module.sleep(settings.poll_seconds)
    except KeyboardInterrupt:
        print("\nDemo trader stopped by user. Any open position retains its broker-side SL; "
              "the bot's trailing management stops until restarted.")
        return 0
    except (MT5Error, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
if __name__ == "__main__":
    raise SystemExit(main())
