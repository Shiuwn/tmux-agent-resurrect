#!/usr/bin/env python3
"""Embed per-pane CLI resume IDs using discovered adapters.

No prompts or shell history are replayed. Unresolved Codex panes fail closed.
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

from adapter_api import Context, Resolution
from adapter_registry import load_adapters

SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏ "


def run(args):
    return subprocess.run(args, text=True, capture_output=True, timeout=30).stdout


def processes():
    result = {}
    for line in run(["ps", "-axo", "pid=,ppid=,comm="]).splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) == 3:
            result[int(parts[0])] = (int(parts[1]), parts[2])
    return result


def descendants(root, table):
    found = {root}
    while True:
        more = {pid for pid, (parent, _) in table.items() if parent in found}
        if more <= found:
            return found
        found |= more


def save(snapshot):
    snapshot = Path(snapshot)
    original = snapshot.read_text()
    table = processes()
    if not table:
        raise RuntimeError("Cannot inspect processes; snapshot was not modified")
    fmt = "\t".join("#{" + x + "}" for x in (
        "session_name", "window_index", "pane_index", "pane_id", "pane_pid",
        "pane_title", "pane_current_path"))
    panes = {}
    for line in run(["tmux", "list-panes", "-a", "-F", fmt]).splitlines():
        fields = line.split("\t")
        if len(fields) == 7:
            panes[tuple(fields[:3])] = fields[3:]
    if not panes:
        raise RuntimeError("Cannot list tmux panes; snapshot was not modified")
    adapters = load_adapters()
    output, report = [], []
    for line in original.splitlines():
        fields = line.split("\t")
        if fields[0] != "pane" or len(fields) != 11:
            output.append(line)
            continue
        pane = panes.get((fields[1], fields[2], fields[5]))
        if not pane:
            output.append(line)
            continue
        pane_id, root, title, cwd = pane
        tree = descendants(int(root), table)
        matches = [(adapter, tuple(pid for pid in tree
                    if pid in table and Path(table[pid][1]).name in adapter.process_names)) for adapter in adapters]
        matches = [(adapter, pids) for adapter, pids in matches if pids]
        if not matches:
            output.append(line)
            continue
        adapter, pids = matches[0]
        tool = adapter.name
        session_id, method = None, "multiple-agent-processes"
        if len(matches) == 1:
            try:
                result = adapter.resolve(Context(pane_id, title, cwd, pids, run))
                if not isinstance(result, Resolution):
                    raise TypeError("Resolver must return Resolution")
                session_id, method = result.session_id, result.method
            except Exception as error:
                # A broken custom adapter must not stop other panes being saved.
                method = "resolver-error:" + type(error).__name__
        # A title changed while reading: don't save a potentially stale mapping.
        current = run(["tmux", "display-message", "-p", "-t", pane_id, "#{pane_title}"]).rstrip("\n")
        if current.lstrip(SPINNER) != title.lstrip(SPINNER):
            session_id, method = None, "title-changed-during-save"
        try:
            if session_id is None:
                raise ValueError("unresolved")
            command = adapter.command(session_id, cwd)
            fields[10] = ":" + shlex.join(command)
        except (ValueError, TypeError):
            if session_id is not None:
                method = "invalid-session-id"
            session_id = None
            fields[10] = ":"  # Do not accidentally launch a new chat.
        report.append({"pane": pane_id, "target": f"{fields[1]}:{fields[2]}.{fields[5]}",
                       "tool": tool, "session_id": session_id, "method": method, "cwd": cwd})
        output.append("\t".join(fields))
    atomic_write(snapshot, "\n".join(output) + "\n")
    # Human-readable diagnostics travel with the corresponding snapshot.
    atomic_write(Path(str(snapshot) + ".codex.json"), json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    skipped = sum(not r["session_id"] for r in report)
    counts = {adapter.name: sum(r["tool"] == adapter.name and bool(r["session_id"]) for r in report)
              for adapter in adapters}
    message = "Saved " + ", ".join(f"{name} {count}" for name, count in counts.items())
    message += f"; skipped {skipped} unresolved panes"
    print(message)
    if skipped:
        run(["tmux", "display-message", "-d", "10000", message + "; see snapshot .codex.json"])
    return report


def atomic_write(path, text):
    fd, temporary = tempfile.mkstemp(prefix=".codex-resurrect-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


if __name__ == "__main__":
    try:
        save(sys.argv[1])
    except Exception as error:
        print(f"codex-resurrect: {error}", file=sys.stderr)
        sys.exit(1)
