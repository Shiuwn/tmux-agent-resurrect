# tmux-agent-resurrect

Bring your coding conversations back after a reboot.

A companion plugin for [tmux-resurrect](https://github.com/tmux-plugins/tmux-resurrect) that saves the conversation ID for each agent pane and resumes it when you restore your tmux workspace. Codex and OpenCode work out of the box. Other CLIs can be added with a small Python adapter.

[中文说明](README.zh-CN.md) · [Installation guide for agents](llm.txt) · [Adapter template](examples/example_agent.py)

## What it does

If you keep several coding agents open in tmux, restoring the window layout is only half the job. You also need each pane to reopen the right conversation—even when several panes share the same project directory.

This plugin adds a save hook to tmux-resurrect. For each supported agent pane, it identifies the current conversation and writes a resume command into the snapshot:

```sh
codex resume <conversation-id> -C <project-directory>
opencode --session <session-id> <project-directory>
```

When you restore the workspace, tmux-resurrect recreates the layout and runs those commands. Existing panes are left alone.

The plugin restores saved conversations, not running processes. Commands and model responses that were interrupted by shutdown do not pick up mid-execution. It does not send a prompt automatically or enable unattended approvals.

## Requirements

- tmux and [tmux-resurrect](https://github.com/tmux-plugins/tmux-resurrect)
- Python 3.9 or later, Bash, `ps`, and `lsof`
- Codex, OpenCode, or an adapter-supported CLI available in your login shell's `PATH`

Tested on macOS, with Windows support verified by a user running WSL. Native Linux installations have not yet been verified. Conversation detection also depends on each CLI's local storage format and terminal UI. The OpenCode adapter has been tested with version 1.19.3.

## Install

Clone the plugin into a location you intend to keep:

```sh
git clone https://github.com/Shiuwn/tmux-agent-resurrect.git \
  ~/.tmux/plugins/tmux-agent-resurrect
```

If you do not already have tmux-resurrect:

```sh
git clone https://github.com/tmux-plugins/tmux-resurrect.git \
  ~/.tmux/plugins/tmux-resurrect
```

Then run the installer:

```sh
python3 ~/.tmux/plugins/tmux-agent-resurrect/install.py
```

The installer backs up `~/.tmux.conf` before changing it, adds a managed configuration block, and reloads the configuration if tmux is running. It does not restart your panes. Running it again will not duplicate the block.

The plugin can live elsewhere; the installer uses its actual location. Keep that directory in place after installation.

### Custom configuration

```sh
python3 install.py --config ~/.config/tmux/tmux.conf
python3 install.py --resurrect /path/to/tmux-resurrect
python3 install.py --no-reload
```

`--config` selects the tmux configuration file. `--resurrect` selects an existing tmux-resurrect installation. `--no-reload` edits the file without applying it to a running server.

For manual installation, see [tmux.conf.example](tmux.conf.example). To choose a Python interpreter, set this option before loading the plugin:

```tmux
set -g @agent-resurrect-python /path/to/python3
```

### Install with TPM

If you use [TPM](https://github.com/tmux-plugins/tpm), declare tmux-resurrect before this plugin and keep the TPM startup line last:

```tmux
set -g @plugin 'tmux-plugins/tpm'
set -g @plugin 'tmux-plugins/tmux-resurrect'
set -g @plugin 'Shiuwn/tmux-agent-resurrect'

run '~/.tmux/plugins/tpm/tpm'
```

Use your usual TPM installation workflow. Choose either TPM or the installer to manage the plugin's loading configuration.

## Save and restore

The plugin uses tmux-resurrect's bindings. With the default tmux prefix:

1. Before shutting down, press **Ctrl+b**, then **Ctrl+s** to save.
2. After restarting, open tmux and press **Ctrl+b**, then **Ctrl+r** to restore.

A new save is required after installation; old snapshots do not contain the conversation IDs added by this plugin. Saving and restoring remain manual unless you separately configure automation.

For OpenCode, keep the conversation sidebar visible when saving. It provides the current conversation title when the terminal title only says `OpenCode`.

## How conversations are identified

The save hook inspects each pane's process tree, then asks the matching adapter to resolve its current conversation.

| CLI | Identification |
| --- | --- |
| Codex | Matches the pane title and working directory against the local `state_*.sqlite` index. Open rollout files can help distinguish conversations with the same name. |
| OpenCode | Matches the title and working directory against `opencode.db`. When necessary, reads the visible sidebar title, including wrapped text and wide characters. |

These are local heuristics, not an official pane-to-conversation API. A CLI update or a manually changed pane title can affect detection. The plugin does not choose the most recent conversation in a directory or rely solely on startup arguments that may have become stale after a conversation switch.

If a pane cannot be resolved unambiguously, its agent command is omitted from the snapshot. The pane comes back as a shell, and the save report marks it as skipped. Giving conversations distinct names and keeping the OpenCode sidebar visible helps avoid this.

### Snapshots and reports

Snapshots are stored in tmux-resurrect's configured `@resurrect-dir`, typically `~/.local/share/tmux/resurrect/` or `~/.tmux/resurrect/`. The `last` symlink points to the latest snapshot.

Each snapshot has a companion `<snapshot>.codex.json` report containing the pane, CLI name, session ID, working directory, and resolution method. The filename is retained for compatibility; reports cover all loaded adapters.

The built-in adapters read their tools' conversation indexes. They do not modify conversation data or credentials. Existing save hooks run first, and existing process restore entries are preserved. Explicit `@resurrect-processes=false` and `:all:` settings retain their meaning.

## Add another CLI

Custom adapters live outside the plugin checkout, so updates will not overwrite them:

```text
~/.config/tmux-agent-resurrect/adapters/my_agent.py
```

The location follows `XDG_CONFIG_HOME` when set. Start with the supplied template:

```sh
mkdir -p ~/.config/tmux-agent-resurrect/adapters
cp ~/.tmux/plugins/tmux-agent-resurrect/examples/example_agent.py \
  ~/.config/tmux-agent-resurrect/adapters/my_agent.py
```

Edit the file before loading it. `example-cli` and its flags are placeholders, not a supported tool.

Each file exports an `ADAPTER` with the process names, an ID pattern, a resume argument list, and a resolver:

```python
from adapter_api import Adapter, Resolution


def resolve(ctx):
    # Implement this lookup using your CLI's current-session API or local index.
    session_id = read_current_session(ctx)
    return Resolution(session_id, "current-session-index")


ADAPTER = Adapter(
    name="my-agent",
    process_names=("my-agent",),
    session_id_pattern=r"session_[A-Za-z0-9_-]+",
    resume_argv=("my-agent", "--resume", "{session_id}", "-C", "{cwd}"),
    resolve=resolve,
)
```

`read_current_session` is a function you supply. Return `Resolution(None, "reason")` when the current session cannot be identified. The resolver receives:

- `ctx.pane_id`, `ctx.title`, and `ctx.cwd`
- `ctx.pids`: the matching process IDs
- `ctx.run(argv)`: a command helper that returns stdout and has a 30-second timeout

Keep lookups read-only, and account for users switching conversations after launching the CLI. Return the current session, not the latest one in a directory.

`{session_id}` and `{cwd}` must each occupy an entire argument. The core validates IDs and quotes the argument list. The command and flags before the first placeholder become the restore allowlist entry; that prefix may contain only letters, digits, underscores, and hyphens. Use a command available in `PATH`, without shell syntax.

Check the adapter and reload your configuration:

```sh
python3 ~/.tmux/plugins/tmux-agent-resurrect/scripts/configure.py --list
tmux source-file ~/.tmux.conf
```

Allowlist entries, reports, and uninstall cleanup follow adapter metadata automatically. Reload after adding or removing an adapter. Duplicate adapter names, invalid metadata, and syntax errors are reported with the file path. Resolver failures, invalid session IDs, and panes matching multiple adapters are skipped.

Additional directories can be supplied through `AGENT_RESURRECT_ADAPTER_DIR`, separated by the platform's path separator. This variable must be available in the tmux server's environment. Files beginning with `_` are ignored. Custom adapters run as your user, so load code you trust.

## Move to another computer

For the same functionality on a new machine, install the plugin and its dependencies, then install and sign in to your agent CLIs.

To resume conversations from the old machine, you also need the project files, tmux snapshots, and each CLI's conversation data. Session IDs alone do not contain the conversation history. This plugin does not transfer that data, credentials, or API keys.

Save the workspace and exit the tools before backing up their databases. SQLite data may still be in WAL files; copying only a live database's main file can produce an incomplete backup. Use the tools' export and import features where available, or follow the migration procedure for the versions you use.

Keep project paths the same where possible. If your username or directory layout changes, update the pane directories and resume commands in the snapshot, and verify that the CLI can resume the migrated conversation at the new location. Try one conversation manually before restoring the entire workspace.

## Update or uninstall

For a clean Git checkout:

```sh
git -C ~/.tmux/plugins/tmux-agent-resurrect pull --ff-only
python3 ~/.tmux/plugins/tmux-agent-resurrect/install.py
```

To uninstall an installation managed by the script:

```sh
python3 ~/.tmux/plugins/tmux-agent-resurrect/install.py --uninstall
```

Uninstall backs up the configuration, removes the managed block, restores the previous live save hook, and removes allowlist entries added by this plugin. Snapshots are retained. If installation added the tmux-resurrect loading line inside the managed block, that line is removed too; keep a separate loading line if you still need it.

For a TPM installation, remove this plugin's declaration and follow TPM's removal workflow. Restart tmux when convenient to clear the live hook, or run `scripts/configure.py --uninstall` to clear it immediately without restarting panes.

## Development

```sh
python3 -m unittest -v test_codex_resurrect.py test_adapters.py test_plugin.py
python3 package.py
```

Integration tests use isolated tmux sockets. Coverage includes adapter discovery, command quoting, ambiguous sessions, dynamic allowlists, existing hooks, repeated installation, and uninstall. Packaging produces `dist/tmux-agent-resurrect-0.2.0.tar.gz` from an explicit file list, without local configurations, conversation data, credentials, or user adapters.
