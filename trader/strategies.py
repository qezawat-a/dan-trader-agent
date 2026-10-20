"""10 signal strategies over klines: EMA, RSI, MACD, volume, momentum,
ATR breakout, funding rate, supertrend, Bollinger, Ichimoku.

Each strategy returns (direction, strength): direction in {+1 LONG, -1 SHORT,
0 flat}, strength in [0,1]. A signal passes when >= MIN_AGREE strategies agree
on a direction and confidence >= TF_MIN.
"""
import math


def ema(vals, n):
    k = 2 / (n + 1)
    out = [vals[0]]
    for v in vals[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def sma(vals, n):
    return [sum(vals[max(0, i - n + 1):i + 1]) / min(i + 1, n) for i in range(len(vals))]


def rsi(c, n=14):
    out = [50.0] * len(c)
    g = l = 0.0
    for i in range(1, len(c)):
        d = c[i] - c[i - 1]
        gain, loss = max(d, 0), max(-d, 0)
        if i <= n:
            g += gain / n
            l += loss / n
            if i == n:
                out[i] = 100 - 100 / (1 + (g / l if l else 1e9))
        else:
            g = (g * (n - 1) + gain) / n
            l = (l * (n - 1) + loss) / n
            out[i] = 100 - 100 / (1 + (g / l if l else 1e9))
    return out


def macd(c):
    m = [a - b for a, b in zip(ema(c, 12), ema(c, 26))]
    s = ema(m, 9)
    return m, s


def atr(h, l, c, n=14):
    trs = []
    for i in range(len(c)):
        if i == 0:
            trs.append(h[0] - l[0])
        else:
            trs.append(max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
    return ema(trs, n)


def stoch(h, l, c, n=14):
    out = [50.0] * len(c)
    for i in range(n - 1, len(c)):
        hh, ll = max(h[i - n + 1:i + 1]), min(l[i - n + 1:i + 1])
        out[i] = 50.0 if hh == ll else (c[i] - ll) / (hh - ll) * 100
    return out


def bollinger(c, n=20, k=2.0):
    pb = [0.5] * len(c)
    for i in range(n - 1, len(c)):
        w = c[i - n + 1:i + 1]
        m = sum(w) / n
        sd = (sum((x - m) ** 2 for x in w) / n) ** 0.5
        pb[i] = 0.5 if sd == 0 else (c[i] - (m - k * sd)) / (2 * k * sd)
    return pb


def supertrend(h, l, c, n=10, mult=3.0):
    a = atr(h, l, c, n)
    up = [0.0] * len(c)
    for i in range(len(c)):
        mid = (h[i] + l[i]) / 2
        up[i] = 1 if c[i] > mid + mult * a[i] * 0 else ( -1 if c[i] < mid - 0 else up[i - 1] if i else 0)
    # simplified: price vs trailing band
    band_up = [(h[i] + l[i]) / 2 + mult * a[i] for i in range(len(c))]
    band_lo = [(h[i] + l[i]) / 2 - mult * a[i] for i in range(len(c))]
    d = [0] * len(c)
    fu, fl = band_up[0], band_lo[0]
    for i in range(len(c)):
        if i:
            fu = min(band_up[i], fu) if c[i - 1] > fu else band_up[i]
            fl = max(band_lo[i], fl) if c[i - 1] < fl else band_lo[i]
        if c[i] > fu:
            d[i] = 1
        elif c[i] < fl:
            d[i] = -1
        else:
            d[i] = d[i - 1] if i else 0
    return d


def ichimoku(h, l, c):
    def mid(s, n, i):
        w_h = max(h[max(0, i - n + 1):i + 1])
        w_l = min(l[max(0, i - n + 1):i + 1])
        return (w_h + w_l) / 2
    i = len(c) - 1
    tenkan = mid(h, 9, i)
    kijun = mid(h, 26, i)
    span_a = (tenkan + kijun) / 2
    span_b = mid(h, 52, i)
    above = c[i] > span_a and c[i] > span_b
    below = c[i] < span_a and c[i] < span_b
    cross = tenkan - kijun
    if above and cross > 0:
        return 1, 0.8
    if below and cross < 0:
        return -1, 0.8
    if above:
        return 1, 0.4
    if below:
        return -1, 0.4
    return 0, 0.0


def _klines(rows):
    rows = sorted(rows, key=lambda r: int(r.get("time", r.get("t", 0)) or 0))
    o = [float(r.get("open", r.get("o", 0))) for r in rows]
    h = [float(r.get("high", r.get("h", 0))) for r in rows]
    l = [float(r.get("low", r.get("l", 0))) for r in rows]
    c = [float(r.get("close", r.get("c", 0))) for r in rows]
    v = [float(r.get("baseVol", r.get("volume", r.get("v", 0))) or 0) for r in rows]
    return o, h, l, c, v


def analyze(symbol, klines, funding_rate=None):
    """Run all 10 strategies. Returns dict with direction, confidence, votes."""
    o, h, l, c, v = _klines(klines)
    if len(c) < 60:
        return {"symbol": symbol, "dir": "FLAT", "conf": 0.0, "agree": 0, "votes": [], "price": c[-1] if c else 0}
    i = len(c) - 1
    votes = []

    e9, e21 = ema(c, 9), ema(c, 21)
    gap = (e9[i] - e21[i]) / c[i] * 100
    votes.append(("EMA", 1 if gap > 0.02 else -1 if gap < -0.02 else 0, min(abs(gap) / 0.2, 1)))

    r = rsi(c)[i]
    if r < 30:
        votes.append(("RSI", 1, (30 - r) / 30 + 0.5))
    elif r > 70:
        votes.append(("RSI", -1, (r - 70) / 30 + 0.5))
    elif r > 55:
        votes.append(("RSI", 1, 0.3))
    elif r < 45:
        votes.append(("RSI", -1, 0.3))
    else:
        votes.append(("RSI", 0, 0.0))

    m, s = macd(c)
    hist, prev = m[i] - s[i], m[i - 1] - s[i - 1]
    cross = 1 if (hist > 0 and prev <= 0) else -1 if (hist < 0 and prev >= 0) else 0
    d = cross if cross else (1 if hist > 0 else -1 if hist < 0 else 0)
    votes.append(("MACD", d, 1.0 if cross else min(abs(hist) / (c[i] * 0.001), 1)))

    if len(v) >= 21 and sum(v[-21:-1]) > 0:
        ratio = v[i] / (sum(v[-21:-1]) / 20)
        mom_c = (c[i] - c[i - 5]) / c[i] * 100
        if ratio > 1.5:
            votes.append(("VOLUME", 1 if mom_c > 0 else -1 if mom_c < 0 else 0, min(ratio / 3, 1)))
        else:
            votes.append(("VOLUME", 0, 0.0))
    else:
        votes.append(("VOLUME", 0, 0.0))

    chg = (c[i] - c[i - 10]) / c[i - 10] * 100
    votes.append(("MOMENTUM", 1 if chg > 0.3 else -1 if chg < -0.3 else 0, min(abs(chg) / 1.5, 1)))

    a = atr(h, l, c)[i]
    brk = (c[i] - max(h[i - 20:i])) / a if a else 0
    brk_d = (min(l[i - 20:i]) - c[i]) / a if a else 0
    if brk > 0:
        votes.append(("ATR_BREAKOUT", 1, min(brk, 1)))
    elif brk_d > 0:
        votes.append(("ATR_BREAKOUT", -1, min(brk_d, 1)))
    else:
        votes.append(("ATR_BREAKOUT", 0, 0.0))

    if funding_rate is not None:
        try:
            fr = float(funding_rate)
            if fr > 0.001:
                votes.append(("FUNDING", -1, min(fr / 0.005, 1)))
            elif fr < -0.001:
                votes.append(("FUNDING", 1, min(-fr / 0.005, 1)))
            else:
                votes.append(("FUNDING", 0, 0.0))
        except (ValueError, TypeError):
            votes.append(("FUNDING", 0, 0.0))
    else:
        votes.append(("FUNDING", 0, 0.0))

    st = supertrend(h, l, c)[i]
    votes.append(("SUPERTREND", st, 0.8 if st else 0.0))

    pb = bollinger(c)[i]
    if pb < 0.1:
        votes.append(("BOLLINGER", 1, 0.8))
    elif pb > 0.9:
        votes.append(("BOLLINGER", -1, 0.8))
    elif pb > 0.6:
        votes.append(("BOLLINGER", 1, 0.3))
    elif pb < 0.4:
        votes.append(("BOLLINGER", -1, 0.3))
    else:
        votes.append(("BOLLINGER", 0, 0.0))

    idir, istr = ichimoku(h, l, c)
    votes.append(("ICHIMOKU", idir, istr))

    longs = [x for x in votes if x[1] > 0]
    shorts = [x for x in votes if x[1] < 0]
    ls, ss = sum(x[2] for x in longs), sum(x[2] for x in shorts)
    tot = ls + ss
    if tot <= 0:
        return {"symbol": symbol, "dir": "FLAT", "conf": 0.0, "agree": 0, "votes": votes, "price": c[i]}
    if ls >= ss:
        return {"symbol": symbol, "dir": "LONG", "conf": ls / tot * 100, "agree": len(longs),
                "votes": votes, "price": c[i]}
    return {"symbol": symbol, "dir": "SHORT", "conf": ss / tot * 100, "agree": len(shorts),
            "votes": votes, "price": c[i]}


STRATEGY_NAMES = ["EMA", "RSI", "MACD", "VOLUME", "MOMENTUM", "ATR_BREAKOUT",
                  "FUNDING", "SUPERTREND", "BOLLINGER", "ICHIMOKU"]
