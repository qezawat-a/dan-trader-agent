"""MCP connections (minis-mcp-cli) + app connectors + persisted config."""
import json
import os
import subprocess
import config

STATE_FILE = os.path.join(config.BASE_DIR, "state.json")


def state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"mcp": [], "connectors": {}, "provider": None, "sessions": {}}


def save(st):
    with open(STATE_FILE, "w") as f:
        json.dump(st, f, indent=2)


def mcp_list():
    r = subprocess.run(["minis-mcp-cli", "list"], capture_output=True, text=True, timeout=60)
    return (r.stdout or r.stderr or "")[:3000]


def mcp_add(name, cmd=None, url=None, env=None, note=None):
    st = state()
    entry = {"name": name, "cmd": cmd, "url": url, "env": env or {}, "note": note}
    argv = ["minis-mcp-cli", "add", "--name", name]
    if url:
        argv += ["--url", url]
    elif cmd:
        argv += ["--command", cmd]
    for k, v in (env or {}).items():
        argv += ["--env", f"{k}={v}"]
    if note:
        argv += ["--note", note]
    r = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    if r.returncode == 0 and not any(s.get("name") == name for s in st["mcp"]):
        st["mcp"].append(entry)
        save(st)
    return (r.stdout or "") + (r.stderr or "") or "added"


def mcp_tools(server):
    r = subprocess.run(["minis-mcp-cli", "tools", server], capture_output=True, text=True, timeout=120)
    return (r.stdout or r.stderr or "")[:6000]


def mcp_call(server, tool, args=None):
    argv = ["minis-mcp-cli", "call", server, tool]
    if args:
        argv.append(json.dumps(args))
    r = subprocess.run(argv, capture_output=True, text=True, timeout=180)
    return (r.stdout or r.stderr or "")[:6000]


def connector(name, target=None, note=None):
    """Attach an app connector (records an endpoint/key reference, never the secret)."""
    st = state()
    if target is None:
        cur = st["connectors"].get(name)
        return json.dumps(cur) if cur else f"connector '{name}' not set"
    masked = target[:6] + "..." if len(target) > 9 else "***"
    st["connectors"][name] = {"target": masked, "note": note}
    save(st)
    return f"connector '{name}' set -> {masked}"
