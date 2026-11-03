import os
from pathlib import Path
import re
import sqlite3
from contextlib import closing
from adapter_api import Adapter, Resolution

UUID = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏ "

def names_match(title, name, cwd):
    title = title.lstrip(SPINNER)
    return bool(name) and title in (name, name + " | " + Path(cwd).name)


def choose_id(candidates, opened):
    # Open rollout files identify the actual live thread, including /resume changes.
    live = candidates & opened
    if len(live) == 1:
        return next(iter(live)), "open-rollout"
    if len(candidates) == 1:
        return next(iter(candidates)), "unique-name-and-cwd"
    # Startup arguments alone can become stale after /new or /resume. Never use
    # them to break a tie between same-name conversations.
    return None, "ambiguous-or-unrecognized"



def resolve(ctx):
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    dbs = sorted(codex_home.glob("state_*.sqlite"),
                 key=lambda p: int(p.stem.split("_")[-1]), reverse=True)
    threads = []
    if dbs:
        with closing(sqlite3.connect(dbs[0].as_uri() + "?mode=ro", uri=True, timeout=3)) as db:
            columns = {r[1] for r in db.execute("pragma table_info(threads)")}
            name = "coalesce(name,title)" if "name" in columns else "title"
            threads = db.execute(f"select id,{name},cwd from threads where archived=0").fetchall()
    opened = set()
    for pid in ctx.pids:
        files = ctx.run(["lsof", "-n", "-P", "-p", str(pid), "-Fn"])
        opened.update(re.findall(r"rollout-[^\n]*?(" + UUID + r")\.jsonl", files))
    candidates = {i for i, name, directory in threads
                  if os.path.realpath(directory) == os.path.realpath(ctx.cwd)
                  and names_match(ctx.title, name, ctx.cwd)}
    return Resolution(*choose_id(candidates, opened))


ADAPTER = Adapter(
    name="codex",
    process_names=("codex",),
    session_id_pattern=UUID,
    resume_argv=("codex", "resume", "{session_id}", "-C", "{cwd}"),
    resolve=resolve,
)
