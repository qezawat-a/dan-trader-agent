"""J+R Telegram agent — main loop (long polling)."""
import sys
import time
import urllib.request
import urllib.parse
import json

sys.path.insert(0, __import__("os").path.dirname(__file__))
import agent as A
import agent_cmds as C

COMMANDS = ("/harness", "/thinking", "/set", "/models", "/provider", "/skills", "/skills_add",
            "/skill", "/mcp", "/mcp_add", "/mcp_tools", "/mcp_call", "/soul", "/soul_add",
            "/memory", "/dream", "/deepsearch", "/bugfix", "/bugfixes", "/code_review",
            "/quit", "/auto_compat", "/compat", "/resume_session", "/sessions", "/set_api_key",
            "/set-api-key", "/team", "/agents", "/tools", "/run", "/app_connector",
            "/config", "/generator", "/auto_approve_on_edit", "/learning", "/trade",
            "/start", "/help")


def poll():
    off = A.get_offset()
    data = urllib.parse.urlencode({"offset": off, "timeout": 50}).encode()
    req = urllib.request.Request(A.API + "/getUpdates", data=data)
    try:
        with urllib.request.urlopen(req, timeout=70) as r:
            return json.load(r)
    except Exception:
        return {"ok": False}


def handle(upd):
    msg = upd.get("message") or upd.get("edited_message") or {}
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    text = (msg.get("text") or "").strip()
    msg_id = msg.get("message_id")
    if not chat_id or not text:
        return
    import config as cfg
    a = str(getattr(cfg, "ALLOWED_CHAT_ID", "0"))
    if a != "0" and str(chat_id) != a:
        A.send(chat_id, "unauthorized chat", msg_id)
        return
    first = text.split(None, 1)[0].lower()
    if first in ("/bugfixes",):
        first = "/bugfix"
    if first in ("/set-api-key",):
        first = "/set_api_key"
    if first in COMMANDS or first.startswith("/trade"):
        if first == "/bugfix":
            text = "/bugfix " + text.split(None, 1)[1] if " " in text else "/bugfix"
        r = C.do_command(chat_id, text if first.startswith("/") else text, msg_id)
        if r is not None:
            return
    A.think_and_answer(chat_id, text, msg_id)


def main():
    print("J+R agent polling...", flush=True)
    while True:
        d = poll()
        if not d.get("ok"):
            time.sleep(3)
            continue
        for u in d.get("result", []):
            A.set_offset(u["update_id"] + 1)
            try:
                handle(u)
            except Exception as e:
                print("handle error:", str(e)[:200], flush=True)


if __name__ == "__main__":
    main()
