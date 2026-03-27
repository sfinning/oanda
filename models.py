from __future__ import annotations

from pydantic import BaseModel, Field


class AccountSummary(BaseModel):
    id: str = ""
    currency: str = ""
    balance: str = "0"
    nav: str = Field("0", alias="NAV")
    unrealized_pl: str = Field("0", alias="unrealizedPL")
    pl: str = "0"
    margin_used: str = Field("0", alias="marginUsed")
    margin_available: str = Field("0", alias="marginAvailable")
    open_trade_count: int = Field(0, alias="openTradeCount")
    open_position_count: int = Field(0, alias="openPositionCount")
    pending_order_count: int = Field(0, alias="pendingOrderCount")

    model_config = {"populate_by_name": True}


class PriceBucket(BaseModel):
    price: str
    liquidity: int


class Price(BaseModel):
    instrument: str = ""
    time: str = ""
    status: str = ""
    asks: list[PriceBucket] = Field(default_factory=list)
    bids: list[PriceBucket] = Field(default_factory=list)
    closeout_ask: str = Field("", alias="closeoutAsk")
    closeout_bid: str = Field("", alias="closeoutBid")

    model_config = {"populate_by_name": True}

    @property
    def best_ask(self) -> str:
        return self.asks[0].price if self.asks else ""

    @property
    def best_bid(self) -> str:
        return self.bids[0].price if self.bids else ""

    @property
    def spread(self) -> str:
        if self.asks and self.bids:
            return f"{float(self.asks[0].price) - float(self.bids[0].price):.2f}"
        return ""


class PositionSide(BaseModel):
    units: str = "0"
    average_price: str = Field(default="", alias="averagePrice")
    pl: str = "0"
    unrealized_pl: str = Field(default="0", alias="unrealizedPL")

    model_config = {"populate_by_name": True}


class Position(BaseModel):
    instrument: str = ""
    pl: str = "0"
    unrealized_pl: str = Field(default="0", alias="unrealizedPL")
    long: PositionSide = PositionSide()  # type: ignore[call-arg]
    short: PositionSide = PositionSide()  # type: ignore[call-arg]

    model_config = {"populate_by_name": True}


class Trade(BaseModel):
    id: str = ""
    instrument: str = ""
    price: str = ""
    open_time: str = Field("", alias="openTime")
    current_units: str = Field("0", alias="currentUnits")
    initial_units: str = Field("0", alias="initialUnits")
    state: str = ""
    unrealized_pl: str = Field("0", alias="unrealizedPL")
    realized_pl: str = Field("0", alias="realizedPL")

    model_config = {"populate_by_name": True}


class Order(BaseModel):
    id: str = ""
    type: str = ""
    instrument: str = ""
    units: str = ""
    price: str = ""
    state: str = ""
    time_in_force: str = Field("", alias="timeInForce")
    create_time: str = Field("", alias="createTime")

    model_config = {"populate_by_name": True}


class CandlestickData(BaseModel):
    o: str = ""
    h: str = ""
    l: str = ""  # noqa: E741
    c: str = ""


class Candlestick(BaseModel):
    time: str = ""
    volume: int = 0
    complete: bool = False
    mid: CandlestickData | None = None
    bid: CandlestickData | None = None
    ask: CandlestickData | None = None
