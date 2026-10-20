"""J+R Telegram agent — command dispatcher. Part 1: setup, helpers, chat flow."""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.parse

import config
import soul as soulmod
import models as mm
import memory as mem
import skills as sk
import mcps
import teams
import runner
import gen

API = "https://api.telegram.org/bot" + config.TELEGRAM_BOT_TOKEN
OFFSET_FILE = os.path.join(config.BASE_DIR, ".offset")
LEARN_FILE = os.path.join(config.BASE_DIR, ".learning.json")


def api(method, **kw):
    data = urllib.parse.urlencode(kw).encode()
    req = urllib.request.Request(API + "/" + method, data=data)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def send(chat_id, text, reply_to=None):
    kw = {"chat_id": chat_id, "text": text[:4000]}
    if reply_to:
        kw["reply_to_message_id"] = reply_to
    return api("sendMessage", **kw)


def get_offset():
    if os.path.exists(OFFSET_FILE):
        with open(OFFSET_FILE) as f:
            return int(f.read().strip() or 0)
    return 0


def set_offset(v):
    with open(OFFSET_FILE, "w") as f:
        f.write(str(v))


def learning():
    if os.path.exists(LEARN_FILE):
        try:
            with open(LEARN_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"on": config.LEARNING, "notes": []}


def save_learning(l):
    with open(LEARN_FILE, "w") as f:
        json.dump(l, f, indent=2)


def improve_note(user_text, bot_text):
    """Improvement by experience: store short reusable patterns."""
    l = learning()
    if not l.get("on"):
        return
    low = user_text.lower()
    for cue, note in [("remember", "user asked to remember"),
                      ("always", "user stated a standing preference"),
                      ("never", "user stated a standing restriction"),
                      ("prefer", "user stated a preference")]:
        if cue in low and len(l.get("notes", [])) < 200:
            l["notes"].append(f"{time.strftime('%Y-%m-%d')}: {user_text[:160]}")
            break
    save_learning(l)


def think_and_answer(chat_id, user_text, msg_id=None, model=None):
    mem.append("user", user_text)
    hist = mem.read(n=10)
    ctx = "\n".join(f"{h['role']}: {h['text'][:300]}" for h in hist)
    notes = learning().get("notes", [])[-8:]
    sys_txt = soulmod.load() + "\n\nChat history:\n" + ctx
    if notes:
        sys_txt += "\n\nLearned notes:\n" + "\n".join("- " + n for n in notes)
    try:
        from trader_bridge import status_line
        sys_txt += "\n\nTrader engine: " + status_line()
    except Exception:
        pass
    out, used = mm.chat([{"role": "user", "content": user_text}], model=model, system=sys_txt)
    if out is None:
        return send(chat_id, "Model error: " + used, msg_id)
    mem.append("assistant", out)
    improve_note(user_text, out)
    return send(chat_id, out, msg_id)
