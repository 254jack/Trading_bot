"""Environment-backed configuration for the gold trading bot."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    mt5_path: str | None
    symbol: str
    timeframe: str
    candle_count: int
    require_demo_account: bool
    trading_mode: str
    enable_demo_trading: bool
    risk_fraction: float
    daily_loss_fraction: float
    max_spread_price: float
    poll_seconds: int


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

    mode = os.getenv("TRADING_MODE", "READ_ONLY").strip().upper()
    if mode not in {"READ_ONLY", "DEMO"}:
        raise ValueError("TRADING_MODE must be READ_ONLY or DEMO")

    risk = float(os.getenv("RISK_PER_TRADE", "0.005"))
    daily_loss = float(os.getenv("MAX_DAILY_LOSS", "0.01"))
    spread = float(os.getenv("MAX_SPREAD_PRICE", "0.50"))
    poll = int(os.getenv("POLL_SECONDS", "10"))
    if not 0 < risk <= 0.005:
        raise ValueError("RISK_PER_TRADE must be greater than 0 and no more than 0.005 (0.5%)")
    if not 0 < daily_loss <= 0.01:
        raise ValueError("MAX_DAILY_LOSS must be greater than 0 and no more than 0.01 (1%)")
    if spread <= 0 or not 1 <= poll <= 300:
        raise ValueError("MAX_SPREAD_PRICE must be positive and POLL_SECONDS between 1 and 300")

    return Settings(
        path, symbol, timeframe, count,
        _bool("REQUIRE_DEMO_ACCOUNT", "true"),
        mode, _bool("ENABLE_DEMO_TRADING"),
        risk, daily_loss, spread, poll,
    )
