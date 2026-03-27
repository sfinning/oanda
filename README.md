
## OANDA API CLI Spec

### Overview
A Python CLI wrapping the OANDA REST-v20 API, living in `src/oanda/`. Uses `httpx` (already installed) for HTTP, `argparse` for CLI parsing, and outputs JSON to stdout.

### Auth & Config
- API token read from env var `OANDA_API_KEY`
- Account ID from env var `OANDA_ACCOUNT_ID`
- Environment toggle via `OANDA_ENV` env var (`practice` or `live`, defaults to `practice`)
- Add env vars to `.env.ps1`

### File Structure
```
src/oanda/
    __init__.py
    client.py       # OandaClient class (httpx-based, all API calls)
    cli.py          # argparse entry point, subcommands
    models.py       # Pydantic response models
```

### CLI Commands

**Account**
- `oanda account` -- Get account summary (balance, NAV, P/L, margin, positions, orders)

**Market Data**
- `oanda price [-i INSTRUMENT]` -- Get current bid/ask spread for instrument
- `oanda candles [-i INSTRUMENT] [-g GRANULARITY] [-n COUNT]` -- Get OHLCV candles (default: M1, 10 candles)
- `oanda prev-hl [-i INSTRUMENT] [-g GRANULARITY]` -- Previous time frame high/low (default: H1)
- `oanda m0-check [-i INSTRUMENT] [-g GRANULARITY]` -- Opening candle bias and level check (default: M1)
- `oanda overnight [-i INSTRUMENT] [-g GRANULARITY]` -- Overnight session range analysis (22:00-10:00 UTC, default: M5)

**Trading**
- `oanda buy UNITS [-i INSTRUMENT] [--tp PRICE] [--sl PRICE]` -- Market buy with optional TP/SL
- `oanda sell UNITS [-i INSTRUMENT] [--tp PRICE] [--sl PRICE]` -- Market sell with optional TP/SL
- `oanda limit buy|sell UNITS PRICE [-i INSTRUMENT] [--tp PRICE] [--sl PRICE]` -- Limit order with optional TP/SL
- `oanda stop buy|sell UNITS PRICE [-i INSTRUMENT] [--tp PRICE] [--sl PRICE]` -- Stop order with optional TP/SL
- `oanda orders [-i INSTRUMENT]` -- List pending orders
- `oanda cancel ORDER_ID` -- Cancel a pending order
- `oanda trades [-i INSTRUMENT]` -- List open trades
- `oanda close TRADE_ID [-u UNITS]` -- Close a trade (default: ALL units)
- `oanda modify TRADE_ID [--tp PRICE] [--sl PRICE]` -- Modify trade TP/SL
- `oanda positions` -- List open positions
- `oanda close-position [-i INSTRUMENT] [--long-units UNITS] [--short-units UNITS]` -- Close a position

### Client Design
```python
class OandaClient:
    def __init__(self, api_key: str, account_id: str, environment: str = "practice"):
        self.base_url = "https://api-fxpractice.oanda.com" if environment == "practice" else "https://api-fxtrade.oanda.com"
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            timeout=30.0,
        )
```

All methods return raw JSON dicts. The CLI layer just does `json.dumps(result, indent=2)` to stdout.

### Entry point
Add to `pyproject.toml`:
```toml
[project.scripts]
oanda = "oanda.cli:main"
```

Alternatively runnable as `python -m oanda`.

### Supported Instruments
Default instrument is `NAS100_USD` (configurable via `INSTRUMENT` env var). OANDA supports forex, commodities, indices, and metals.

### Granularities
- `S5`, `S10`, `S15`, `S30` -- Seconds
- `M1`, `M2`, `M4`, `M5`, `M10`, `M15`, `M30` -- Minutes
- `H1`, `H2`, `H3`, `H4`, `H6`, `H8`, `H12` -- Hours
- `D` -- Daily
- `W` -- Weekly
- `M` -- Monthly
