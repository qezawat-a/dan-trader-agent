"""TP/SL planner — 4 methods (help centre id=290).

POSITION = one TP/SL for the whole position.
PARTIAL  = scale-out ladder (share@R pairs; remainder rides as runner).
ADAPTIVE = TP/SL from trend strength/structure: confidence picks an R pair
           from adaptive_table, stop = ATR_STOP_MULT * ATR.
FIXED_R  = TP = FIXED_R x stop distance.

Plus: partial ladder, trailing (ATR behind price / RATIO callback from best /
INTERVAL absolute), account-level TP/SL on total unrealised PnL, and the
liquidation guard (LIQ_SL_DISTANCE_PCT keeps the stop inside the liq price).

Returns plain price levels; the engine converts them to Bitunix tp_sl calls.
"""


def _atr(h, l, c, n=14):
    trs = []
    for i in range(len(c)):
        if i == 0:
            trs.append(h[i] - l[i])
        else:
            trs.append(max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
    k = 2 / (n + 1)
    out = trs[0]
    for v in trs[1:]:
        out = v * k + out * (1 - k)
    return out


def plan(entry, side, signal_conf, klines, cfg, liq_price=None):
    """side: LONG | SHORT. Returns dict with stop, tp, ladder, trailing, method."""
    rows = sorted(klines, key=lambda r: int(r.get("time", 0) or 0))
    c = [float(r["close"]) for r in rows]
    h = [float(r["high"]) for r in rows]
    l = [float(r["low"]) for r in rows]
    a = _atr(h, l, c)
    method = (cfg.get("tpsl_method") or "ADAPTIVE").upper()
    sgn = 1 if side == "LONG" else -1

    def stop_guard(stop):
        if liq_price and liq_price > 0:
            buf = abs(entry - liq_price) * (1 - cfg.get("liq_sl_distance_pct", 10.0) / 100.0)
            if sgn > 0:
                stop = max(stop, liq_price + buf * 0.01 + abs(entry) * 0.0005)
            else:
                stop = min(stop, liq_price - buf * 0.01 - abs(entry) * 0.0005)
        return stop

    if method == "POSITION":
        table = cfg.get("adaptive_table", {})
        key = max([k for k in table if float(k) <= signal_conf], default=None,
                  key=lambda k: float(k)) if table else None
        r_tp, r_sl = table.get(key, [2.0, 1.0]) if key else (2.0, 1.0)
        stop_d = a * cfg.get("atr_stop_mult", 1.5)
        stop = stop_guard(entry - sgn * stop_d)
        tp = entry + sgn * stop_d * r_tp / max(r_sl, 0.01)
        return {"method": "POSITION", "stop": stop, "tp": tp, "ladder": [], "runner": 0.0,
                "trailing": None}

    if method == "PARTIAL":
        ladder = cfg.get("partial_tp_ladder", [[50, 1.0], [30, 2.0], [20, 3.0]])
        stop_d = a * cfg.get("atr_stop_mult", 1.5)
        stop = stop_guard(entry - sgn * stop_d)
        legs = [{"share": sh, "price": entry + sgn * stop_d * r} for sh, r in ladder]
        used = sum(sh for sh, _ in ladder)
        return {"method": "PARTIAL", "stop": stop, "tp": legs[-1]["price"] if legs else None,
                "ladder": legs, "runner": max(0.0, 100.0 - used), "trailing": None}

    if method == "FIXED_R":
        rmult = cfg.get("fixed_r", 2.0)
        stop_d = a * cfg.get("atr_stop_mult", 1.5)
        stop = stop_guard(entry - sgn * stop_d)
        tp = entry + sgn * stop_d * rmult
        return {"method": "FIXED_R", "stop": stop, "tp": tp, "ladder": [], "runner": 0.0,
                "trailing": None}

    # ADAPTIVE (default)
    table = cfg.get("adaptive_table", {})
    key = max([k for k in table if float(k) <= signal_conf], default=None,
              key=lambda k: float(k)) if table else None
    r_tp, r_sl = table.get(key, [2.0, 1.2]) if key else (2.0, 1.2)
    stop_d = a * cfg.get("atr_stop_mult", 1.5) * r_sl
    stop = stop_guard(entry - sgn * stop_d)
    tp = entry + sgn * stop_d * (r_tp / max(r_sl, 0.01))
    tmethod = (cfg.get("trailing_method") or "RATIO").upper()
    trailing = {"method": tmethod, "callback": cfg.get("trailing_callback", 0.5)}
    return {"method": "ADAPTIVE", "stop": stop, "tp": tp, "ladder": [], "runner": 0.0,
            "trailing": trailing, "r_pair": [r_tp, r_sl]}
