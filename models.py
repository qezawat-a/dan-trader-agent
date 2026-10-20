"""Model auto-detection + invocation via minis-model-use.

No hardcoded model and no fallback: a model is usable only if it answered a
real ping. Results are cached in models.json and refreshed by /set models.
"""
import json
import os
import subprocess
import time
import config

MODELS_FILE = os.path.join(config.BASE_DIR, "models.json")
DETECTOR = os.path.join(config.BASE_DIR, "detect_models.py")


def _ping(model_id, timeout=90):
    tmp = os.path.join(config.BASE_DIR, ".ping.json")
    with open(tmp, "w") as f:
        json.dump({"messages": [{"role": "user", "content": "Reply with the single word: pong"}], "max_tokens": 16}, f)
    try:
        r = subprocess.run(["minis-model-use", "run", "--model", model_id, "--input", tmp],
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        os.remove(tmp)
        return False, "timeout"
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return (r.returncode == 0 and bool(r.stdout.strip())), (r.stdout.strip()[:80] if r.returncode == 0 else r.stderr.strip()[:160])


def discover(refresh=False):
    """Return working models. Runs detection if cache missing or refresh requested."""
    if not refresh and os.path.exists(MODELS_FILE):
        try:
            with open(MODELS_FILE) as f:
                return json.load(f)["working"]
        except Exception:
            pass
    subprocess.run([sys.executable, DETECTOR], capture_output=True, text=True, timeout=1800)
    return load()


def load():
    if not os.path.exists(MODELS_FILE):
        return []
    try:
        with open(MODELS_FILE) as f:
            return json.load(f)["working"]
    except Exception:
        return []


def pick(preferred=None):
    ws = load()
    if not ws:
        return None
    if preferred:
        for w in ws:
            if preferred in w["model_id"]:
                return w
    return ws[0]


def chat(messages, model=None, system=None, max_tokens=2000, temperature=0.7):
    """Run a chat completion through minis-model-use. Returns (text, model_id) or (None, error)."""
    m = pick(model)
    if not m:
        return None, "no working models detected — run /set models first"
    body = {"messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    if system:
        body["system"] = system
    tmp = os.path.join(config.BASE_DIR, ".chat.json")
    with open(tmp, "w") as f:
        json.dump(body, f)
    try:
        r = subprocess.run(["minis-model-use", "run", "--model", m["model_id"], "--input", tmp],
                           capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return None, "model request timed out"
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    if r.returncode != 0:
        return None, (r.stderr.strip()[:200] or f"rc={r.returncode}")
    out = r.stdout.strip()
    if not out:
        return None, "empty response"
    try:
        data = json.loads(out)
        return data.get("content") or data.get("text") or out, m["model_id"]
    except Exception:
        return out, m["model_id"]