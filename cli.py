from __future__ import annotations

import argparse
import json
import os
import sys

from .client import OandaClient, OandaError
from .m0_candle_check import analyse as m0_analyse
from .m0_candle_check import get_current_hour_candles
from .m0_candle_check import print_result as m0_print_result
from .overnight_range import analyse as overnight_analyse
from .overnight_range import get_overnight_candles, get_overnight_window
from .overnight_range import print_result as overnight_print_result

INSTRUMENT = os.environ.get("INSTRUMENT", "NAS100_USD")


def _client() -> OandaClient:
    return OandaClient()


def _print_json(data: object) -> None:
    if hasattr(data, "model_dump"):
        data = data.model_dump(by_alias=True)  # type: ignore[union-attr]
    print(json.dumps(data, indent=2))


# ── subcommands ──────────────────────────────────────────────────

def cmd_account(_args: argparse.Namespace) -> None:
    with _client() as c:
        summary = c.get_account_summary()
        print(f"Account:          {summary.id}")
        print(f"Currency:         {summary.currency}")
        print(f"Balance:          {summary.balance}")
        print(f"NAV:              {summary.nav}")
        print(f"Unrealized P/L:   {summary.unrealized_pl}")
        print(f"Realized P/L:     {summary.pl}")
        print(f"Margin Used:      {summary.margin_used}")
        print(f"Margin Available: {summary.margin_available}")
        print(f"Open Trades:      {summary.open_trade_count}")
        print(f"Open Positions:   {summary.open_position_count}")
        print(f"Pending Orders:   {summary.pending_order_count}")


def cmd_price(args: argparse.Namespace) -> None:
    instrument = args.instrument or INSTRUMENT
    with _client() as c:
        prices = c.get_pricing([instrument])
        for p in prices:
            print(f"{p.instrument}  Bid: {p.best_bid}  Ask: {p.best_ask}  Spread: {p.spread}  ({p.status})")


def cmd_candles(args: argparse.Namespace) -> None:
    instrument = args.instrument or INSTRUMENT
    with _client() as c:
        candles = c.get_candles(instrument, granularity=args.granularity, count=args.count)
        header = f"{'Time':<28} {'Open':>12} {'High':>12} {'Low':>12} {'Close':>12} {'Vol':>6}"
        print(header)
        print("-" * len(header))
        for candle in candles:
            mid = candle.mid
            if mid:
                mark = "*" if not candle.complete else " "
                print(
                    f"{candle.time:<28} {mid.o:>12} {mid.h:>12} {mid.l:>12} {mid.c:>12} {candle.volume:>6}{mark}"
                )


def cmd_buy(args: argparse.Namespace) -> None:
    instrument = args.instrument or INSTRUMENT
    with _client() as c:
        result = c.create_market_order(
            instrument,
            abs(args.units),
            take_profit=args.tp,
            stop_loss=args.sl,
        )
        fill = result.get("orderFillTransaction")
        if fill:
            print(f"FILLED  {instrument}  +{fill['units']}  @ {fill['price']}")
        else:
            _print_json(result)


def cmd_sell(args: argparse.Namespace) -> None:
    instrument = args.instrument or INSTRUMENT
    with _client() as c:
        result = c.create_market_order(
            instrument,
            -abs(args.units),
            take_profit=args.tp,
            stop_loss=args.sl,
        )
        fill = result.get("orderFillTransaction")
        if fill:
            print(f"FILLED  {instrument}  {fill['units']}  @ {fill['price']}")
        else:
            _print_json(result)


def cmd_limit(args: argparse.Namespace) -> None:
    instrument = args.instrument or INSTRUMENT
    units = args.units if args.side == "buy" else -abs(args.units)
    with _client() as c:
        result = c.create_limit_order(
            instrument,
            units,
            args.price,
            take_profit=args.tp,
            stop_loss=args.sl,
        )
        txn = result.get("orderCreateTransaction", {})
        print(f"LIMIT {args.side.upper()}  {instrument}  {txn.get('units', units)}  @ {args.price}  id={txn.get('id')}")


def cmd_stop(args: argparse.Namespace) -> None:
    instrument = args.instrument or INSTRUMENT
    units = args.units if args.side == "buy" else -abs(args.units)
    with _client() as c:
        result = c.create_stop_order(
            instrument,
            units,
            args.price,
            take_profit=args.tp,
            stop_loss=args.sl,
        )
        txn = result.get("orderCreateTransaction", {})
        print(f"STOP {args.side.upper()}  {instrument}  {txn.get('units', units)}  @ {args.price}  id={txn.get('id')}")


