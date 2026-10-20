"""Scanner + position manager + trading loops.

Scanner: for each symbol x each timeframe, fetch klines + funding, run the 10
strategies, keep signals passing TF_MIN + MIN_AGREE. A symbol signal passes when
>=2 TFs agree on a direction and mean confidence >= MIN_CONFIDENCE.

Manager (every MANAGE_INTERVAL_SEC per open position):
  breakeven  — move SL to entry once ROI >= BREAKEVEN_THRESHOLD_PCT
  trailing   — once ROI >= TRAILING_TRIGGER_ROI_PCT, trail SL by
               TRAILING_METHOD/CALLBACK (ATR behind price, RATIO callback from
               best, INTERVAL absolute)
  reversal   — if fresh scan opposes the position and passes filters, flag close
  account TP/SL — close everything on total unrealised PnL bounds
"""
import time
import strategies
import tpsl


def scan_symbol(client, symbol, cfg):
    tf_results = []
    funding = None
    try:
        fr = client.get_funding_rate(symbol)
        items = fr if isinstance(fr, list) else [fr]
        if items and isinstance(items[0], dict):
            funding = items[0].get("fundingRate", items[0].get("funding_rate"))
    except Exception:
        pass
    for tf in cfg["timeframes"]:
        try:
            kl = client.get_kline(symbol, tf, limit=120)
            rows = kl if isinstance(kl, list) else kl.get("klineList", kl.get("data", []))
        except Exception as e:
            tf_results.append({"tf": tf, "error": str(e)[:120]})
            continue
        r = strategies.analyze(symbol, rows, funding)
        r["tf"] = tf
        r["pass"] = r["agree"] >= cfg["min_agreeing_strategies"] and r["conf"] >= cfg["tf_min_confidence"]
        tf_results.append(r)
    ok = [r for r in tf_results if r.get("pass")]
    longs = [r for r in ok if r["dir"] == "LONG"]
    shorts = [r for r in ok if r["dir"] == "SHORT"]
    for group, side in ((longs, "LONG"), (shorts, "SHORT")):
        if len(group) >= 2:
            conf = sum(r["conf"] for r in group) / len(group)
            if conf >= cfg["min_confidence"]:
                return {"symbol": symbol, "dir": side, "conf": conf,
                        "tfs": [r["tf"] for r in group], "detail": tf_results,
                        "price": group[-1]["price"]}
    return {"symbol": symbol, "dir": "NONE", "conf": 0.0, "tfs": [], "detail": tf_results,
            "price": tf_results[-1].get("price", 0) if tf_results else 0}


def scan_all(client, cfg):
    out = []
    syms = cfg["symbols"]
    try:
        tick = client.get_tickers(",".join(syms[:20]) if syms else None)
        items = tick if isinstance(tick, list) else tick.get("tickerList", tick.get("data", []))
        vols = {}
        for t in items if isinstance(items, list) else []:
            try:
                vols[t.get("symbol")] = float(t.get("quoteVol", t.get("volume", 0)) or 0)
            except (ValueError, TypeError):
                pass
        floor = cfg.get("min_24h_volume_usd", 0)
        if floor:
            syms = [s for s in syms if vols.get(s, float("inf")) >= floor]
        if (cfg.get("universe_rank") or "VOLUME").upper() == "VOLUME" and vols:
            syms = sorted(syms, key=lambda s: vols.get(s, 0), reverse=True)
    except Exception:
        pass
    for s in syms:
        try:
            out.append(scan_symbol(client, s, cfg))
        except Exception as e:
            out.append({"symbol": s, "dir": "ERROR", "conf": 0.0, "error": str(e)[:200]})
    return out


