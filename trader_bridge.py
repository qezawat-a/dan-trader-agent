"""Bridge between Telegram agent and trader engine. Imported by agent_cmds.py."""
import threading
import time
from trader import bridge as trader_bridge

_send_fn = None
_started = False


def set_sender(fn):
    global _send_fn
    _send_fn = fn


def status_line():
    return trader_bridge.status_line()


def handle(text):
    if not _send_fn:
        return "trader engine: sender not set"
    return trader_bridge.handle(text)


def ensure_loops():
    global _started
    if not _started and _send_fn:
        trader_bridge.ensure_loops(_send_fn)
        _started = True


def scan_now():
    """One-shot scan; returns list of signals."""
    import tconfig
    import engine
    import client as _client_mod
    import os
    c = _client_mod.BitunixClient(os.environ.get("BITUNIX_API_KEY", ""), os.environ.get("BITUNIX_SECRET_KEY", ""))
    cfg = tconfig.load()
    return engine.scan_all(c, cfg)