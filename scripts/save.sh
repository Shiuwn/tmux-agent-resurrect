#!/usr/bin/env bash
set -eu
plugin_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
snapshot="${1:?tmux-resurrect snapshot path is required}"
previous="$(tmux show-option -gqv @agent-resurrect-previous-hook)"
if [ -n "$previous" ]; then
    # Preserve the pre-existing hook's command syntax and pass its snapshot
    # argument without expanding any characters in the path.
    bash -c "$previous \"\$1\"" -- "$snapshot"
fi
python_bin="$(tmux show-option -gqv @agent-resurrect-python)"
python_bin="${python_bin:-python3}"
exec "$python_bin" "$plugin_dir/codex-resurrect.py" "$snapshot"
