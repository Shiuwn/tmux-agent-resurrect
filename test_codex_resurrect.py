import importlib.util
import tempfile
from pathlib import Path
from adapters import codex, opencode
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("plugin", Path(__file__).with_name("codex-resurrect.py"))
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)
A = "11111111-1111-4111-8111-111111111111"
B = "22222222-2222-4222-8222-222222222222"


class MappingTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(plugin, "load_adapters", return_value=[codex.ADAPTER, opencode.ADAPTER])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_duplicate_names_fail_closed(self):
        self.assertIsNone(codex.choose_id({A, B}, set())[0])

    def test_open_file_disambiguates_same_name(self):
        self.assertEqual(codex.choose_id({A, B}, {B})[0], B)

    def test_wrong_directory_or_title_never_uses_file(self):
        self.assertIsNone(codex.choose_id(set(), {A})[0])

    def test_spinner_and_project_suffix(self):
        self.assertTrue(codex.names_match("⠇ 工作 | project", "工作", "/tmp/project"))
        self.assertFalse(codex.names_match("其他工作 | project", "工作", "/tmp/project"))

    def test_opencode_sidebar_wraps_and_wide_characters(self):
        screen = "正文中文" + " " * 12 + "New session -\n" + " " * 20 + "2026-11-03\n\n" + "正文" + " " * 16 + "Context\n"
        # Sidebar starts at terminal column 20, despite CJK occupying two cells.
        self.assertEqual(opencode.opencode_sidebar_title(screen.replace(" " * 12, " " * 32).replace(" " * 20, " " * 40).replace(" " * 16, " " * 36)), "Newsession-2026-11-03")
        self.assertEqual(opencode.opencode_sidebar_title("normal transcript\nno sidebar"), "")

    def test_opencode_uses_visible_title_not_latest_session(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "opencode"
            root.mkdir()
            db = sqlite3.connect(root / "opencode.db")
            db.execute("create table session(id,title,directory,time_archived)")
            db.executemany("insert into session values(?,?,?,null)", [
                ("ses_correct", "Selected session", "/tmp/project"),
                ("ses_other", "Other session", "/tmp/project"),
                ("ses_wrongcwd", "Selected session", "/tmp/other")])
            db.commit()
            screen = " " * 60 + "Selected session\n\n" + " " * 60 + "Context\n"
            with patch.dict(plugin.os.environ, {"XDG_DATA_HOME": directory}), \
                 patch.object(plugin, "run", return_value=screen):
                self.assertEqual(opencode.opencode_session("%1", "OpenCode", "/tmp/project", plugin.run)[0], "ses_correct")
                db.execute("insert into session values('ses_duplicate','Selected session','/tmp/project',null)")
                db.commit()
                self.assertIsNone(opencode.opencode_session("%1", "OpenCode", "/tmp/project", plugin.run)[0])
            db.close()

    def test_opencode_snapshot_saves_session_argument(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "snapshot"
            snapshot.write_text("pane\ts\t0\t1\t:*\t0\tOpenCode\t:/tmp\t1\topencode\t:opencode -c\n")

            def run(args):
                if args[1] == "list-panes":
                    return "s\t0\t0\t%1\t100\tOpenCode\t/tmp\n"
                if args[1] == "display-message":
                    return "OpenCode\n"
                return ""

            with patch.dict(plugin.os.environ, {"CODEX_HOME": directory}), \
                 patch.object(plugin, "processes", return_value={100: (1, "zsh"), 101: (100, "opencode")}), \
                 patch.object(opencode, "opencode_session", return_value=("ses_exact123", "opencode-sidebar-and-cwd")), \
                 patch.object(plugin, "run", side_effect=run):
                report = plugin.save(snapshot)
            self.assertEqual(snapshot.read_text().strip().split("\t")[10], ":opencode --session ses_exact123 /tmp")
            self.assertEqual(report[0]["tool"], "opencode")

    def test_snapshot_keeps_shell_and_replaces_only_codex(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = sqlite3.connect(root / "state_5.sqlite")
            db.execute("create table threads(id,name,title,cwd,archived)")
            db.execute("insert into threads values(?,?,?,?,0)", (A, "工作", "原始问题", "/tmp/project space"))
            db.commit()
            db.close()
            snapshot = root / "snapshot"
            codex = "pane\ts\t0\t1\t:*\t0\ttitle\t:/tmp/project\\ space\t1\tcodex\t:codex old prompt"
            shell = "pane\ts\t1\t0\t:\t0\tshell\t:/tmp\t1\tzsh\t:"
            snapshot.write_text(codex + "\n" + shell + "\n")

            def run(args):
                if args[1] == "list-panes":
                    return "s\t0\t0\t%1\t100\t工作 | project space\t/tmp/project space\n"
                if args[1] == "display-message":
                    return "工作 | project space\n"
                return ""

            with patch.dict(plugin.os.environ, {"CODEX_HOME": directory}), \
                 patch.object(plugin, "processes", return_value={100: (1, "zsh"), 101: (100, "/bin/codex")}), \
                 patch.object(plugin, "run", side_effect=run):
                report = plugin.save(snapshot)
            lines = snapshot.read_text().splitlines()
            self.assertEqual(lines[1], shell)
            self.assertEqual(lines[0].split("\t")[10], f":codex resume {A} -C '/tmp/project space'")
            self.assertEqual(report[0]["session_id"], A)


if __name__ == "__main__":
    unittest.main()
