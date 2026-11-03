"""Run with Python unittest; requires tmux for isolated integration checks."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


@unittest.skipUnless(shutil.which("tmux"), "tmux not installed")
class PluginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tmux-plugin-")
        self.root = Path(self.temp.name)
        self.socket = self.root / "socket"
        self.env = dict(os.environ, TMUX=str(self.socket) + ",1,0")
        self.command("tmux", "-S", str(self.socket), "-f", "/dev/null", "new-session", "-d", "-s", "test")

    def tearDown(self):
        self.command("tmux", "-S", str(self.socket), "kill-server")
        self.temp.cleanup()

    def command(self, *args):
        return subprocess.run(args, env=self.env, text=True, capture_output=True, check=True).stdout.strip()

    def tmux(self, *args):
        return self.command("tmux", *args)

    def test_preserves_disable_and_restore_all(self):
        for value in ("false", ":all:"):
            self.tmux("set-option", "-g", "@resurrect-processes", value)
            self.command("bash", str(ROOT / "agent-resurrect.tmux"))
            self.assertEqual(self.tmux("show-option", "-gqv", "@resurrect-processes"), value)

    def test_custom_whitelist_sync_and_broken_adapter_uninstall(self):
        import shlex
        from test_adapters import CUSTOM
        config_root = self.root / "config"
        custom = config_root / "tmux-agent-resurrect/adapters"
        custom.mkdir(parents=True)
        module = custom / "demo.py"
        module.write_text(CUSTOM)
        self.env["XDG_CONFIG_HOME"] = str(config_root)
        self.tmux("set-option", "-g", "@resurrect-processes", "ssh")
        self.command("bash", str(ROOT / "agent-resurrect.tmux"))
        tokens = shlex.split(self.tmux("show-option", "-gqv", "@resurrect-processes"))
        self.assertEqual(tokens, ["ssh", "codex resume", "opencode --session", "demo --resume"])
        module.unlink()
        self.command("bash", str(ROOT / "agent-resurrect.tmux"))
        tokens = shlex.split(self.tmux("show-option", "-gqv", "@resurrect-processes"))
        self.assertNotIn("demo --resume", tokens)
        module.write_text(CUSTOM)
        self.command("bash", str(ROOT / "agent-resurrect.tmux"))
        module.write_text("invalid python content !!!")
        self.command("python3", str(ROOT / "scripts/configure.py"), "--uninstall")
        tokens = shlex.split(self.tmux("show-option", "-gqv", "@resurrect-processes"))
        self.assertEqual(tokens, ["ssh"])

    def test_hook_chaining_reload_and_uninstall(self):
        # Install from a directory containing spaces and apostrophes.
        plugin = self.root / "plugin with ' spaces"
        shutil.copytree(ROOT, plugin, ignore=shutil.ignore_patterns("dist", "__pycache__"))
        config = self.root / "tmux.conf"
        prior_hook = "printf '%s'"
        config.write_text("# existing config\n# tmux-resurrect already loaded\n")
        self.tmux("set-option", "-g", "@resurrect-hook-post-save-layout", prior_hook)
        self.tmux("set-option", "-g", "@resurrect-processes", 'ssh "codex resume"')
        self.command("python3", str(plugin / "install.py"), "--config", str(config))
        first = config.read_text()
        hook = self.tmux("show-option", "-gqv", "@resurrect-hook-post-save-layout")
        self.assertIn("save.sh", hook)
        self.assertEqual(self.tmux("show-option", "-gqv", "@agent-resurrect-previous-hook"), prior_hook)
        self.command("python3", str(plugin / "install.py"), "--config", str(config))
        self.assertEqual(config.read_text(), first)
        self.assertEqual(self.tmux("show-option", "-gqv", "@resurrect-hook-post-save-layout"), hook)
        self.assertEqual(self.tmux("show-option", "-gqv", "@resurrect-processes").count('"opencode --session"'), 1)
        # Use a fake Python executable to verify hook argument forwarding.
        fake = self.root / "fake-python"
        fake.write_text('#!/bin/sh\nprintf "%s\\n" "$2"\n')
        fake.chmod(0o755)
        self.tmux("set-option", "-g", "@agent-resurrect-python", str(fake))
        snapshot = str(self.root / "snapshot with ' spaces.txt")
        output = self.command("bash", str(plugin / "scripts/save.sh"), snapshot)
        self.assertEqual(output, snapshot + snapshot)
        self.command("python3", str(plugin / "install.py"), "--config", str(config), "--uninstall")
        self.assertNotIn("# BEGIN agent-resurrect", config.read_text())
        self.assertEqual(self.tmux("show-option", "-gqv", "@resurrect-hook-post-save-layout"), prior_hook)
        self.assertEqual(__import__('shlex').split(self.tmux("show-option", "-gqv", "@resurrect-processes")), ['ssh', 'codex resume'])
        self.assertTrue(list(self.root.glob("tmux.conf.backup-*")))


if __name__ == "__main__":
    unittest.main()
