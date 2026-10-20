"""Skills registry: local skills + add from repo/url."""
import json
import os
import subprocess
import config

SKILLS_DIR = os.path.join(config.BASE_DIR, "skills")
INDEX_FILE = os.path.join(SKILLS_DIR, "index.json")


def _ensure():
    os.makedirs(SKILLS_DIR, exist_ok=True)
    if not os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "w") as f:
            json.dump([], f)


def list_skills():
    _ensure()
    try:
        with open(INDEX_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def describe(name):
    for s in list_skills():
        if s.get("name") == name:
            path = os.path.join(SKILLS_DIR, name, "SKILL.md")
            if os.path.exists(path):
                with open(path) as f:
                    return f.read()[:4000]
            return json.dumps(s)
    return "unknown skill"


def add(source, name=None):
    """Install a skill from a git URL or local path."""
    _ensure()
    name = name or os.path.basename(source.rstrip("/")).replace(".git", "")
    dest = os.path.join(SKILLS_DIR, name)
    if os.path.exists(dest):
        return f"skill '{name}' already installed"
    if source.startswith(("http", "git@")):
        r = subprocess.run(["git", "clone", "--depth", "1", source, dest],
                           capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            return "clone failed: " + (r.stderr.strip()[:200] or "unknown error")
    else:
        if not os.path.isdir(source):
            return "source not found"
        subprocess.run(["cp", "-r", source, dest], timeout=60)
    skills = list_skills()
    if not any(s.get("name") == name for s in skills):
        skills.append({"name": name, "source": source})
        with open(INDEX_FILE, "w") as f:
            json.dump(skills, f, indent=2)
    return f"skill '{name}' installed"


def run_skill(name, task, model=None, system=None):
    """Load a skill's SKILL.md and run the task under it."""
    doc = describe(name)
    if doc == "unknown skill":
        return "unknown skill"
    import models
    sys_txt = (system or "") + f"\n\nSkill '{name}' instructions:\n{doc}"
    return models.chat([{"role": "user", "content": task}], model=model, system=sys_txt)
