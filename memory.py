"""Memory: daily log + global memory. Mirrors the app's memory system."""
import os
import datetime
import config

DAILY_DIR = os.path.join(config.BASE_DIR, "memory")
GLOBAL_FILE = os.path.join(config.BASE_DIR, "memory", "GLOBAL.md")


def _ensure():
    os.makedirs(DAILY_DIR, exist_ok=True)


def today():
    return datetime.date.today().isoformat()


def _path(date=None):
    _ensure()
    return os.path.join(DAILY_DIR, (date or today()) + ".md")


def write(content, date=None):
    """Append an entry to today's daily log."""
    _ensure()
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    with open(_path(date), "a") as f:
        f.write(f"\n<!-- {date or today()} {ts} -->\n{content.strip()}\n")
    return _path(date)


def read(date=None, lines=40):
    p = _path(date)
    if not os.path.exists(p):
        return ""
    with open(p) as f:
        return "".join(f.readlines()[-lines:])


def read_global():
    if not os.path.exists(GLOBAL_FILE):
        return ""
    with open(GLOBAL_FILE) as f:
        return f.read()


def write_global(content):
    _ensure()
    with open(GLOBAL_FILE, "w") as f:
        f.write(content.strip() + "\n")


def recall(keywords):
    """Keyword search across daily logs + global memory."""
    kws = [k.lower() for k in keywords.split() if k]
    if not kws:
        return ""
    hits = []
    for fn in sorted(os.listdir(DAILY_DIR), reverse=True):
        if not fn.endswith(".md"):
            continue
        try:
            with open(os.path.join(DAILY_DIR, fn)) as f:
                text = f.read()
        except OSError:
            continue
        low = text.lower()
        if all(k in low for k in kws):
            hits.append(f"### {fn}\n" + "\n".join(
                l for l in text.splitlines() if any(k in l.lower() for k in kws))[:1200])
    g = read_global()
    if g and all(k in g.lower() for k in kws):
        hits.append("### GLOBAL.md\n" + g[:1200])
    return "\n\n".join(hits[:8])[:4000]


def dream():
    """Rolling summary: distill today's log into a compact note and append."""
    _ensure()
    today_text = read(today())
    if not today_text.strip():
        return "Nothing logged today."
    summary = "Summary of today:\n" + "\n".join(
        "- " + l.strip() for l in today_text.splitlines() if l.strip() and not l.startswith("<!--"))[:1500]
    return summary