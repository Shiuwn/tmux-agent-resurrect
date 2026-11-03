#!/usr/bin/env python3
"""Install/remove the managed tmux configuration block. Never copy credentials."""
import argparse
from datetime import datetime
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
START = "# BEGIN agent-resurrect"
END = "# END agent-resurrect"


def config_quote(command):
    return '"' + command.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$') + '"'


def tmux(*args):
    return subprocess.run(["tmux", *args], text=True, capture_output=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path.home() / ".tmux.conf")
    parser.add_argument("--resurrect", type=Path, default=Path.home() / ".tmux/plugins/tmux-resurrect")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--no-reload", action="store_true", help="Only edit the config file")
    args = parser.parse_args()
    config = args.config.expanduser().absolute()
    resurrect = args.resurrect.expanduser().absolute() / "resurrect.tmux"
    if not args.uninstall:
        for binary in ("tmux", "ps", "lsof", "bash"):
            if not shutil.which(binary):
                parser.error(f"Missing dependency: {binary}")
        if sys.version_info < (3, 9):
            parser.error("Python 3.9 or newer is required")
    original = config.read_text() if config.exists() else ""
    text = re.sub(r"(?m)^# BEGIN agent-resurrect\n.*?^# END agent-resurrect\n?", "", original, flags=re.S)
    # Migrate the one-off configuration created before the reusable plugin.
    legacy = re.search(r"(?m)^# BEGIN codex-resurrect:.*?^# END codex-resurrect\n?", text, re.S)
    if legacy and not args.uninstall:
        text = text[:legacy.start()] + text[legacy.end():]
    if not args.uninstall:
        lines = [START]
        if "tmux-resurrect" not in text:
            if not resurrect.is_file():
                parser.error(f"Install tmux-resurrect first, or pass --resurrect PATH: {resurrect}")
            lines.append("run-shell " + config_quote("bash " + shlex.quote(str(resurrect))))
        lines += ["run-shell " + config_quote("bash " + shlex.quote(str(ROOT / "agent-resurrect.tmux"))), END]
        text = text.rstrip() + "\n\n" + "\n".join(lines) + "\n"
    if text != original:
        config.parent.mkdir(parents=True, exist_ok=True)
        if config.exists():
            backup = config.with_name(config.name + ".backup-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + "-agent-resurrect")
            shutil.copy2(config, backup)
            print(f"Backup: {backup}")
        config.write_text(text)
    print(f"{'Removed' if args.uninstall else 'Installed'}: {config}")
    if args.no_reload:
        return
    if tmux("list-sessions").returncode:
        print("No running tmux server; configuration will load on next start.")
        return
    if args.uninstall:
        subprocess.run([sys.executable, str(ROOT / "scripts/configure.py"), "--uninstall"], check=True)
    elif legacy:
        # The old hook is this same script. Chaining it would run the save twice.
        tmux("set-option", "-gu", "@resurrect-hook-post-save-layout")
        processes = tmux("show-option", "-gqv", "@resurrect-processes").stdout.strip()
        for token in ('"codex resume"', '"opencode --session"'):
            processes = processes.replace(token, "")
        tmux("set-option", "-g", "@resurrect-processes", processes.strip())
    result = tmux("source-file", str(config))
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    print("Reloaded tmux configuration; existing panes were not restarted.")


if __name__ == "__main__":
    main()