def position_roi_pct(pos):
    try:
        entry = float(pos.get("entryPrice", pos.get("entryValue", 0)) or 0)
        mark = float(pos.get("markPrice", pos.get("lastPrice", entry)) or entry)
        lev = float(pos.get("leverage", 1) or 1)
        side = str(pos.get("side", pos.get("positionSide", "LONG"))).upper()
    except (ValueError, TypeError):
        return 0.0
    if not entry:
        return 0.0
    move = (mark - entry) / entry * 100 * lev
    return move if "LONG" in side or "BUY" in side else -move


def manage_positions(client, cfg, positions, on_event):
    """Apply breakeven / trailing / reversal / account-level exits. on_event(msg)."""
    total_upnl = 0.0
    for p in positions:
        try:
            total_upnl += float(p.get("unrealizedPNL", p.get("unrealisedPNL", 0)) or 0)
        except (ValueError, TypeError):
            pass
    if cfg.get("account_tp_usdt") and total_upnl >= cfg["account_tp_usdt"]:
        on_event(f"ACCOUNT TP hit: {total_upnl:.2f} USDT — closing all")
        try:
            client.close_all_position()
        except Exception as e:
            on_event("close_all failed: " + str(e)[:200])
        return
    if cfg.get("account_sl_usdt") and total_upnl <= -abs(cfg["account_sl_usdt"]):
        on_event(f"ACCOUNT SL hit: {total_upnl:.2f} USDT — closing all")
        try:
            client.close_all_position()
        except Exception as e:
            on_event("close_all failed: " + str(e)[:200])
        return
    for p in positions:
        sym = p.get("symbol")
        pid = p.get("positionId", p.get("id"))
        roi = position_roi_pct(p)
        entry = float(p.get("entryPrice", p.get("entryValue", 0)) or 0)
        side = "LONG" if "LONG" in str(p.get("side", "LONG")).upper() or "BUY" in str(p.get("side", "")).upper() else "SHORT"
        sgn = 1 if side == "LONG" else -1
        # breakeven
        if roi >= cfg.get("breakeven_threshold_pct", 0.5):
            try:
                client.modify_position_tp_sl_order(symbol=sym, positionId=pid, slPrice=str(entry))
                on_event(f"{sym}: breakeven SL -> entry (ROI {roi:.2f}%)")
            except Exception as e:
                on_event(f"{sym}: breakeven failed: {str(e)[:150]}")
        # trailing
        if roi >= cfg.get("trailing_trigger_roi_pct", 1.0):
            try:
                mark = float(p.get("markPrice", entry) or entry)
                cb = cfg.get("trailing_callback", 0.5) / 100.0
                tm = (cfg.get("trailing_method") or "RATIO").upper()
                if tm == "RATIO":
                    new_sl = mark - sgn * abs(mark) * cb
                elif tm == "INTERVAL":
                    new_sl = mark - sgn * cfg.get("trailing_callback", 0.5)
                else:  # ATR
                    try:
                        kl = client.get_kline(sym, cfg["timeframes"][-1], limit=30)
                        rows = kl if isinstance(kl, list) else kl.get("klineList", [])
                        c = [float(r["close"]) for r in rows]
                        h = [float(r["high"]) for r in rows]
                        l = [float(r["low"]) for r in rows]
                        a = tpsl._atr(h, l, c)
                    except Exception:
                        a = abs(mark) * 0.005
                    new_sl = mark - sgn * a * max(cfg.get("trailing_callback", 0.5), 0.1)
                client.modify_position_tp_sl_order(symbol=sym, positionId=pid, slPrice=str(new_sl))
                on_event(f"{sym}: trailing SL -> {new_sl:.6g} (ROI {roi:.2f}%)")
            except Exception as e:
                on_event(f"{sym}: trailing failed: {str(e)[:150]}")
        # reversal
        if cfg.get("reversal_close"):
            try:
                s = scan_symbol(client, sym, cfg)
                if s["dir"] != "NONE" and ((s["dir"] == "LONG") != (side == "LONG")):
                    on_event(f"{sym}: REVERSAL — scan {s['dir']} {s['conf']:.1f}% vs position {side}; manual close advised")
            except Exception:
                pass
