#!/usr/bin/env python3
"""Configure tmux from adapter metadata; uninstall works even with broken adapters."""
import json
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from adapter_registry import load_adapters


def tmux(*args):
    return subprocess.check_output(['tmux', *args], text=True).strip()


def get(key):
    return tmux('show-option', '-gqv', key)


def put(key, value):
    tmux('set-option', '-g', key, value)


def encode(tokens):
    return ' '.join(json.dumps(token) for token in tokens)


def configure(uninstall=False):
    hook = shlex.quote(str(ROOT / 'scripts/save.sh'))
    current = get('@resurrect-hook-post-save-layout')
    tokens = shlex.split(get('@resurrect-processes'))
    owned = shlex.split(get('@agent-resurrect-added-processes'))
    if uninstall:
        if shlex.split(current) == [str(ROOT / 'scripts/save.sh')]:
            put('@resurrect-hook-post-save-layout', get('@agent-resurrect-previous-hook'))
            tmux('set-option', '-gu', '@agent-resurrect-previous-hook')
        if tokens not in (['false'], [':all:']):
            put('@resurrect-processes', encode([t for t in tokens if t not in owned]))
        tmux('set-option', '-gu', '@agent-resurrect-added-processes')
        return
    # Load and validate before touching the live hook or whitelist.
    adapters = load_adapters()
    if current != hook:
        put('@agent-resurrect-previous-hook', current)
        put('@resurrect-hook-post-save-layout', hook)
    if tokens in (['false'], [':all:']):
        return
    # Remove only entries owned by us; preserve pre-existing user entries.
    tokens = [t for t in tokens if t not in owned]
    added = []
    for adapter in adapters:
        prefix = adapter.restore_prefix
        if prefix not in tokens:
            tokens.append(prefix)
            added.append(prefix)
    put('@resurrect-processes', encode(tokens))
    put('@agent-resurrect-added-processes', encode(added))


if __name__ == '__main__':
    if sys.argv[1:] == ['--list']:
        print(json.dumps([{'name': a.name, 'process_names': a.process_names,
                           'restore_prefix': a.restore_prefix} for a in load_adapters()], indent=2))
    else:
        configure(uninstall=sys.argv[1:] == ['--uninstall'])
