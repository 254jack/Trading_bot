import pandas as pd
import pytest

from app.market_data import rates_to_frame


def test_rates_are_sorted_and_converted_to_utc():
    rates = [
        (2, 2.0, 3.0, 1.0, 2.5, 20),
        (1, 1.0, 2.0, 0.5, 1.5, 10),
    ]
    # Structured records mirror the fields returned by MetaTrader5.
    dtype = [("time", "i8"), ("open", "f8"), ("high", "f8"),
             ("low", "f8"), ("close", "f8"), ("tick_volume", "i8")]
    frame = rates_to_frame(pd.DataFrame(rates, columns=["time", "open", "high", "low", "close", "tick_volume"]).to_records(index=False))
    assert frame.iloc[0]["time"] < frame.iloc[1]["time"]
    assert str(frame["time"].dt.tz) == "UTC"
    assert "volume" in frame.columns


def test_rejects_invalid_candle_range():
    rates = pd.DataFrame([{"time": 1, "open": 1, "high": 1, "low": 2, "close": 1, "tick_volume": 1}]).to_records(index=False)
    with pytest.raises(ValueError, match="high is below low"):
        rates_to_frame(rates)
