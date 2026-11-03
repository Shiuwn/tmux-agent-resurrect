#!/usr/bin/env bash
set -eu
plugin_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python_bin="$(tmux show-option -gqv @agent-resurrect-python)"
exec "${python_bin:-python3}" "$plugin_dir/scripts/configure.py"
