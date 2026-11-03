import importlib.util
import os
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import patch
from adapter_api import Adapter, Context, Resolution
from adapter_registry import ROOT, load_adapters

spec = importlib.util.spec_from_file_location('save_entry', ROOT / 'codex-resurrect.py')
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

CUSTOM = '''from adapter_api import Adapter, Resolution
def resolve(ctx):
    return Resolution("demo_123", "test-current-session")
ADAPTER = Adapter("demo", ("demo",), r"demo_[0-9]+",
                  ("demo", "--resume", "{session_id}", "-C", "{cwd}"), resolve)
'''


class AdapterTests(unittest.TestCase):
    def test_default_adapters(self):
        self.assertEqual([a.name for a in load_adapters([ROOT / 'adapters'])], ['codex', 'opencode'])

    def test_metadata_rejects_shell_prefix_and_embedded_placeholder(self):
        for command in [('demo;bad', '{session_id}'), ('demo', '--id={session_id}')]:
            with self.assertRaises(ValueError):
                Adapter('demo', ('demo',), r'.+', command, lambda ctx: None).validate()

    def test_duplicate_names_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p / 'one.py').write_text(CUSTOM)
            (p / 'two.py').write_text(CUSTOM)
            with self.assertRaisesRegex(ValueError, 'duplicate adapter name'):
                load_adapters([p])

    def test_add_file_then_save_without_core_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)
            custom = config / 'tmux-agent-resurrect/adapters'
            custom.mkdir(parents=True)
            (custom / 'demo.py').write_text(CUSTOM)
            snapshot = config / 'snapshot'
            row = 'pane\ts\t0\t1\t:*\t0\ttitle\t:/tmp\t1\tdemo\t:demo old prompt\n'
            snapshot.write_text(row)
            cwd = '/tmp/project with spaces; echo never-execute'

            def run(args):
                if args[1] == 'list-panes':
                    return 's\t0\t0\t%1\t100\tCurrent\t' + cwd + '\n'
                if args[1] == 'display-message':
                    return 'Current\n'
                return ''

            with patch.dict(os.environ, {'XDG_CONFIG_HOME': directory, 'AGENT_RESURRECT_ADAPTER_DIR': ''}), \
                 patch.object(core, 'processes', return_value={100: (1, 'sh'), 101: (100, 'demo')}), \
                 patch.object(core, 'run', side_effect=run):
                adapters = load_adapters()
                self.assertEqual([a.name for a in adapters], ['codex', 'opencode', 'demo'])
                self.assertEqual(adapters[-1].restore_prefix, 'demo --resume')
                report = core.save(snapshot)
                command = snapshot.read_text().strip().split('\t')[10][1:]
                self.assertEqual(shlex.split(command), ['demo', '--resume', 'demo_123', '-C', cwd])
                self.assertEqual(report[0]['tool'], 'demo')
                # A broken resolver clears its pane's command, and still saves.
                (custom / 'demo.py').write_text(CUSTOM.replace('return Resolution("demo_123", "test-current-session")', 'raise RuntimeError("broken")'))
                snapshot.write_text(row)
                report = core.save(snapshot)
                self.assertIsNone(report[0]['session_id'])
                self.assertEqual(snapshot.read_text().strip().split('\t')[10], ':')

    def test_invalid_id_is_rejected(self):
        adapter = Adapter('demo', ('demo',), r'demo_[0-9]+', ('demo', '--resume', '{session_id}'), lambda ctx: None)
        with self.assertRaises(ValueError):
            adapter.command('wrong-id; shell', '/tmp')


if __name__ == '__main__':
    unittest.main()
