"""Trader <-> Telegram bridge: /trade commands, background loops, report + guard."""
import threading
import time
from . import client as _client_mod
from . import tconfig
from . import engine as eng
from . import sizing
from . import tpsl

_client = None
_loops = {}
_last_signals = []
_report_log = []


def get_client():
    global _client
    if _client is None:
        import os
        _client = _client_mod.BitunixClient(os.environ.get("BITUNIX_API_KEY", ""),
                                            os.environ.get("BITUNIX_SECRET_KEY", ""))
    return _client


def status_line():
    cfg = tconfig.load()
    return (f"engine={'ON' if cfg['engine_on'] else 'OFF'} autotrade={'ON' if cfg['autotrade'] else 'OFF'} "
            f"scan={'ON' if cfg['scanning'] else 'OFF'} syms={','.join(cfg['symbols'])}")


def _notify(msg):
    _report_log.append(f"{time.strftime('%H:%M:%S')} {msg}")
    del _report_log[:-100]


def _scan_loop(send):
    global _last_signals
    cfg = tconfig.load()
    while _loops.get("scan"):
        try:
            cfg = tconfig.load()
            if cfg["engine_on"] and cfg["scanning"]:
                _last_signals = eng.scan_all(get_client(), cfg)
                hits = [s for s in _last_signals if s["dir"] in ("LONG", "SHORT")]
                if hits and cfg["report_on"]:
                    send("SCAN: " + "; ".join(f"{h['symbol']} {h['dir']} {h['conf']:.1f}% [{','.join(h['tfs'])}]" for h in hits))
                if cfg["autotrade"]:
                    _autotrade(hits, cfg, send)
        except Exception as e:
            _notify("scan error: " + str(e)[:200])
        time.sleep(max(tconfig.load().get("scan_interval_sec", 15), 5))


def _autotrade(hits, cfg, send):
    try:
        pos = get_client().get_pending_positions()
        plist = pos if isinstance(pos, list) else pos.get("positionList", pos.get("data", []))
    except Exception as e:
        send("autotrade: positions fetch failed: " + str(e)[:150])
        return
    if len(plist if isinstance(plist, list) else []) >= cfg.get("max_positions", 3):
        return
    for h in hits:
        sym = h["symbol"]
        if any(p.get("symbol") == sym for p in (plist if isinstance(plist, list) else [])):
            continue
        try:
            acct = get_client().get_account()
            bal = float(acct.get("available", acct.get("transfer", 0)) or 0)
            qty, notional = sizing.calc_order_qty(bal, cfg.get("risk_pct", 1.0),
                                                  cfg.get("leverage", 10), h["price"])
            if qty <= 0:
                send(f"{sym}: size too small (bal {bal:.2f})")
                continue
            kl = get_client().get_kline(sym, cfg["timeframes"][-1], limit=60)
            rows = kl if isinstance(kl, list) else kl.get("klineList", [])
            plan = tpsl.plan(h["price"], h["dir"], h["conf"], rows, cfg)
            side = "BUY" if h["dir"] == "LONG" else "SELL"
            o = get_client().place_order(sym, side, "MARKET", str(qty))
            send(f"OPEN {sym} {h['dir']} qty={qty} ({h['conf']:.1f}%) TP={plan['tp']:.6g} SL={plan['stop']:.6g}")
            try:
                get_client().place_position_tp_sl_order(symbol=sym, tpPrice=str(plan["tp"]),
                                                        slPrice=str(plan["stop"]))
            except Exception as e:
                send(f"{sym}: TP/SL attach failed: {str(e)[:150]}")
        except Exception as e:
            send(f"{sym}: order failed: {str(e)[:200]}")


def _manage_loop(send):
    while _loops.get("manage"):
        try:
            cfg = tconfig.load()
            if cfg["engine_on"]:
                pos = get_client().get_pending_positions()
                plist = pos if isinstance(pos, list) else pos.get("positionList", pos.get("data", []))
                if isinstance(plist, list) and plist:
                    eng.manage_positions(get_client(), cfg, plist, lambda m: (send(m), _notify(m)))
        except Exception as e:
            _notify("manage error: " + str(e)[:200])
        time.sleep(max(tconfig.load().get("manage_interval_sec", 15), 5))


def _report_loop(send):
    while _loops.get("report"):
        try:
            cfg = tconfig.load()
            if cfg["engine_on"] and cfg["report_on"]:
                pos = get_client().get_pending_positions()
                plist = pos if isinstance(pos, list) else pos.get("positionList", pos.get("data", []))
                lines = []
                for p in (plist if isinstance(plist, list) else []):
                    lines.append(f"{p.get('symbol')} {p.get('side')} ROI {eng.position_roi_pct(p):.2f}% uPnL {p.get('unrealizedPNL', 0)}")
                sig = "; ".join(f"{s['symbol']} {s['dir']} {s.get('conf', 0):.0f}%" for s in _last_signals if s.get("dir") in ("LONG", "SHORT")) or "no signals"
                send("REPORT\nsignals: " + sig + "\npositions:\n" + ("\n".join(lines) if lines else "(none)"))
        except Exception as e:
            _notify("report error: " + str(e)[:200])
        time.sleep(max(tconfig.load().get("report_interval_sec", 30), 10))


def ensure_loops(send):
    for name, fn in (("scan", _scan_loop), ("manage", _manage_loop), ("report", _report_loop)):
        if not _loops.get(name):
            _loops[name] = True
            t = threading.Thread(target=fn, args=(send,), daemon=True)
            t.start()