def cmd_orders(args: argparse.Namespace) -> None:
    instrument = args.instrument if args.instrument else None
    with _client() as c:
        orders = c.list_pending_orders() if not instrument else c.list_orders(instrument=instrument)
        if not orders:
            print("No pending orders.")
            return
        header = f"{'ID':<8} {'Type':<20} {'Instrument':<14} {'Units':>8} {'Price':>12} {'State':<10}"
        print(header)
        print("-" * len(header))
        for o in orders:
            print(f"{o.id:<8} {o.type:<20} {o.instrument:<14} {o.units:>8} {o.price:>12} {o.state:<10}")


def cmd_cancel(args: argparse.Namespace) -> None:
    with _client() as c:
        result = c.cancel_order(args.order_id)
        txn = result.get("orderCancelTransaction", {})
        print(f"Cancelled order {txn.get('orderID', args.order_id)}")


def cmd_trades(args: argparse.Namespace) -> None:
    instrument = args.instrument if args.instrument else None
    with _client() as c:
        trades = c.list_open_trades(instrument=instrument)
        if not trades:
            print("No open trades.")
            return
        header = f"{'ID':<8} {'Instrument':<14} {'Units':>8} {'Price':>12} {'UPL':>12} {'State':<8}"
        print(header)
        print("-" * len(header))
        for t in trades:
            print(f"{t.id:<8} {t.instrument:<14} {t.current_units:>8} {t.price:>12} {t.unrealized_pl:>12} {t.state:<8}")


def cmd_close(args: argparse.Namespace) -> None:
    units = args.units or "ALL"
    with _client() as c:
        result = c.close_trade(args.trade_id, units=units)
        fill = result.get("orderFillTransaction")
        if fill:
            print(f"Closed trade {args.trade_id}  units={fill['units']}  P/L={fill.get('pl', '?')}")
        else:
            _print_json(result)


def cmd_modify(args: argparse.Namespace) -> None:
    with _client() as c:
        result = c.set_trade_orders(args.trade_id, take_profit=args.tp, stop_loss=args.sl)
        print(f"Modified trade {args.trade_id}")
        if args.tp is not None:
            print(f"  Take Profit: {args.tp}")
        if args.sl is not None:
            print(f"  Stop Loss:   {args.sl}")
        _print_json(result)


def cmd_positions(_args: argparse.Namespace) -> None:
    with _client() as c:
        positions = c.list_open_positions()
        if not positions:
            print("No open positions.")
            return
        header = f"{'Instrument':<14} {'Long':>8} {'Short':>8} {'UPL':>12} {'P/L':>12}"
        print(header)
        print("-" * len(header))
        for p in positions:
            print(
                f"{p.instrument:<14} {p.long.units:>8} {p.short.units:>8} "
                f"{p.unrealized_pl:>12} {p.pl:>12}"
            )


def cmd_prev_hl(args: argparse.Namespace) -> None:
    instrument = args.instrument or INSTRUMENT
    count = 3
    with _client() as c:
        candles = c.get_candles(instrument, granularity=args.granularity, count=count)
        completed = [cd for cd in candles if cd.complete and cd.mid]
        if not completed:
            print(f"No completed {args.granularity} candle found for {instrument}.")
            return
        prev = completed[-1]
        mid = prev.mid
        assert mid is not None
        high = float(mid.h)
        low = float(mid.l)
        print(f"{instrument}  {args.granularity}  Previous Candle")
        print(f"  Time:  {prev.time}")
        print(f"  High:  {mid.h}")
        print(f"  Low:   {mid.l}")
        print(f"  Range: {high - low:.1f}")
        print(f"  Open:  {mid.o}")
        print(f"  Close: {mid.c}")


def cmd_m0_check(args: argparse.Namespace) -> None:
    instrument = args.instrument or INSTRUMENT
    granularity = args.granularity
    with _client() as c:
        candles = get_current_hour_candles(c, instrument, granularity=granularity)
        result = m0_analyse(candles, granularity=granularity)
        m0_print_result(instrument, result)


def cmd_overnight(args: argparse.Namespace) -> None:
    instrument = args.instrument or INSTRUMENT
    granularity = args.granularity
    _, _, in_progress = get_overnight_window()
    with _client() as c:
        candles = get_overnight_candles(c, instrument, granularity=granularity)
        result = overnight_analyse(candles)
        overnight_print_result(instrument, result, in_progress=in_progress)


def cmd_close_position(args: argparse.Namespace) -> None:
    instrument = args.instrument or INSTRUMENT
    with _client() as c:
        result = c.close_position(
            instrument,
            long_units=args.long_units or "NONE",
            short_units=args.short_units or "NONE",
        )
        print(f"Position close request sent for {instrument}")
        _print_json(result)


