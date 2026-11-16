import numpy as np
import pandas as pd

from app.strategy import generate_signal


def make_frame(close):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=len(close), freq="15min", tz="UTC"),
        "open": close,
        "high": close + 0.5,
        "low": close - 0.5,
        "close": close,
    })


def test_strategy_ignores_short_history():
    frame = make_frame(np.linspace(100, 101, 20))
    assert generate_signal(frame) is None


def test_strategy_returns_no_signal_for_flat_market():
    frame = make_frame(np.full(100, 100.0))
    assert generate_signal(frame) is None


def test_strategy_generates_buy_in_a_clear_uptrend():
    frame = make_frame(np.linspace(100, 120, 100))
    signal = generate_signal(frame)
    assert signal is not None
    assert signal.side == "BUY"
    assert signal.atr > 0


def test_strategy_generates_sell_in_a_clear_downtrend():
    frame = make_frame(np.linspace(120, 100, 100))
    signal = generate_signal(frame)
    assert signal is not None
    assert signal.side == "SELL"
    assert signal.atr > 0
