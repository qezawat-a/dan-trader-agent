"""Local shell runner — explicit terminal access, gated by chat-id allowlist."""
import subprocess
import config

TIMEOUT = 120


def run(cmd):
    """Run a shell command. Returns (rc, output). Dangerous ops need owner chat."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return 124, "timed out"
    out = (r.stdout or "") + (r.stderr or "")
    return r.returncode, out[:6000] or "(no output)"


def allowed(chat_id):
    a = str(getattr(config, "ALLOWED_CHAT_ID", "0"))
    return a == "0" or str(chat_id) == a
