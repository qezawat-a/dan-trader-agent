"""Generators: image / tts / video / files / code / docs via configured models."""
import base64
import json
import os
import subprocess
import time
import config

OUT_DIR = os.path.join(config.BASE_DIR, "generated")


def _ensure():
    os.makedirs(OUT_DIR, exist_ok=True)
    return OUT_DIR


def _run(model, body, timeout=300):
    tmp = os.path.join(config.BASE_DIR, ".gen.json")
    with open(tmp, "w") as f:
        json.dump(body, f)
    try:
        r = subprocess.run(["minis-model-use", "run", "--model", model, "--input", tmp],
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "timed out"
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    if r.returncode != 0:
        return None, (r.stderr.strip()[:200] or f"rc={r.returncode}")
    return r.stdout.strip(), None


def image(prompt, model=None, size="1024x1024"):
    import models as mm
    m = mm.pick(model)
    if not m:
        return "no working models — run /set models"
    out, err = _run(m["model_id"], {
        "prompt": prompt, "n": 1, "size": size,
        "messages": [{"role": "user", "content": f"Generate an image: {prompt}"}]}, timeout=600)
    if err:
        return "image failed: " + err
    _ensure()
    fn = f"image-{int(time.time())}.txt"
    path = os.path.join(OUT_DIR, fn)
    with open(path, "w") as f:
        f.write(out[:20000])
    return f"image result saved to generated/{fn} (raw payload, first 20k chars)"


def tts(text, model=None, voice="alloy"):
    import models as mm
    m = mm.pick(model)
    if not m:
        return "no working models — run /set models"
    body = {"messages": [{"role": "user", "content": text[:4000]}],
            "extra_body": {"input": text[:4000], "voice": voice}}
    out, err = _run(m["model_id"], body, timeout=600)
    if err:
        return "tts failed: " + err
    _ensure()
    try:
        data = json.loads(out)
        for key in ("audio", "data", "b64", "content"):
            blob = data.get(key)
            if blob and isinstance(blob, str) and len(blob) > 1000:
                fn = f"tts-{int(time.time())}.mp3"
                with open(os.path.join(OUT_DIR, fn), "wb") as f:
                    f.write(base64.b64decode(blob))
                return f"audio saved to generated/{fn}"
    except Exception:
        pass
    fn = f"tts-{int(time.time())}.txt"
    with open(os.path.join(OUT_DIR, fn), "w") as f:
        f.write(out[:20000])
    return f"tts payload saved to generated/{fn}"


def video(prompt, model=None):
    return image("video storyboard frames for: " + prompt, model=model)


def files(spec_text, model=None):
    import models as mm
    m = mm.pick(model)
    if not m:
        return "no working models — run /set models"
    out, err = _run(m["model_id"], {
        "messages": [{"role": "user", "content": "Produce the requested file contents, code only, no explanation:\n" + spec_text[:6000]}],
        "max_tokens": 4000})
    if err:
        return "files failed: " + err
    _ensure()
    fn = f"file-{int(time.time())}.md"
    with open(os.path.join(OUT_DIR, fn), "w") as f:
        f.write(out)
    return f"saved to generated/{fn}"


def code(spec_text, model=None):
    return files("Write complete runnable code. No placeholders:\n" + spec_text, model=model)


def docs(topic, model=None):
    return files("Write clear documentation with examples:\n" + topic, model=model)
