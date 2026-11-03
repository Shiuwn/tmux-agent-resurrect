"""Template only: adapt the session lookup and command to your actual CLI.

Copy to ~/.config/tmux-agent-resurrect/adapters/my_agent.py, edit, then reload
~/.tmux.conf. This example expects your CLI's session-change hook to write a
local pane record; it never selects the latest session or trusts stale argv.
"""
import json
import os
from pathlib import Path
from adapter_api import Adapter, Resolution


def resolve(ctx):
    # Replace this lookup with your CLI's documented status API/index/hook.
    # Example hook-produced JSON: {"%12": {"pid": 1234, "cwd": "/work/project",
    #                                      "session_id": "session_abc123"}}
    state = Path.home() / '.local/state/example-cli/panes.json'
    if not state.exists():
        return Resolution(None, 'session-state-missing')
    record = json.loads(state.read_text()).get(ctx.pane_id, {})
    if record.get('pid') not in ctx.pids:
        return Resolution(None, 'stale-process-record')
    if os.path.realpath(record.get('cwd', '')) != os.path.realpath(ctx.cwd):
        return Resolution(None, 'directory-mismatch')
    return Resolution(record.get('session_id'), 'current-pane-record')


ADAPTER = Adapter(
    name='example-cli',
    process_names=('example-cli',),
    session_id_pattern=r'session_[A-Za-z0-9_-]+',
    # Placeholder flags: replace these with your CLI's real resume syntax.
    resume_argv=('example-cli', '--resume', '{session_id}', '--directory', '{cwd}'),
    resolve=resolve,
)
