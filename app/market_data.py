"""Convert MT5 rate arrays into validated pandas OHLCV frames."""

import pandas as pd


REQUIRED_COLUMNS = {"time", "open", "high", "low", "close", "tick_volume"}


def rates_to_frame(rates) -> pd.DataFrame:
    frame = pd.DataFrame(rates)
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"MT5 rates are missing columns: {sorted(missing)}")
    frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
    frame = frame.rename(columns={"tick_volume": "volume"})
    frame = frame.sort_values("time").drop_duplicates("time").reset_index(drop=True)
    if (frame["high"] < frame["low"]).any():
        raise ValueError("Invalid candle data: high is below low")
    return frame
