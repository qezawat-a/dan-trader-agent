
"""J+R Telegram agent — command dispatcher. Part 2: all commands. Appended to agent.py."""
import shlex


def cmd_help():
    return ("Commands:\n"
            "/harness /thinking <task> /set models /models /provider [name]\n"
            "/skills /skills_add <git-url> [name] /skill <name> <task>\n"
            "/mcp /mcp_add <name> <cmd-or-url> /mcp_tools <server> /mcp_call <server> <tool> [json]\n"
            "/soul /soul_add <text> /memory [keywords] /dream /deepsearch <q>\n"
            "/bugfix <error> /code_review <git-diff-path> /quit /auto_compat\n"
            "/compat /resume_session [id] /sessions /set_api_key <NAME> <value>\n"
            "/team <plan|build> <task> /tools /run <shell cmd>\n"
            "/app_connector <name> [target] /config [key] [value]\n"
            "/generator <image|tts|video|files|codes|docs> <prompt>\n"
            "/auto_approve_on_edit <on|off> /learning <on|off>\n"
            "Trading: /trade <cmd> — engine on/off, scan, status (see /trade help)")


def do_command(chat_id, text, msg_id=None):
    parts = text.strip().split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd == "/harness":
        return send(chat_id, "J+R harness: dispatcher + models + memory + soul + skills + mcp, all local. " + teams.compat_check(), msg_id)
    if cmd == "/thinking":
        return send(chat_id, teams.thinking(arg or "no task"), msg_id)
    if cmd == "/set" and arg.startswith("models"):
        send(chat_id, "Detecting working models (no fallback, no hardcode)...", msg_id)
        ws = mm.discover(refresh=True)
        if not ws:
            return send(chat_id, "No working models found.", msg_id)
        return send(chat_id, f"{len(ws)} working models:\n" + "\n".join(f"- {w['model_id']} ({w['latency_s']}s)" for w in ws), msg_id)
    if cmd == "/models":
        ws = mm.load() or mm.discover()
        if not ws:
            return send(chat_id, "No working models cached. Run /set models.", msg_id)
        return send(chat_id, "Working models:\n" + "\n".join(f"- {w['model_id']}" for w in ws), msg_id)
    if cmd == "/provider":
        st = mcps.state()
        if arg:
            st["provider"] = arg
            mcps.save(st)
            return send(chat_id, f"provider set: {arg}", msg_id)
        return send(chat_id, "provider: " + str(st.get("provider") or "(not set)") + "\ngateway: " + ("set" if config.NINEROUTER_URL else "missing"), msg_id)
    if cmd == "/skills":
        ss = sk.list_skills()
        return send(chat_id, "Skills:\n" + ("\n".join(f"- {s['name']}" for s in ss) if ss else "(none installed)"), msg_id)
    if cmd == "/skills_add":
        a = arg.split()
        if not a:
            return send(chat_id, "usage: /skills_add <git-url> [name]", msg_id)
        return send(chat_id, sk.add(a[0], a[1] if len(a) > 1 else None), msg_id)
    if cmd == "/skill":
        a = arg.split(None, 1)
        if len(a) < 2:
            return send(chat_id, "usage: /skill <name> <task>", msg_id)
        out, used = sk.run_skill(a[0], a[1])
        return send(chat_id, (out or used or "")[:4000], msg_id)
    if cmd == "/mcp":
        return send(chat_id, "MCP servers:\n" + mcps.mcp_list(), msg_id)
    if cmd == "/mcp_add":
        a = arg.split(None, 1)
        if len(a) < 2:
            return send(chat_id, "usage: /mcp_add <name> <command-or-url>", msg_id)
        src = a[1]
        if src.startswith("http"):
            return send(chat_id, mcps.mcp_add(a[0], url=src), msg_id)
        return send(chat_id, mcps.mcp_add(a[0], cmd=src), msg_id)
    if cmd == "/mcp_tools":
        return send(chat_id, mcps.mcp_tools(arg.strip() or "bitunix"), msg_id)
    if cmd == "/mcp_call":
        a = arg.split(None, 2)
        if len(a) < 2:
            return send(chat_id, "usage: /mcp_call <server> <tool> [json]", msg_id)
        try:
            js = json.loads(a[2]) if len(a) > 2 else None
        except Exception:
            return send(chat_id, "bad json args", msg_id)
        return send(chat_id, mcps.mcp_call(a[0], a[1], js), msg_id)
    if cmd == "/soul":
        return send(chat_id, soulmod.load()[:4000], msg_id)
    if cmd == "/soul_add":
        if not arg:
            return send(chat_id, "usage: /soul_add <text>", msg_id)
        soulmod.add(arg)
        return send(chat_id, "Soul updated.", msg_id)
    if cmd == "/memory":
        if arg:
            hits = mem.recall(arg)
            return send(chat_id, hits or "no matches", msg_id)
        return send(chat_id, mem.read() or "(empty today)", msg_id)
    if cmd == "/dream":
        return send(chat_id, mem.dream(), msg_id)
    if cmd == "/deepsearch":
        if not arg:
            return send(chat_id, "usage: /deepsearch <query>", msg_id)
        sys_txt = soulmod.load() + "\nDo a deep multi-angle analysis. Structure: findings, evidence, risks, next steps."
        out, used = mm.chat([{"role": "user", "content": arg}], system=sys_txt, max_tokens=4000)
        return send(chat_id, (out or used or "")[:4000], msg_id)
    if cmd == "/bugfix":
        plan = teams.fix_plan(arg or "no error given")
        out, used = mm.chat([{"role": "user", "content": arg}], system=soulmod.load() + "\n" + plan)
        return send(chat_id, (out or used or "")[:4000], msg_id)
    if cmd == "/code_review":
        try:
            with open(os.path.expanduser(arg.strip())) as f:
                diff = f.read()[:8000]
        except Exception:
            return send(chat_id, "cannot read file", msg_id)
        out, used = mm.chat([{"role": "user", "content": "Review this diff:\n" + diff}], system=soulmod.load())
        return send(chat_id, (out or used or "")[:4000], msg_id)
    if cmd == "/quit":
        return send(chat_id, "Session closed. History saved; use /resume_session to continue.", msg_id)
    if cmd == "/auto_compat":
        return send(chat_id, teams.compat_check(), msg_id)
    if cmd == "/compat":
        return send(chat_id, teams.compat_check(), msg_id)
    if cmd == "/resume_session":
        sid = arg.strip() or teams.current()
        lines = teams.read(sid)
        if not lines:
            return send(chat_id, f"session {sid}: no history", msg_id)
        return send(chat_id, f"resumed {sid}, last {len(lines)} msgs:\n" + "\n".join(f"{h['role']}: {h['text'][:200]}" for h in lines[-6:]), msg_id)
    if cmd == "/sessions":
        ss = teams.list_sessions()
        return send(chat_id, "Sessions:\n" + ("\n".join(ss) if ss else "(none)"), msg_id)
    if cmd == "/set_api_key":
        a = arg.split(None, 1)
        if len(a) < 2:
            return send(chat_id, "usage: /set_api_key <NAME> <value> — value is written to server env reference, never echoed", msg_id)
        os.environ[a[0]] = a[1]
        mem.write(f"API key reference set: {a[0]} (value hidden)")
        return send(chat_id, f"{a[0]}: set for this process (value hidden). Add it to host env to persist.", msg_id)
    if cmd == "/team":
        a = arg.split(None, 1)
        if len(a) < 2:
            return send(chat_id, "usage: /team <plan|build> <task>", msg_id)
        mode, task = a[0], a[1]
        sys_txt = soulmod.load() + ("\nProduce a build plan only." if mode == "plan" else "\nBuild it: produce complete code.")
        out, used = mm.chat([{"role": "user", "content": task}], system=sys_txt, max_tokens=4000)
        return send(chat_id, (out or used or "")[:4000], msg_id)
    if cmd == "/agents":
        a = arg.split(None, 1)
        if len(a) < 2:
            return send(chat_id, "usage: /agents <build|plan> <task>", msg_id)
        sys_txt = soulmod.load() + ("\nProduce a build plan only." if a[0] == "plan" else "\nProduce complete build output.")
        out, used = mm.chat([{"role": "user", "content": a[1]}], system=sys_txt, max_tokens=4000)
        return send(chat_id, (out or used or "")[:4000], msg_id)
    if cmd == "/tools":
        return send(chat_id, "Tools: chat, shell /run, skills, mcp, generators, trader engine (/trade).", msg_id)
    if cmd == "/run":
        if not runner.allowed(chat_id):
            return send(chat_id, "not allowed for this chat", msg_id)
        if not arg:
            return send(chat_id, "usage: /run <shell cmd>", msg_id)
        rc, out = runner.run(arg)
        return send(chat_id, f"rc={rc}\n{out}"[:4000], msg_id)
    if cmd == "/app_connector":
        a = arg.split(None, 1)
        if not a:
            return send(chat_id, "usage: /app_connector <name> [target]", msg_id)
        return send(chat_id, mcps.connector(a[0], a[1] if len(a) > 1 else None), msg_id)
    if cmd == "/config":
        st = mcps.state()
        a = arg.split(None, 1)
        if not a:
            safe = {k: v for k, v in st.items() if k != "mcp"}
            return send(chat_id, "state: " + json.dumps(safe)[:2000] + f"\nauto_approve_on_edit={config.AUTO_APPROVE_ON_EDIT} learning={learning().get('on')}", msg_id)
        if len(a) == 1:
            return send(chat_id, f"{a[0]} = {st.get(a[0], getattr(config, a[0].upper(), '(unknown)'))}", msg_id)
        st[a[0]] = a[1]
        mcps.save(st)
        return send(chat_id, f"{a[0]} set", msg_id)
    if cmd == "/generator":
        a = arg.split(None, 1)
        if len(a) < 2:
            return send(chat_id, "usage: /generator <image|tts|video|files|codes|docs> <prompt>", msg_id)
        kind, prompt = a[0].lower(), a[1]
        fn = {"image": gen.image, "tts": gen.tts, "video": gen.video,
              "files": gen.files, "codes": gen.code, "docs": gen.docs}.get(kind)
        if not fn:
            return send(chat_id, "unknown generator kind", msg_id)
        send(chat_id, f"generating {kind}...", msg_id)
        return send(chat_id, fn(prompt)[:4000], msg_id)
    if cmd == "/auto_approve_on_edit":
        v = arg.strip().lower() in ("on", "1", "true")
        os.environ["DAN_AUTO_APPROVE_ON_EDIT"] = "1" if v else "0"
        config.AUTO_APPROVE_ON_EDIT = v
        return send(chat_id, f"auto_approve_on_edit={'on' if v else 'off'}", msg_id)
    if cmd == "/learning":
        l = learning()
        v = arg.strip().lower() in ("on", "1", "true")
        l["on"] = v
        save_learning(l)
        return send(chat_id, f"learning={'on' if v else 'off'}", msg_id)
    if cmd == "/trade":
        try:
            import trader_bridge
            return send(chat_id, trader_bridge.handle(arg)[:4000], msg_id)
        except Exception as e:
            return send(chat_id, "trader engine not merged yet: " + str(e)[:200], msg_id)
    if cmd == "/start":
        return send(chat_id, "J+R online. " + cmd_help()[:2000], msg_id)
    if cmd == "/help":
        return send(chat_id, cmd_help(), msg_id)
    return None
