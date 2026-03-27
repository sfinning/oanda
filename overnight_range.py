"""Calculate the overnight session range (22:00-10:00 UTC).

Fetches candles for the overnight window and reports the high, low,
and range.  If the session is currently in progress, includes data
up to the latest available candle.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .client import OandaClient
    from .models import Candlestick

OVERNIGHT_START_HOUR = 22
OVERNIGHT_END_HOUR = 10


def _fmt_utc(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_candle_time(raw: str) -> datetime:
    ts = raw[:19]
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)


def get_overnight_window() -> tuple[datetime, datetime, bool]:
    """Return (session_start, session_end, in_progress)."""
    now = datetime.now(UTC)

    if now.hour < OVERNIGHT_END_HOUR:
        start = (now - timedelta(days=1)).replace(
            hour=OVERNIGHT_START_HOUR, minute=0, second=0, microsecond=0,
        )
        end = now.replace(hour=OVERNIGHT_END_HOUR, minute=0, second=0, microsecond=0)
        in_progress = True
    elif now.hour < OVERNIGHT_START_HOUR:
        start = (now - timedelta(days=1)).replace(
            hour=OVERNIGHT_START_HOUR, minute=0, second=0, microsecond=0,
        )
        end = now.replace(hour=OVERNIGHT_END_HOUR, minute=0, second=0, microsecond=0)
        in_progress = False
    else:
        start = now.replace(
            hour=OVERNIGHT_START_HOUR, minute=0, second=0, microsecond=0,
        )
        end = (now + timedelta(days=1)).replace(
            hour=OVERNIGHT_END_HOUR, minute=0, second=0, microsecond=0,
        )
        in_progress = True

    return start, end, in_progress


def get_overnight_candles(
    client: OandaClient,
    instrument: str,
    granularity: str = "M5",
) -> list[Candlestick]:
    start, end, in_progress = get_overnight_window()
    effective_end = min(end, datetime.now(UTC)) if in_progress else end
    return client.get_candles(
        instrument,
        granularity=granularity,
        count=None,
        from_time=_fmt_utc(start),
        to_time=_fmt_utc(effective_end),
    )


def analyse(candles: list[Candlestick]) -> dict[str, Any]:
    if not candles:
        return {"error": "No candle data available for the overnight session."}

    mids = [(c, c.mid) for c in candles if c.mid]
    if not mids:
        return {"error": "No mid-price data in overnight candles."}

    highs = [(float(m.h), c) for c, m in mids]
    lows = [(float(m.l), c) for c, m in mids]

    max_val, max_candle = max(highs, key=lambda x: x[0])
    min_val, min_candle = min(lows, key=lambda x: x[0])

    first_time = _parse_candle_time(candles[0].time)
    last_time = _parse_candle_time(candles[-1].time)
    first_mid = mids[0][1]
    last_mid = mids[-1][1]

    return {
        "session_start": candles[0].time,
        "session_end": candles[-1].time,
        "candle_count": len(mids),
        "high": max_val,
        "high_time": max_candle.time,
        "low": min_val,
        "low_time": min_candle.time,
        "range": round(max_val - min_val, 1),
        "open": float(first_mid.o),
        "close": float(last_mid.c),
        "hours_covered": round((last_time - first_time).total_seconds() / 3600, 1),
    }


def print_result(instrument: str, result: dict[str, Any], *, in_progress: bool = False) -> None:
    if "error" in result:
        print(result["error"])
        return

    status = "IN PROGRESS" if in_progress else "COMPLETE"

    print(f"\n{'='*55}")
    print(f"  {instrument}  Overnight Range (22:00-10:00 UTC)")
    print(f"{'='*55}")
    print(f"  Status:  {status}")
    print(f"  From:    {result['session_start']}")
    print(f"  To:      {result['session_end']}")
    print(f"  Candles: {result['candle_count']}  ({result['hours_covered']}h covered)")
    print(f"{'─'*55}")
    print(f"  High:    {result['high']}  ({result['high_time'][:19]})")
    print(f"  Low:     {result['low']}  ({result['low_time'][:19]})")
    print(f"  Range:   {result['range']}")
    print(f"{'─'*55}")
    print(f"  Open:    {result['open']}")
    print(f"  Close:   {result['close']}")
    print(f"{'='*55}\n")