# ── parser ───────────────────────────────────────────────────────

def _add_instrument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-i", "--instrument", default=None, help=f"Instrument (default: {INSTRUMENT})")


def _add_tp_sl(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tp", type=float, default=None, help="Take profit price")
    parser.add_argument("--sl", type=float, default=None, help="Stop loss price")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oanda", description="OANDA NAS100_USD Trading CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    # account
    sub.add_parser("account", help="Show account summary")

    # price
    p = sub.add_parser("price", help="Get current price")
    _add_instrument(p)

    # candles
    p = sub.add_parser("candles", help="Get OHLC candles")
    _add_instrument(p)
    p.add_argument("-g", "--granularity", default="M1", help="Candle granularity (S5,M1,M5,M15,H1,D,...)")
    p.add_argument("-n", "--count", type=int, default=10, help="Number of candles")

    # buy
    p = sub.add_parser("buy", help="Market buy")
    p.add_argument("units", type=int, help="Number of units to buy")
    _add_instrument(p)
    _add_tp_sl(p)

    # sell
    p = sub.add_parser("sell", help="Market sell")
    p.add_argument("units", type=int, help="Number of units to sell")
    _add_instrument(p)
    _add_tp_sl(p)

    # limit
    p = sub.add_parser("limit", help="Limit order")
    p.add_argument("side", choices=["buy", "sell"])
    p.add_argument("units", type=int, help="Number of units")
    p.add_argument("price", type=float, help="Limit price")
    _add_instrument(p)
    _add_tp_sl(p)

    # stop
    p = sub.add_parser("stop", help="Stop order")
    p.add_argument("side", choices=["buy", "sell"])
    p.add_argument("units", type=int, help="Number of units")
    p.add_argument("price", type=float, help="Stop price")
    _add_instrument(p)
    _add_tp_sl(p)

    # orders
    p = sub.add_parser("orders", help="List pending orders")
    _add_instrument(p)

    # cancel
    p = sub.add_parser("cancel", help="Cancel a pending order")
    p.add_argument("order_id", help="Order ID to cancel")

    # trades
    p = sub.add_parser("trades", help="List open trades")
    _add_instrument(p)

    # close
    p = sub.add_parser("close", help="Close a trade")
    p.add_argument("trade_id", help="Trade ID to close")
    p.add_argument("-u", "--units", default=None, help="Units to close (default: ALL)")

    # modify
    p = sub.add_parser("modify", help="Modify trade TP/SL")
    p.add_argument("trade_id", help="Trade ID to modify")
    _add_tp_sl(p)

    # positions
    sub.add_parser("positions", help="List open positions")

    # m0-check
    p = sub.add_parser("m0-check", help="Opening candle bias and level check")
    _add_instrument(p)
    p.add_argument("-g", "--granularity", default="M1", help="Candle granularity (M1,M5,M15,...) [default: M1]")

    # prev-hl
    p = sub.add_parser("prev-hl", help="Previous time frame high/low")
    _add_instrument(p)
    p.add_argument("-g", "--granularity", default="H1", help="Time frame (M1,M5,M15,H1,H4,D,...) [default: H1]")

    # overnight
    p = sub.add_parser("overnight", help="Overnight session range (22:00-10:00 UTC)")
    _add_instrument(p)
    p.add_argument("-g", "--granularity", default="M5", help="Candle granularity [default: M5]")

    # close-position
    p = sub.add_parser("close-position", help="Close a position")
    _add_instrument(p)
    p.add_argument("--long-units", default=None, help="Long units to close (e.g. ALL or a number)")
    p.add_argument("--short-units", default=None, help="Short units to close (e.g. ALL or a number)")

    return parser


_COMMANDS = {
    "account": cmd_account,
    "price": cmd_price,
    "candles": cmd_candles,
    "buy": cmd_buy,
    "sell": cmd_sell,
    "limit": cmd_limit,
    "stop": cmd_stop,
    "orders": cmd_orders,
    "cancel": cmd_cancel,
    "trades": cmd_trades,
    "close": cmd_close,
    "modify": cmd_modify,
    "positions": cmd_positions,
    "m0-check": cmd_m0_check,
    "overnight": cmd_overnight,
    "prev-hl": cmd_prev_hl,
    "close-position": cmd_close_position,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = _COMMANDS.get(args.command)
    if not handler:
        parser.print_help()
        return 1
    try:
        handler(args)
    except OandaError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyError as exc:
        print(f"Missing environment variable: {exc}", file=sys.stderr)
        print("Set OANDA_API_KEY, OANDA_ACCOUNT_ID, and optionally OANDA_ENV", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
