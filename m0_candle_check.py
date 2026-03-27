"""Check if the opening candle of the current hour is holding.

The "M0" candle is the first candle of the current hour at the chosen
granularity (M1, M5, M15, etc.).  Subsequent candles of the same
granularity within the hour are checked for violations.

Down candle (close < open) -> check if high has NOT been traded through.
Up candle   (close >= open) -> check if low has NOT been traded through.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .client import OandaClient
    from .models import Candlestick

_GRANULARITY_MINUTES: dict[str, int] = {
    "S5": 1, "S10": 1, "S15": 1, "S30": 1,
    "M1": 1, "M2": 2, "M4": 4, "M5": 5,
    "M10": 10, "M15": 15, "M30": 30,
}


def _parse_candle_time(raw: str) -> datetime:
    ts = raw[:19]
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)


def get_current_hour_candles(
    client: OandaClient,
    instrument: str,
    granularity: str = "M1",
) -> list[Candlestick]:
    now = datetime.now(UTC)
    hour_start = now.replace(minute=0, second=0, microsecond=0)

    gran_minutes = _GRANULARITY_MINUTES.get(granularity, 1)
    candles_per_hour = max(60 // gran_minutes, 1)
    count = candles_per_hour + 1

    candles = client.get_candles(instrument, granularity=granularity, count=count)
    return [c for c in candles if _parse_candle_time(c.time) >= hour_start]


def analyse(candles: list[Candlestick], granularity: str = "M1") -> dict[str, Any]:
    if not candles or not candles[0].mid:
        return {"error": f"No opening {granularity} candle data available for the current hour."}

    m0 = candles[0]
    mid = m0.mid
    assert mid is not None
    m0_open = float(mid.o)
    m0_high = float(mid.h)
    m0_low = float(mid.l)
    m0_close = float(mid.c)

    is_down = m0_close < m0_open
    bias = "DOWN" if is_down else "UP"
    level = m0_high if is_down else m0_low
    level_label = "High" if is_down else "Low"

    subsequent = candles[1:]
    violated = False
    violation_candle: Candlestick | None = None

    for c in subsequent:
        if not c.mid:
            continue
        if is_down and float(c.mid.h) > m0_high:
            violated = True
            violation_candle = c
            break
        if not is_down and float(c.mid.l) < m0_low:
            violated = True
            violation_candle = c
            break

    highest_after = max((float(c.mid.h) for c in subsequent if c.mid), default=None)
    lowest_after = min((float(c.mid.l) for c in subsequent if c.mid), default=None)

    return {
        "granularity": granularity,
        "m0_time": m0.time,
        "m0_open": m0_open,
        "m0_high": m0_high,
        "m0_low": m0_low,
        "m0_close": m0_close,
        "bias": bias,
        "level_label": level_label,
        "level": level,
        "violated": violated,
        "violation_time": violation_candle.time if violation_candle else None,
        "subsequent_count": len(subsequent),
        "highest_after": highest_after,
        "lowest_after": lowest_after,
    }


def print_result(instrument: str, result: dict[str, Any]) -> None:
    if "error" in result:
        print(result["error"])
        return

    gran = result.get("granularity", "M1")
    bias = result["bias"]
    level_label = result["level_label"]
    level = result["level"]
    violated = result["violated"]

    print(f"\n{'='*50}")
    print(f"  {instrument}  {gran} Opening Candle Check")
    print(f"{'='*50}")
    print(f"  Time:   {result['m0_time']}")
    print(f"  Open:   {result['m0_open']}")
    print(f"  High:   {result['m0_high']}")
    print(f"  Low:    {result['m0_low']}")
    print(f"  Close:  {result['m0_close']}")
    print(f"  Bias:   {bias} candle")
    print(f"{'─'*50}")

    if not violated:
        print(f"  {level_label} ({level}) is HOLDING")
        print("  Status: IMBALANCE")
    else:
        print(f"  {level_label} ({level}) has been VIOLATED")
        print(f"  Broken at: {result['violation_time']}")
        print("  Status: BALANCED")

    if result["subsequent_count"] > 0:
        print(f"{'─'*50}")
        if result["highest_after"] is not None:
            print(f"  Post-M0 High: {result['highest_after']}")
        if result["lowest_after"] is not None:
            print(f"  Post-M0 Low:  {result['lowest_after']}")
    else:
        print("  (no subsequent candles yet this hour)")

    print(f"{'='*50}\n")
