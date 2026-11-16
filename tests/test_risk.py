from app.risk import calculate_position_size


def test_rejects_trade_when_minimum_volume_exceeds_risk_budget():
    result = calculate_position_size(
        equity=300, risk_fraction=0.005, entry_price=3000, stop_price=2997,
        tick_size=0.01, tick_value_per_lot=1.0,
        volume_min=0.01, volume_max=100, volume_step=0.01,
    )
    assert result.accepted is False
    assert result.volume == 0
    assert "Minimum broker volume" in result.reason


def test_sizes_position_without_exceeding_risk_budget():
    result = calculate_position_size(
        equity=10000, risk_fraction=0.005, entry_price=3000, stop_price=2999,
        tick_size=0.01, tick_value_per_lot=1.0,
        volume_min=0.01, volume_max=100, volume_step=0.01,
    )
    assert result.accepted is True
    assert result.volume > 0
    assert result.estimated_risk <= 50


def test_rejects_zero_stop_distance():
    result = calculate_position_size(
        equity=300, risk_fraction=0.005, entry_price=3000, stop_price=3000,
        tick_size=0.01, tick_value_per_lot=1.0,
        volume_min=0.01, volume_max=100, volume_step=0.01,
    )
    assert not result.accepted
