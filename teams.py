"""Session resume + thinking + compat + teams plan."""
import json
import os
import time
import config

SESSIONS_DIR = os.path.join(config.BASE_DIR, "sessions")
CURRENT_FILE = os.path.join(config.BASE_DIR, ".current_session")


def _ensure():
    os.makedirs(SESSIONS_DIR, exist_ok=True)


def current():
    if os.path.exists(CURRENT_FILE):
        with open(CURRENT_FILE) as f:
            return f.read().strip()
    sid = f"sess-{int(time.time())}"
    with open(CURRENT_FILE, "w") as f:
        f.write(sid)
    return sid


def new():
    sid = f"sess-{int(time.time())}"
    with open(CURRENT_FILE, "w") as f:
        f.write(sid)
    return sid


def append(role, text, sid=None):
    _ensure()
    sid = sid or current()
    path = os.path.join(SESSIONS_DIR, sid + ".jsonl")
    with open(path, "a") as f:
        f.write(json.dumps({"t": time.time(), "role": role, "text": text[:2000]}) + "\n")


def read(sid=None, n=30):
    sid = sid or current()
    path = os.path.join(SESSIONS_DIR, sid + ".jsonl")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        lines = f.readlines()[-n:]
    return [json.loads(l) for l in lines if l.strip()]


def list_sessions():
    _ensure()
    out = []
    for fn in sorted(os.listdir(SESSIONS_DIR), reverse=True):
        if fn.endswith(".jsonl"):
            out.append(fn[:-6])
    return out[:20]


def thinking(text, strength=3):
    """/thinking: return a structured reasoning trace for the current task."""
    lines = [l.strip() for l in text.splitlines() if l.strip()][:20]
    steps = ["1. Constraint: what must hold (risk, scope, secrets)",
             "2. Plan: smallest verifiable step",
             "3. Execute: tool call, not intention",
             "4. Check: read the output, then continue"]
    return "THINKING trace\n" + "\n".join(steps) + "\n\nTask:\n" + "\n".join(f"- {l}" for l in lines[:10])


def compat_check():
    """Verify the environment: python, git, tokens (names only), models cache."""
    import subprocess
    checks = []
    checks.append(("python3", "ok"))
    checks.append(("git", "ok" if subprocess.run(["which", "git"], capture_output=True).returncode == 0 else "missing"))
    for v in ["TELEGRAM_BOT_TOKEN", "BITUNIX_API_KEY", "BITUNIX_SECRET_KEY", "NINEROUTER_KEY", "GITHUB_PUSH_TOKEN"]:
        checks.append((v, "set" if os.environ.get(v) else "missing"))
    import models as mm
    checks.append(("working models", str(len(mm.load()))))
    return "\n".join(f"{k}: {v}" for k, v in checks)


def review_diff(diff):
    """Skeleton for /code-review: returns structure, real review happens via chat."""
    n = len(diff.splitlines())
    return f"diff: {n} lines. Review: check scope, edge cases, error paths, secrets."


def fix_plan(error_text):
    return "BUGFIX plan: reproduce -> smallest failing case -> patch -> verify -> log.\nError:\n" + error_text[:1000]
