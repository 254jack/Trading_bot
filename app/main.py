"""Read-only MT5 diagnostics entry point."""

from __future__ import annotations

import json
import sys

from app.config import load_settings
from app.market_data import rates_to_frame
from app.mt5_client import MT5Client, MT5Error


def main() -> int:
    try:
        settings = load_settings()
        with MT5Client(settings.mt5_path, settings.require_demo_account) as client:
            account = client.account_summary()
            symbol = client.resolve_symbol(settings.symbol)
            instrument = client.symbol_summary(symbol)
            rates = client.candles(symbol, settings.timeframe, settings.candle_count)
            frame = rates_to_frame(rates)

            print("MT5 CONNECTION: SUCCESS")
            print("ACCOUNT (sensitive identifiers omitted):")
            print(json.dumps({k: v for k, v in account.items() if k not in {"login"}}, indent=2))
            print("\nGOLD INSTRUMENT SPECIFICATION:")
            print(json.dumps(instrument, indent=2))
            print(f"\n{settings.timeframe} CANDLES: {len(frame)}")
            print(frame.tail(5).to_string(index=False))
            print("\nREAD-ONLY MODE: no orders were submitted or modified.")
        return 0
    except (MT5Error, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
