"""Trader engine config — all bot settings with defaults. Persisted to trader.json."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_FILE = os.path.join(HERE, "trader.json")

DEFAULTS = {
    # engine state
    "engine_on": True,
    "autotrade": False,
    "scanning": True,
    "report_on": True,
    "report_interval_sec": 30,
    "scan_interval_sec": 15,
    "guard_interval_sec": 15,
    "manage_interval_sec": 15,
    # universe
    "symbols": ["BTCUSDT", "ETHUSDT", "STRKUSDT"],
    "timeframes": ["1m", "3m", "5m", "15m"],
    "min_confidence": 80.0,
    "tf_min_confidence": 60.0,
    "min_agreeing_strategies": 3,
    "universe_rank": "VOLUME",
    "min_24h_volume_usd": 1000000,
    # sizing / leverage
    "leverage": 10,
    "margin_mode": "ISOLATED",
    "position_mode": "HEDGE",
    "max_positions": 3,
    "risk_pct": 1.0,
    # mid management
    "breakeven_threshold_pct": 0.5,
    "trailing_trigger_roi_pct": 1.0,
    "trailing_stop_pct": 0.5,
    "trailing_distance_pct": 0.5,
    "liq_sl_distance_pct": 10.0,
    "reversal_close": True,
    # TP/SL — 4 methods: POSITION | PARTIAL | ADAPTIVE | FIXED_R
    "tp_mode": "POSITION",
    "tpsl_method": "ADAPTIVE",
    "partial_tp_ladder": [[50, 1.0], [30, 2.0], [20, 3.0]],
    "trailing_method": "RATIO",
    "trailing_callback": 0.5,
    "account_tp_usdt": 0.0,
    "account_sl_usdt": 0.0,
    # adaptive TP/SL tables by signal confidence
    "adaptive_table": {"60": [1.5, 1.0], "70": [2.0, 1.2], "80": [2.5, 1.5], "90": [3.0, 2.0]},
    "fixed_r": 2.0,
    "atr_stop_mult": 1.5,
    "atr_tp_mult": 3.0,
}


def load():
    cfg = dict(DEFAULTS)
    if os.path.exists(CFG_FILE):
        try:
            with open(CFG_FILE) as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def save(cfg):
    with open(CFG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def set(cfg, key, value):
    kl = key.lower()
    for k in cfg:
        if k.lower() == kl:
            old = cfg[k]
            if isinstance(old, bool):
                cfg[k] = str(value).lower() in ("1", "true", "on", "yes")
            elif isinstance(old, int):
                cfg[k] = int(float(value))
            elif isinstance(old, float):
                cfg[k] = float(value)
            elif isinstance(old, list):
                cfg[k] = [x.strip() for x in str(value).split(",") if x.strip()]
            else:
                cfg[k] = value
            save(cfg)
            return k, cfg[k]
    cfg[key] = value
    save(cfg)
    return key, value
