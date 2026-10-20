"""Order-unit calculator (Bitunix help centre: order units in futures trading).

Contracts are quoted in base units (e.g. BTC) while the UI shows USDT value.
qty_base = notional_usdt / price. This module converts a risk budget into a
valid order qty snapped to the pair's step size, and validates min notional.
"""
import math


def notional_to_qty(notional_usdt, price):
    if price <= 0:
        return 0.0
    return notional_usdt / price


def risk_to_notional(balance_usdt, risk_pct, leverage):
    return balance_usdt * (risk_pct / 100.0) * leverage


def snap_qty(qty, step=0.001, min_qty=0.0):
    if step and step > 0:
        qty = math.floor(qty / step) * step
    return max(qty, 0.0) if qty >= min_qty else 0.0


def calc_order_qty(balance_usdt, risk_pct, leverage, price, step=0.001, min_qty=0.0, min_notional=5.0):
    """Full pipeline: risk budget -> notional -> qty -> snapped qty. Returns (qty, notional)."""
    notional = risk_to_notional(balance_usdt, risk_pct, leverage)
    if notional < min_notional:
        return 0.0, notional
    qty = snap_qty(notional_to_qty(notional, price), step, min_qty)
    if qty * price < min_notional:
        return 0.0, notional
    return qty, notional


def specs_from_tickers(tickers):
    """Best-effort step/min extraction from ticker payloads (exchange may omit; defaults apply)."""
    out = {}
    items = tickers if isinstance(tickers, list) else tickers.get("tickerList", tickers.get("data", []))
    for t in items if isinstance(items, list) else []:
        sym = t.get("symbol")
        if sym:
            out[sym] = {"step": float(t.get("qtyStep", t.get("step", 0.001)) or 0.001),
                        "min_qty": float(t.get("minQty", 0) or 0),
                        "min_notional": float(t.get("minNotional", 5) or 5)}
    return out
