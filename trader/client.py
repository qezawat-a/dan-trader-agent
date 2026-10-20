"""Bitunix futures HTTP client — full endpoint coverage.

Signing follows the official Demo exactly (open_api_http_sign.py):
  digest = sha256(nonce + timestamp_ms + apiKey + sortedQuery + rawBody)
  sign   = sha256(digest + secretKey)
Headers: api-key, sign, nonce, timestamp (ms).

Endpoint map (fapi.bitunix.com, /api/v1/futures/...):
  account : GET account, POST adjust_position_margin, change_leverage,
            change_margin_mode, change_position_mode, GET get_leverage_and_margin_mode
  market  : GET tickers, depth, kline, trading_pairs, funding_rate,
            funding_rate/batch, funding_rate/history
  position: GET get_pending_positions, get_history_positions, get_position_tiers
  trade   : POST place_order, batch_order, cancel_orders, cancel_all_orders,
            modify_order, flash_close_position, close_all_position,
            GET get_pending_orders, get_history_orders, get_history_trades,
            get_order_detail
  tp_sl   : POST place_tp_sl_order, place_position_tp_sl_order,
            modify_tp_sl_order, modify_position_tp_sl_order, cancel_tp_sl_order,
            GET get_pending_tp_sl_order, get_history_tp_sl_order
Secrets come from env only and are never logged.
"""
import hashlib
import json
import time
import uuid
import requests


def _get_nonce():
    return str(uuid.uuid4()).replace("-", "")


def _get_timestamp():
    return str(int(time.time() * 1000))


def _sign(api_key, secret_key, nonce, timestamp, query_params="", body=""):
    digest = hashlib.sha256((nonce + timestamp + api_key + query_params + body).encode()).hexdigest()
    return hashlib.sha256((digest + secret_key).encode()).hexdigest()


def _sort_params(params):
    if not params:
        return ""
    return "".join(f"{k}{v}" for k, v in sorted(params.items()))


class BitunixError(Exception):
    pass


