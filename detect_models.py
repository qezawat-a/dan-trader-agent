"""Auto-detect which configured models answer on this key/gateway.

No hardcoded model and no fallback: a model is only usable if it returns a
real completion right now. Results go to models.json; the agent reads that file.
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "models.json")
PING = {"messages": [{"role": "user", "content": "Reply with the single word: pong"}], "max_tokens": 16}


def list_models():
    raw = subprocess.run(["minis-model-use", "list"], capture_output=True, text=True, timeout=60).stdout
    data = json.loads(raw)["models"]
    return [m for m in data if "text_output" in m.get("modalities", [])]


def ping(model_id, timeout=90):
    tmp = os.path.join(HERE, ".ping.json")
    with open(tmp, "w") as f:
        json.dump(PING, f)
    t0 = time.time()
    try:
        r = subprocess.run(["minis-model-use", "run", "--model", model_id, "--input", tmp],
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "timeout", 0.0
    finally:
        os.remove(tmp)
    ok = r.returncode == 0 and bool(r.stdout.strip())
    return ok, (r.stdout.strip()[:80] if ok else (r.stderr.strip()[:160] or f"rc={r.returncode}")), round(time.time() - t0, 2)


def main():
    models = list_models()
    if not models:
        sys.exit("No text-capable models are configured in minis-model-use. Add a provider in Settings > Model Groups.")
    working = []
    for m in models:
        ok, info, secs = ping(m["model_id"])
        print(("OK   " if ok else "FAIL ") + m["model_id"] + f"  ({secs}s)", flush=True)
        if ok:
            working.append({
                "model_id": m["model_id"],
                "entry_id": m["entry_id"],
                "provider": m.get("instance_label"),
                "modalities": m.get("modalities", []),
                "context_window": m.get("context_window"),
                "latency_s": secs,
            })
    working.sort(key=lambda w: w["latency_s"])
    with open(OUT, "w") as f:
        json.dump({"checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "working": working}, f, indent=2)
    print(f"\n{len(working)} working of {len(models)} checked -> {OUT}")
    if not working:
        sys.exit(1)


if __name__ == "__main__":
    main()
