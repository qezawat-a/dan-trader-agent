"""Bitunix futures WebSocket clients — public + private channels.

Public : wss://fapi.bitunix.com/public/  — kline, ticker, tickers, depth, trade,
         MarketPrice. Subscribe: {"symbol": ..., "ch": ...}.
Private: wss://fapi.bitunix.com/private/ — balance, position, order, tpsl.
         Login first: {"op":"login","args":[{apiKey,timestamp,nonce,sign}]} with
         sign = sha256(sha256(nonce + timestamp_sec + apiKey) + secret).
Heartbeat: {"op":"ping","ping":<sec>} every 3s. Reconnects automatically.
"""
import asyncio
import hashlib
import json
import random
import ssl
import string
import time

PUBLIC_URI = "wss://fapi.bitunix.com/public/"
PRIVATE_URI = "wss://fapi.bitunix.com/private/"

PUBLIC_CHANNELS = ["kline", "ticker", "tickers", "depth", "depth_book1", "trade", "MarketPrice"]
PRIVATE_CHANNELS = ["balance", "position", "order", "tpsl"]


def _ws_sign(api_key, secret_key):
    nonce = "".join(random.choices(string.ascii_letters + string.digits, k=32))
    ts = str(int(time.time()))
    digest = hashlib.sha256((nonce + ts + api_key).encode()).hexdigest()
    return {"apiKey": api_key, "timestamp": int(ts), "nonce": nonce,
            "sign": hashlib.sha256((digest + secret_key).encode()).hexdigest()}


def _ssl():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


class PublicWS:
    def __init__(self, on_msg=None):
        self.on_msg = on_msg or (lambda m: None)
        self.queue = asyncio.Queue()
        self.ws = None
        self.connected = False

    async def subscribe(self, channels):
        await self.ws.send(json.dumps({"op": "subscribe", "args": channels}))

    async def run(self, channels):
        import websockets
        while True:
            try:
                async with websockets.connect(PUBLIC_URI, ssl=_ssl(), ping_interval=None,
                                              close_timeout=5) as ws:
                    self.ws = ws
                    self.connected = True
                    await self.subscribe(channels)
                    ping = asyncio.create_task(self._ping())
                    try:
                        async for raw in ws:
                            try:
                                d = json.loads(raw)
                            except ValueError:
                                continue
                            if d.get("op") == "ping":
                                continue
                            if d.get("ch") in PUBLIC_CHANNELS:
                                await self.queue.put(d)
                                self.on_msg(d)
                    finally:
                        ping.cancel()
                        self.connected = False
            except Exception:
                await asyncio.sleep(5)

    async def _ping(self):
        while True:
            await asyncio.sleep(3)
            try:
                await self.ws.send(json.dumps({"op": "ping", "ping": int(time.time())}))
            except Exception:
                break


class PrivateWS:
    def __init__(self, api_key, secret_key, on_msg=None):
        self.api_key = api_key
        self.secret_key = secret_key
        self.on_msg = on_msg or (lambda m: None)
        self.queue = asyncio.Queue()
        self.ws = None
        self.connected = False

    async def subscribe(self, channels):
        await self.ws.send(json.dumps({"op": "subscribe", "args": channels}))

    async def run(self, channels=None):
        import websockets
        channels = channels or [{"ch": c} for c in PRIVATE_CHANNELS]
        while True:
            try:
                async with websockets.connect(PRIVATE_URI, ssl=_ssl(), ping_interval=None,
                                              close_timeout=5) as ws:
                    self.ws = ws
                    await ws.send(json.dumps({"op": "login", "args": [_ws_sign(self.api_key, self.secret_key)]}))
                    self.connected = True
                    await self.subscribe(channels)
                    ping = asyncio.create_task(self._ping())
                    try:
                        async for raw in ws:
                            try:
                                d = json.loads(raw)
                            except ValueError:
                                continue
                            if d.get("op") == "ping":
                                continue
                            if d.get("ch") in PRIVATE_CHANNELS:
                                await self.queue.put(d)
                                self.on_msg(d)
                    finally:
                        ping.cancel()
                        self.connected = False
            except Exception:
                await asyncio.sleep(5)

    async def _ping(self):
        while True:
            await asyncio.sleep(3)
            try:
                await self.ws.send(json.dumps({"op": "ping", "ping": int(time.time())}))
            except Exception:
                break
