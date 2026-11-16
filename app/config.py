"""Environment-backed configuration for the gold trading bot."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    mt5_path: str | None
    symbol: str
    timeframe: str
    candle_count: int
    require_demo_account: bool


def load_settings() -> Settings:
    count = int(os.getenv("MT5_CANDLE_COUNT", "300"))
    if not 50 <= count <= 5000:
        raise ValueError("MT5_CANDLE_COUNT must be between 50 and 5000")

    timeframe = os.getenv("MT5_TIMEFRAME", "M15").upper()
    if timeframe not in {"M5", "M15", "M30", "H1", "H4", "D1"}:
        raise ValueError("Unsupported MT5_TIMEFRAME")

    path = os.getenv("MT5_PATH", "").strip() or None
    symbol = os.getenv("MT5_SYMBOL", "XAUUSD").strip()
    if not symbol:
        raise ValueError("MT5_SYMBOL cannot be empty")

    require_demo = os.getenv("REQUIRE_DEMO_ACCOUNT", "true").lower() in {"1", "true", "yes"}
    return Settings(path, symbol, timeframe, count, require_demo)
