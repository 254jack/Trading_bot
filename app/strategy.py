"""Simple experimental XAUUSD strategy evaluated on completed candles only."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Signal:
    side: str
    atr: float
    candle_time: object
    reason: str


def generate_signal(frame: pd.DataFrame) -> Signal | None:
    if len(frame) < 60:
        return None
    data = frame.copy()
    close = data["close"].astype(float)
    high = data["high"].astype(float)
    low = data["low"].astype(float)

    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rs = gain / loss.where(loss != 0)
    rsi = 100 - (100 / (1 + rs))
    previous_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = true_range.ewm(alpha=1 / 14, adjust=False).mean()

    # MT5's final row is the still-forming candle; use the prior completed bar.
    i = len(data) - 2
    values = [ema20.iloc[i], ema50.iloc[i], rsi.iloc[i], atr.iloc[i], close.iloc[i]]
    if any(pd.isna(value) for value in values) or atr.iloc[i] <= 0:
        return None

    if ema20.iloc[i] > ema50.iloc[i] and close.iloc[i] > ema20.iloc[i] and 52 <= rsi.iloc[i] <= 68:
        return Signal("BUY", float(atr.iloc[i]), data.iloc[i]["time"], "EMA20 above EMA50; close above EMA20; RSI bullish")
    if ema20.iloc[i] < ema50.iloc[i] and close.iloc[i] < ema20.iloc[i] and 32 <= rsi.iloc[i] <= 48:
        return Signal("SELL", float(atr.iloc[i]), data.iloc[i]["time"], "EMA20 below EMA50; close below EMA20; RSI bearish")
    return None
