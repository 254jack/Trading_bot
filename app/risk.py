"""Risk calculations only; this module never sends orders."""
from dataclasses import dataclass
import math
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
