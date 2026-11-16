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
    max_trade_risk_usd: float
    starting_balance_usd: float
    max_cumulative_loss_usd: float
    daily_profit_target_usd: float
    target_balance_usd: float
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
    max_trade_risk = float(os.getenv("MAX_TRADE_RISK_USD", "5.00"))
    starting_balance = float(os.getenv("SMALL_ACCOUNT_START_BALANCE_USD", "50.00"))
    max_loss = float(os.getenv("MAX_CUMULATIVE_LOSS_USD", "30.00"))
    daily_target = float(os.getenv("DAILY_PROFIT_TARGET_USD", "20.00"))
    target_balance = float(os.getenv("SMALL_ACCOUNT_TARGET_BALANCE_USD", "300.00"))
    spread = float(os.getenv("MAX_SPREAD_PRICE", "0.50"))
    poll = int(os.getenv("POLL_SECONDS", "10"))
    if max_trade_risk <= 0:
        raise ValueError("MAX_TRADE_RISK_USD must be positive")
    if starting_balance <= 0 or not 0 < max_loss < starting_balance:
        raise ValueError("Cumulative loss must be positive and smaller than starting balance")
    if daily_target <= 0 or target_balance <= starting_balance:
        raise ValueError("Daily target must be positive and target balance above starting balance")
    if spread <= 0 or not 1 <= poll <= 300:
        raise ValueError("MAX_SPREAD_PRICE must be positive and POLL_SECONDS between 1 and 300")
    return Settings(path, symbol, timeframe, count, _bool("REQUIRE_DEMO_ACCOUNT", "true"),
        mode, _bool("ENABLE_DEMO_TRADING"), max_trade_risk, starting_balance,
        max_loss, daily_target, target_balance, spread, poll)
