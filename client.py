from __future__ import annotations

import os
from typing import Any

import httpx

from .models import (
    AccountSummary,
    Candlestick,
    Order,
    Position,
    Price,
    Trade,
)

_BASE_URLS = {
    "practice": "https://api-fxpractice.oanda.com",
    "live": "https://api-fxtrade.oanda.com",
}


class OandaError(Exception):
    pass


class OandaClient:
    def __init__(
        self,
        api_key: str | None = None,
        account_id: str | None = None,
        environment: str | None = None,
    ) -> None:
        self.api_key = api_key or os.environ["OANDA_API_KEY"]
        self.account_id = account_id or os.environ["OANDA_ACCOUNT_ID"]
        env = (environment or os.environ.get("OANDA_ENV", "practice")).lower()
        self.base_url = _BASE_URLS.get(env, _BASE_URLS["practice"])
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            timeout=30.0,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OandaClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.request(method, path, **kwargs)
        if resp.status_code >= 400:
            try:
                body = resp.json()
                msg = body.get("errorMessage", resp.text)
            except Exception:
                msg = resp.text
            raise OandaError(f"HTTP {resp.status_code}: {msg}")
        return resp.json()

    def _acct(self, suffix: str = "") -> str:
        return f"/v3/accounts/{self.account_id}{suffix}"

    # --- Account ---

    def get_account_summary(self) -> AccountSummary:
        data = self._request("GET", self._acct("/summary"))
        return AccountSummary.model_validate(data["account"])

    # --- Pricing ---

    def get_pricing(self, instruments: list[str]) -> list[Price]:
        params = {"instruments": ",".join(instruments)}
        data = self._request("GET", self._acct("/pricing"), params=params)
        return [Price.model_validate(p) for p in data["prices"]]

    def get_candles(
        self,
        instrument: str,
        *,
        granularity: str = "M1",
        count: int | None = 10,
        price: str = "M",
        from_time: str | None = None,
        to_time: str | None = None,
    ) -> list[Candlestick]:
        params: dict[str, str] = {"granularity": granularity, "price": price}
        if from_time:
            params["from"] = from_time
        if to_time:
            params["to"] = to_time
        if count is not None and not from_time:
            params["count"] = str(count)
        data = self._request(
            "GET", self._acct(f"/instruments/{instrument}/candles"), params=params
        )
        return [Candlestick.model_validate(c) for c in data["candles"]]

    # --- Orders ---

    def create_market_order(
        self,
        instrument: str,
        units: int,
        *,
        take_profit: float | None = None,
        stop_loss: float | None = None,
    ) -> dict[str, Any]:
        order: dict[str, Any] = {
            "type": "MARKET",
            "instrument": instrument,
            "units": str(units),
            "timeInForce": "FOK",
            "positionFill": "DEFAULT",
        }
        if take_profit is not None:
            order["takeProfitOnFill"] = {"price": f"{take_profit:.1f}"}
        if stop_loss is not None:
            order["stopLossOnFill"] = {"timeInForce": "GTC", "price": f"{stop_loss:.1f}"}
        return self._request("POST", self._acct("/orders"), json={"order": order})

    def create_limit_order(
        self,
        instrument: str,
        units: int,
        price: float,
        *,
        take_profit: float | None = None,
        stop_loss: float | None = None,
    ) -> dict[str, Any]:
        order: dict[str, Any] = {
            "type": "LIMIT",
            "instrument": instrument,
            "units": str(units),
            "price": f"{price:.1f}",
            "timeInForce": "GTC",
            "positionFill": "DEFAULT",
        }
        if take_profit is not None:
            order["takeProfitOnFill"] = {"price": f"{take_profit:.1f}"}
        if stop_loss is not None:
            order["stopLossOnFill"] = {"timeInForce": "GTC", "price": f"{stop_loss:.1f}"}
        return self._request("POST", self._acct("/orders"), json={"order": order})

    def create_stop_order(
        self,
        instrument: str,
        units: int,
        price: float,
        *,
        take_profit: float | None = None,
        stop_loss: float | None = None,
    ) -> dict[str, Any]:
        order: dict[str, Any] = {
            "type": "STOP",
            "instrument": instrument,
            "units": str(units),
            "price": f"{price:.1f}",
            "timeInForce": "GTC",
            "positionFill": "DEFAULT",
        }
        if take_profit is not None:
            order["takeProfitOnFill"] = {"price": f"{take_profit:.1f}"}
        if stop_loss is not None:
            order["stopLossOnFill"] = {"timeInForce": "GTC", "price": f"{stop_loss:.1f}"}
        return self._request("POST", self._acct("/orders"), json={"order": order})

    def list_orders(self, *, instrument: str | None = None, state: str = "PENDING") -> list[Order]:
        params: dict[str, str] = {"state": state}
        if instrument:
            params["instrument"] = instrument
        data = self._request("GET", self._acct("/orders"), params=params)
        return [Order.model_validate(o) for o in data["orders"]]

    def list_pending_orders(self) -> list[Order]:
        data = self._request("GET", self._acct("/pendingOrders"))
        return [Order.model_validate(o) for o in data["orders"]]

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        return self._request("PUT", self._acct(f"/orders/{order_id}/cancel"))

    # --- Trades ---

    def list_open_trades(self, *, instrument: str | None = None) -> list[Trade]:
        if instrument:
            data = self._request(
                "GET", self._acct("/trades"), params={"instrument": instrument, "state": "OPEN"}
            )
        else:
            data = self._request("GET", self._acct("/openTrades"))
        return [Trade.model_validate(t) for t in data["trades"]]

    def close_trade(self, trade_id: str, *, units: str = "ALL") -> dict[str, Any]:
        body: dict[str, str] = {}
        if units != "ALL":
            body["units"] = units
        return self._request("PUT", self._acct(f"/trades/{trade_id}/close"), json=body)

    def set_trade_orders(
        self,
        trade_id: str,
        *,
        take_profit: float | None = None,
        stop_loss: float | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if take_profit is not None:
            body["takeProfit"] = {"timeInForce": "GTC", "price": f"{take_profit:.1f}"}
        if stop_loss is not None:
            body["stopLoss"] = {"timeInForce": "GTC", "price": f"{stop_loss:.1f}"}
        return self._request("PUT", self._acct(f"/trades/{trade_id}/orders"), json=body)

    # --- Positions ---

    def list_open_positions(self) -> list[Position]:
        data = self._request("GET", self._acct("/openPositions"))
        return [Position.model_validate(p) for p in data["positions"]]

    def get_position(self, instrument: str) -> Position:
        data = self._request("GET", self._acct(f"/positions/{instrument}"))
        return Position.model_validate(data["position"])

    def close_position(
        self, instrument: str, *, long_units: str = "ALL", short_units: str = "NONE"
    ) -> dict[str, Any]:
        body: dict[str, str] = {"longUnits": long_units, "shortUnits": short_units}
        return self._request("PUT", self._acct(f"/positions/{instrument}/close"), json=body)
