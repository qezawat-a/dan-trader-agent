"""Unit tests for the trader engine (no network): strategies, TP/SL, sizing, config."""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import strategies
import tpsl
import sizing
import tconfig


def fake_klines(n=120, start=100.0, drift=0.04, vol=0.4):
    rows = []
    p = start
    for i in range(n):
        o = p
        c = p + drift + (vol * ((i * 37 % 11) - 5) / 10)
        h = max(o, c) + vol / 3
        l = min(o, c) - vol / 3
        rows.append({"open": o, "high": h, "low": l, "close": c,
                     "baseVol": 1000 + (i * 13 % 500), "time": 1700000000000 + i * 60000})
        p = c
    return rows


def test_strategies_uptrend():
    r = strategies.analyze("T", fake_klines(drift=0.08), funding_rate="-0.002")
    assert r["dir"] == "LONG", r
    assert r["conf"] >= 60, r
    assert len(r["votes"]) == 10, r
    print("uptrend:", r["dir"], round(r["conf"], 1), "agree", r["agree"])


def test_strategies_downtrend():
    r = strategies.analyze("T", fake_klines(drift=-0.08), funding_rate="0.003")
    assert r["dir"] == "SHORT", r
    assert r["conf"] >= 60, r
    print("downtrend:", r["dir"], round(r["conf"], 1), "agree", r["agree"])


def test_tpsl_methods():
    kl = fake_klines()
    entry = kl[-1]["close"]
    for m in ("POSITION", "PARTIAL", "ADAPTIVE", "FIXED_R"):
        cfg = tconfig.load()
        cfg["tpsl_method"] = m
        for side in ("LONG", "SHORT"):
            p = tpsl.plan(entry, side, 82.0, kl, cfg)
            sgn = 1 if side == "LONG" else -1
            assert (p["stop"] - entry) * sgn < 0, (m, side, p)
            assert (p["tp"] - entry) * sgn > 0, (m, side, p)
    cfg = tconfig.load()
    cfg["tpsl_method"] = "PARTIAL"
    p = tpsl.plan(entry, "LONG", 85.0, kl, cfg)
    assert len(p["ladder"]) == 3 and p["runner"] >= 0, p
    print("tpsl 4 methods ok")


def test_sizing():
    qty, notional = sizing.calc_order_qty(1000, 1.0, 10, 100.0)
    assert abs(notional - 100.0) < 1e-9, (qty, notional)
    assert abs(qty - 1.0) < 1e-9, (qty, notional)
    q2, _ = sizing.calc_order_qty(1000, 1.0, 10, 100.0, step=0.5)
    assert q2 == 1.0, q2
    q3, _ = sizing.calc_order_qty(1, 1.0, 1, 100000.0)
    assert q3 == 0.0, q3
    print("sizing ok")


def test_config_roundtrip():
    cfg = tconfig.load()
    k, v = tconfig.set(cfg, "leverage", "25")
    assert k == "leverage" and v == 25, (k, v)
    k, v = tconfig.set(cfg, "symbols", "BTCUSDT,ETHUSDT")
    assert v == ["BTCUSDT", "ETHUSDT"], v
    tconfig.set(cfg, "leverage", str(tconfig.DEFAULTS["leverage"]))
    tconfig.set(cfg, "symbols", ",".join(tconfig.DEFAULTS["symbols"]))
    print("config ok")


if __name__ == "__main__":
    test_strategies_uptrend()
    test_strategies_downtrend()
    test_tpsl_methods()
    test_sizing()
    test_config_roundtrip()
    print("ALL TRADER TESTS PASS")
