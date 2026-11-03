#!/usr/bin/env python3
"""Build an allowlisted source bundle; never include local session data."""
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parent
destination = root / "dist/tmux-agent-resurrect-0.2.0.tar.gz"
destination.parent.mkdir(exist_ok=True)
files = ["README.md", "README.zh-CN.md", "llm.txt", "agent-resurrect.tmux", "codex-resurrect.py", "install.py",
         "package.py", "scripts/save.sh", "tmux.conf.example", "test_codex_resurrect.py",
         "test_plugin.py", "test_adapters.py", "adapter_api.py", "adapter_registry.py",
         "adapters/__init__.py", "adapters/codex.py", "adapters/opencode.py",
         "scripts/configure.py", "examples/example_agent.py"]
def portable_info(info):
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    return info


with tarfile.open(destination, "w:gz") as archive:
    for name in files:
        archive.add(root / name, arcname="tmux-agent-resurrect/" + name, filter=portable_info)
print(destination)
