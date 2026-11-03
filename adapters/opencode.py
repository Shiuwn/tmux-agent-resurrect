import os
from pathlib import Path
import re
import sqlite3
from contextlib import closing
import unicodedata
from adapter_api import Adapter, Resolution

def cell_width(text):
    return sum(0 if unicodedata.combining(c) else
               2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in text)


def after_column(text, column):
    position = 0
    for index, char in enumerate(text):
        if position >= column:
            return text[index:]
        position += cell_width(char)
    return ""


def opencode_sidebar_title(screen):
    # The sidebar shows the selected conversation, not titles quoted in the
    # main transcript. Account for wide CJK characters in the transcript.
    lines = screen.splitlines()
    for index, line in enumerate(lines[:15]):
        match = re.search(r" {2,}(Context)\s*$", line)
        if match:
            column = cell_width(line[:match.start(1)])
            if column < 30:
                continue
            title = "".join(after_column(row, column).strip() for row in lines[:index])
            return re.sub(r"\s+", "", title)
    return ""


def opencode_session(pane_id, title, cwd, run):
    data_root = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    database = data_root / "opencode/opencode.db"
    if not database.exists():
        return None, "opencode-index-missing"
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=3)) as db:
        sessions = db.execute("select id,title,directory from session where time_archived is null").fetchall()
    sessions = [(i, n) for i, n, d in sessions
                if os.path.realpath(d) == os.path.realpath(cwd)]
    candidates = {i for i, n in sessions if title in (n, "OpenCode | " + n)}
    if len(candidates) == 1:
        return next(iter(candidates)), "opencode-unique-name-and-cwd"
    # Older OpenCode versions set a generic terminal title. Read only the
    # visible sidebar header, and require an exact full title (including wraps).
    args = ["tmux", "capture-pane", "-p", "-t", pane_id, "-S", "0", "-E", "14"]
    screen = run(args)
    sidebar = opencode_sidebar_title(screen)
    if not sidebar:
        return None, "opencode-sidebar-unavailable"
    candidates = {i for i, n in sessions if re.sub(r"\s+", "", n) == sidebar}
    if len(candidates) != 1:
        return None, "opencode-ambiguous-or-unrecognized"
    if opencode_sidebar_title(run(args)) != sidebar:
        return None, "opencode-session-changed-during-save"
    return next(iter(candidates)), "opencode-sidebar-and-cwd"



def resolve(ctx):
    session_id, method = opencode_session(ctx.pane_id, ctx.title, ctx.cwd, ctx.run)
    return Resolution(session_id, method)


ADAPTER = Adapter(
    name="opencode",
    process_names=("opencode",),
    session_id_pattern=r"ses_[A-Za-z0-9]+",
    resume_argv=("opencode", "--session", "{session_id}", "{cwd}"),
    resolve=resolve,
)