def handle(text):
    """Handle /trade <args>. Returns reply string. Live orders need autotrade ON."""
    global _last_signals
    import os
    cfg = tconfig.load()
    a = (text or "").strip().split()
    if not a or a[0] in ("help", ""):
        return ("trade commands: start|stop|engine_on|engine_off|status|report_on|report_off|\n"
                "report_interval_sec N|scan_on|scan_off|scans_interval_sec N|guard_interval_sec N|\n"
                "mid_manage_sec N|breakeven N|trailing_trigger N|trailing_stop N|trailing_distance N|\n"
                "liq_sl_distance N|min_agree N|timeframes a,b|min_conf N|tf_min_conf N|\n"
                "symbols a,b|max_positions N|leverage N|tpsl_method M|tp_mode M|positions|history|\n"
                "close SYM|cancel SYM|settings")
    c = a[0].lower()
    arg = a[1] if len(a) > 1 else ""
    rest = " ".join(a[1:])

    simple = {
        "start": ("autotrade", True, "autotrade ON — live orders will fire on signals"),
        "stop": ("autotrade", False, "autotrade OFF"),
        "engine_on": ("engine_on", True, "engine ON"),
        "engine_off": ("engine_off", False, "engine OFF"),
        "scan_on": ("scanning", True, "scan ON"),
        "scan_off": ("scanning", False, "scan OFF"),
        "report_on": ("report_on", True, "report ON"),
        "report_off": ("report_off", False, "report OFF"),
    }
    if c in simple:
        k, v, msg = simple[c]
        cfg[k] = v
        tconfig.save(cfg)
        return msg
    mapping = {
        "report_interval_sec": "report_interval_sec", "scans_interval_sec": "scan_interval_sec",
        "guard_interval_sec": "guard_interval_sec", "mid_manage_sec": "manage_interval_sec",
        "breakeven": "breakeven_threshold_pct", "trailing_trigger": "trailing_trigger_roi_pct",
        "trailing_stop": "trailing_stop_pct", "trailing_distance": "trailing_distance_pct",
        "liq_sl_distance": "liq_sl_distance_pct", "min_agree": "min_agreeing_strategies",
        "timeframes": "timeframes", "min_conf": "min_confidence", "tf_min_conf": "tf_min_confidence",
        "symbols": "symbols", "max_positions": "max_positions", "leverage": "leverage",
        "tpsl_method": "tpsl_method", "tp_mode": "tp_mode",
        "trailing_method": "trailing_method", "trailing_callback": "trailing_callback",
    }
    if c in mapping:
        if not rest:
            return f"{mapping[c]} = {cfg.get(mapping[c])}"
        k, v = tconfig.set(cfg, mapping[c], rest)
        return f"{k} = {v}"
    if c == "settings":
        return "\n".join(f"{k} = {v}" for k, v in cfg.items())
    if c == "status":
        try:
            acct = get_client().get_account()
            bal = acct.get("available", "?")
        except Exception as e:
            bal = "err: " + str(e)[:120]
        try:
            pos = get_client().get_pending_positions()
            plist = pos if isinstance(pos, list) else pos.get("positionList", [])
            npos = len(plist) if isinstance(plist, list) else "?"
        except Exception:
            npos = "?"
        return f"{status_line()}\nbalance={bal} open_positions={npos}\nlast scan: " + (
            "; ".join(f"{s['symbol']} {s['dir']} {s.get('conf', 0):.0f}%" for s in _last_signals) or "(none yet)")
    if c == "positions":
        try:
            pos = get_client().get_pending_positions()
            plist = pos if isinstance(pos, list) else pos.get("positionList", [])
            if not plist:
                return "no open positions"
            return "\n".join(f"{p.get('symbol')} {p.get('side')} qty={p.get('qty')} entry={p.get('entryPrice')} ROI {eng.position_roi_pct(p):.2f}%" for p in plist)
        except Exception as e:
            return "positions error: " + str(e)[:200]
    if c == "history":
        try:
            h = get_client().get_history_positions(arg or None)
            items = h if isinstance(h, list) else h.get("positionList", h.get("data", []))
            if not items:
                return "no history"
            return "\n".join(str(x)[:200] for x in (items if isinstance(items, list) else [])[:10])
        except Exception as e:
            return "history error: " + str(e)[:200]
    if c == "close":
        if not arg:
            return "usage: close SYM"
        try:
            get_client().flash_close_position(arg.upper())
            return f"{arg.upper()}: close sent"
        except Exception as e:
            return "close error: " + str(e)[:200]
    if c in ("cancel", "cancels"):
        if not arg:
            return "usage: cancel SYM"
        try:
            get_client().cancel_all_orders(arg.upper())
            try:
                get_client().cancel_tp_sl_order(symbol=arg.upper())
            except Exception:
                pass
            return f"{arg.upper()}: orders + TP/SL cancelled"
        except Exception as e:
            return "cancel error: " + str(e)[:200]
    if c == "scan":
        try:
            res = eng.scan_all(get_client(), cfg)
            _last_signals = res
            return "\n".join(f"{s['symbol']}: {s['dir']} {s.get('conf', 0):.1f}% [{','.join(s.get('tfs', []))}]" for s in res)
        except Exception as e:
            return "scan error: " + str(e)[:200]
    return "unknown trade cmd — /trade help"
