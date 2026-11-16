import pandas as pd

from app.strategy import generate_signal


def test_strategy_ignores_short_history():
    frame = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=20, freq="15min", tz="UTC"),
        "open": [1.0] * 20, "high": [1.1] * 20,
        "low": [0.9] * 20, "close": [1.0] * 20,
    })
    assert generate_signal(frame) is None


def test_strategy_returns_no_signal_for_flat_market():
    frame = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=100, freq="15min", tz="UTC"),
        "open": [100.0] * 100, "high": [100.1] * 100,
        "low": [99.9] * 100, "close": [100.0] * 100,
    })
    assert generate_signal(frame) is None