class BitunixClient:
    BASE = "https://fapi.bitunix.com"
    P = "/api/v1/futures"

    def __init__(self, api_key, secret_key, base_url=None):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base = (base_url or self.BASE).rstrip("/")
        self.s = requests.Session()
        self.s.headers.update({"language": "en-US", "Content-Type": "application/json"})

    def _headers(self, query="", body=""):
        nonce, ts = _get_nonce(), _get_timestamp()
        return {"api-key": self.api_key, "sign": _sign(self.api_key, self.secret_key, nonce, ts, query, body),
                "nonce": nonce, "timestamp": ts}

    @staticmethod
    def _check(resp):
        if resp.status_code != 200:
            raise BitunixError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        d = resp.json()
        if d.get("code") != 0:
            raise BitunixError(f"code={d.get('code')} msg={d.get('msg')}")
        return d.get("data")

    def _get(self, path, params=None):
        params = params or {}
        qs = _sort_params({k: str(v) for k, v in params.items() if v is not None})
        return self._check(self.s.get(self.base + path, params=params, headers=self._headers(qs), timeout=30))

    def _post(self, path, data=None):
        data = data or {}
        body = json.dumps(data)
        return self._check(self.s.post(self.base + path, json=data, headers=self._headers(body=body), timeout=30))

    # ---- account ----
    def get_account(self, margin_coin="USDT"):
        return self._get(f"{self.P}/account", {"marginCoin": margin_coin})

    def adjust_position_margin(self, symbol, position_id=None, amount=None, type=None):
        d = {"symbol": symbol}
        if position_id is not None:
            d["positionId"] = position_id
        if amount is not None:
            d["amount"] = amount
        if type is not None:
            d["type"] = type
        return self._post(f"{self.P}/account/adjust_position_margin", d)

    def change_leverage(self, symbol, leverage, margin_mode=None, position_side=None):
        d = {"symbol": symbol, "leverage": leverage}
        if margin_mode is not None:
            d["marginMode"] = margin_mode
        if position_side is not None:
            d["positionSide"] = position_side
        return self._post(f"{self.P}/account/change_leverage", d)

    def change_margin_mode(self, symbol, margin_mode):
        return self._post(f"{self.P}/account/change_margin_mode", {"symbol": symbol, "marginMode": margin_mode})

    def change_position_mode(self, position_mode, symbol=None):
        d = {"positionMode": position_mode}
        if symbol is not None:
            d["symbol"] = symbol
        return self._post(f"{self.P}/account/change_position_mode", d)

    def get_leverage_and_margin_mode(self, symbol):
        return self._get(f"{self.P}/account/get_leverage_and_margin_mode", {"symbol": symbol})

    # ---- market ----
    def get_tickers(self, symbols=None):
        p = {}
        if symbols:
            p["symbols"] = symbols
        return self._get(f"{self.P}/market/tickers", p)

    def get_depth(self, symbol, limit=100):
        return self._get(f"{self.P}/market/depth", {"symbol": symbol, "limit": limit})

    def get_kline(self, symbol, interval, limit=100, start_time=None, end_time=None, type="LAST_PRICE"):
        p = {"symbol": symbol, "interval": interval, "limit": limit, "type": type}
        if start_time is not None:
            p["startTime"] = start_time
        if end_time is not None:
            p["endTime"] = end_time
        return self._get(f"{self.P}/market/kline", p)

    def get_trading_pairs(self, symbols=None):
        p = {}
        if symbols:
            p["symbols"] = symbols
        return self._get(f"{self.P}/market/trading_pairs", p)

    def get_funding_rate(self, symbol):
        return self._get(f"{self.P}/market/funding_rate", {"symbol": symbol})

    def get_funding_rate_batch(self, symbols=None):
        p = {}
        if symbols:
            p["symbols"] = symbols
        return self._get(f"{self.P}/market/funding_rate/batch", p)

    def get_funding_rate_history(self, symbol, limit=None):
        p = {"symbol": symbol}
        if limit is not None:
            p["limit"] = limit
        return self._get(f"{self.P}/market/funding_rate/history", p)

    # ---- position ----
    def get_pending_positions(self, symbol=None):
        p = {}
        if symbol:
            p["symbol"] = symbol
        return self._get(f"{self.P}/position/get_pending_positions", p)

    def get_history_positions(self, symbol=None):
        p = {}
        if symbol:
            p["symbol"] = symbol
        return self._get(f"{self.P}/position/get_history_positions", p)

    def get_position_tiers(self, symbol=None):
        p = {}
        if symbol:
            p["symbol"] = symbol
        return self._get(f"{self.P}/position/get_position_tiers", p)

    # ---- trade ----
    def place_order(self, symbol, side, order_type, qty, price=None, position_id=None,
                    trade_side="OPEN", effect="GTC", reduce_only=False, client_id=None,
                    tp_price=None, tp_stop_type=None, tp_order_type=None, tp_order_price=None, **extra):
        d = {"symbol": symbol, "side": side, "orderType": order_type, "qty": qty,
             "tradeSide": trade_side, "effect": effect, "reduceOnly": reduce_only}
        for k, v in [("price", price), ("positionId", position_id), ("clientId", client_id),
                     ("tpPrice", tp_price), ("tpStopType", tp_stop_type),
                     ("tpOrderType", tp_order_type), ("tpOrderPrice", tp_order_price)]:
            if v is not None:
                d[k] = v
        d.update(extra)
        return self._post(f"{self.P}/trade/place_order", d)

    def batch_order(self, order_list):
        return self._post(f"{self.P}/trade/batch_order", {"orderList": order_list})

    def cancel_orders(self, symbol, order_list):
        return self._post(f"{self.P}/trade/cancel_orders", {"symbol": symbol, "orderList": order_list})

    def cancel_all_orders(self, symbol=None):
        d = {}
        if symbol:
            d["symbol"] = symbol
        return self._post(f"{self.P}/trade/cancel_all_orders", d)

    def modify_order(self, symbol, order_id=None, client_id=None, price=None, qty=None, **extra):
        d = {"symbol": symbol}
        if order_id is not None:
            d["orderId"] = order_id
        if client_id is not None:
            d["clientId"] = client_id
        if price is not None:
            d["price"] = price
        if qty is not None:
            d["qty"] = qty
        d.update(extra)
        return self._post(f"{self.P}/trade/modify_order", d)

    def flash_close_position(self, symbol, position_id=None, side=None):
        d = {"symbol": symbol}
        if position_id is not None:
            d["positionId"] = position_id
        if side is not None:
            d["side"] = side
        return self._post(f"{self.P}/trade/flash_close_position", d)

    def close_all_position(self, symbol=None):
        d = {}
        if symbol:
            d["symbol"] = symbol
        return self._post(f"{self.P}/trade/close_all_position", d)

    def get_pending_orders(self, symbol=None, order_id=None, status=None,
                           start_time=None, end_time=None, skip=None, limit=None):
        p = {}
        for k, v in [("symbol", symbol), ("orderId", order_id), ("status", status),
                     ("startTime", start_time), ("endTime", end_time), ("skip", skip), ("limit", limit)]:
            if v is not None:
                p[k] = v
        return self._get(f"{self.P}/trade/get_pending_orders", p)

    def get_history_orders(self, symbol=None, **kw):
        p = dict(kw)
        if symbol:
            p["symbol"] = symbol
        return self._get(f"{self.P}/trade/get_history_orders", p)

    def get_history_trades(self, symbol=None, **kw):
        p = dict(kw)
        if symbol:
            p["symbol"] = symbol
        return self._get(f"{self.P}/trade/get_history_trades", p)

    def get_order_detail(self, order_id=None, client_id=None, symbol=None):
        p = {}
        for k, v in [("orderId", order_id), ("clientId", client_id), ("symbol", symbol)]:
            if v is not None:
                p[k] = v
        return self._get(f"{self.P}/trade/get_order_detail", p)

    # ---- tp/sl ----
    def place_tp_sl_order(self, **kw):
        return self._post(f"{self.P}/tp_sl/place_tp_sl_order", kw)

    def place_position_tp_sl_order(self, **kw):
        return self._post(f"{self.P}/tp_sl/place_position_tp_sl_order", kw)

    def modify_tp_sl_order(self, **kw):
        return self._post(f"{self.P}/tp_sl/modify_tp_sl_order", kw)

    def modify_position_tp_sl_order(self, **kw):
        return self._post(f"{self.P}/tp_sl/modify_position_tp_sl_order", kw)

    def cancel_tp_sl_order(self, symbol=None, order_id=None, client_id=None, position_id=None):
        d = {}
        for k, v in [("symbol", symbol), ("orderId", order_id), ("clientId", client_id), ("positionId", position_id)]:
            if v is not None:
                d[k] = v
        return self._post(f"{self.P}/tp_sl/cancel_tp_sl_order", d)

    def get_pending_tp_sl_order(self, symbol=None, **kw):
        p = dict(kw)
        if symbol:
            p["symbol"] = symbol
        return self._get(f"{self.P}/tp_sl/get_pending_tp_sl_order", p)

    def get_history_tp_sl_order(self, symbol=None, **kw):
        p = dict(kw)
        if symbol:
            p["symbol"] = symbol
        return self._get(f"{self.P}/tp_sl/get_history_tp_sl_order", p)
