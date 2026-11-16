from types import SimpleNamespace

from app.demo_trader import _trailing_stop_price


class FakeMT5:
    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1

    @staticmethod
    def order_calc_profit(order_type, symbol, volume, open_price, close_price):
        direction = 1 if order_type == FakeMT5.ORDER_TYPE_BUY else -1
        return (close_price - open_price) * volume * 100 * direction


def test_buy_trailing_stop_locks_target_cash_profit():
    position = SimpleNamespace(type=FakeMT5.POSITION_TYPE_BUY, volume=1.0, price_open=100.0)
    tick = SimpleNamespace(bid=104.0, ask=104.1)
    info = SimpleNamespace(digits=2, point=0.01, trade_stops_level=10)

    stop = _trailing_stop_price(FakeMT5, position, "XAUUSD", tick, info, 100.0)

    assert stop == 101.0
    assert FakeMT5.order_calc_profit(FakeMT5.ORDER_TYPE_BUY, "XAUUSD", 1.0, 100.0, stop) >= 100.0


def test_sell_trailing_stop_locks_target_cash_profit():
    position = SimpleNamespace(type=FakeMT5.POSITION_TYPE_SELL, volume=1.0, price_open=100.0)
    tick = SimpleNamespace(bid=96.0, ask=96.1)
    info = SimpleNamespace(digits=2, point=0.01, trade_stops_level=10)

    stop = _trailing_stop_price(FakeMT5, position, "XAUUSD", tick, info, 100.0)

    assert stop == 99.0
    assert FakeMT5.order_calc_profit(FakeMT5.ORDER_TYPE_SELL, "XAUUSD", 1.0, 100.0, stop) >= 100.0


def test_trailing_stop_waits_until_broker_minimum_distance_allows_it():
    position = SimpleNamespace(type=FakeMT5.POSITION_TYPE_BUY, volume=1.0, price_open=100.0)
    tick = SimpleNamespace(bid=100.5, ask=100.6)
    info = SimpleNamespace(digits=2, point=0.01, trade_stops_level=100)

    stop = _trailing_stop_price(FakeMT5, position, "XAUUSD", tick, info, 0.0)

    assert stop is None
