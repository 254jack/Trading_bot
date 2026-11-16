"""Risk calculations only; this module never sends orders."""
from dataclasses import dataclass
import math
from collections.abc import Callable
@dataclass(frozen=True)
class PositionSizeResult:
    accepted: bool
    volume: float
    estimated_risk: float
    reason: str
def calculate_position_size(*, equity: float, risk_fraction: float, entry_price: float,
    stop_price: float, tick_size: float, tick_value_per_lot: float, volume_min: float,
    volume_max: float, volume_step: float, risk_budget_cash: float | None = None) -> PositionSizeResult:
    """Size using broker tick metadata; round volume down, never up to minimum."""
    values = (equity, risk_fraction, entry_price, stop_price, tick_size,
              tick_value_per_lot, volume_min, volume_max, volume_step)
    if risk_budget_cash is not None:
        values += (risk_budget_cash,)
    if not all(math.isfinite(float(v)) for v in values):
        return PositionSizeResult(False, 0.0, 0.0, "Non-finite input")
    if equity <= 0 or not 0 < risk_fraction <= 0.01:
        return PositionSizeResult(False, 0.0, 0.0, "Equity or risk fraction is outside allowed bounds")
    if risk_budget_cash is not None and risk_budget_cash <= 0:
        return PositionSizeResult(False, 0.0, 0.0, "Cash risk budget must be positive")
    if tick_size <= 0 or tick_value_per_lot <= 0 or volume_step <= 0:
        return PositionSizeResult(False, 0.0, 0.0, "Invalid broker tick or volume specification")
    if volume_min <= 0 or volume_max < volume_min or entry_price <= 0:
        return PositionSizeResult(False, 0.0, 0.0, "Invalid broker volume or entry specification")
    stop_distance = abs(entry_price - stop_price)
    if stop_distance <= 0:
        return PositionSizeResult(False, 0.0, 0.0, "Stop distance must be positive")
    risk_per_lot = (stop_distance / tick_size) * tick_value_per_lot
    cash_risk = risk_budget_cash if risk_budget_cash is not None else equity * risk_fraction
    raw_volume = cash_risk / risk_per_lot
    steps = math.floor((raw_volume + 1e-12) / volume_step)
    volume = min(volume_max, steps * volume_step)
    if volume + 1e-12 < volume_min:
        min_risk = risk_per_lot * volume_min
        return PositionSizeResult(False, 0.0, min_risk,
            f"Minimum broker volume {volume_min:g} would risk about {min_risk:.2f}, above the {cash_risk:.2f} per-trade limit")
    estimated_risk = risk_per_lot * volume
    if estimated_risk > cash_risk + 1e-8:
        return PositionSizeResult(False, 0.0, estimated_risk, "Rounded volume exceeds risk budget")
    return PositionSizeResult(True, volume, estimated_risk, "Position fits configured cash risk budget")



def calculate_position_size_from_profit(*, volume_min: float, volume_max: float,
    volume_step: float, risk_budget_cash: float,
    loss_at_stop: Callable[[float], float]) -> PositionSizeResult:
    """Size using the broker's own P/L calculator for candidate volumes.

    loss_at_stop(volume) must return the positive cash loss at the stop price
    in the trading account currency. The caller must reject unavailable or
    non-loss results rather than substituting tick-value estimates.
    """
    values = (volume_min, volume_max, volume_step, risk_budget_cash)
    if not all(math.isfinite(float(v)) for v in values):
        return PositionSizeResult(False, 0.0, 0.0, "Non-finite broker sizing input")
    if volume_min <= 0 or volume_max < volume_min or volume_step <= 0 or risk_budget_cash <= 0:
        return PositionSizeResult(False, 0.0, 0.0, "Invalid broker volume or cash risk specification")

    max_steps = math.floor((volume_max - volume_min) / volume_step + 1e-9)

    def checked_loss(volume: float) -> float:
        loss = float(loss_at_stop(volume))
        if not math.isfinite(loss) or loss <= 0:
            raise ValueError("Broker profit calculator returned an invalid stop-loss result")
        return loss

    try:
        min_loss = checked_loss(volume_min)
        if min_loss > risk_budget_cash + 1e-8:
            return PositionSizeResult(False, 0.0, min_loss,
                f"Broker minimum volume {volume_min:g} risks {min_loss:.2f}, above the {risk_budget_cash:.2f} per-trade limit")

        low, high = 0, max_steps
        best_volume, best_loss = volume_min, min_loss
        # Broker P/L is monotonic with volume for a fixed symbol and price.
        while low <= high:
            mid = (low + high) // 2
            volume = round(volume_min + mid * volume_step, 8)
            loss = checked_loss(volume)
            if loss <= risk_budget_cash + 1e-8:
                best_volume, best_loss = volume, loss
                low = mid + 1
            else:
                high = mid - 1
    except Exception:
        return PositionSizeResult(False, 0.0, 0.0, "Broker profit calculator failed or returned invalid data")

    return PositionSizeResult(True, best_volume, best_loss,
        "Position fits broker-calculated cash risk budget")
