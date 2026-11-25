"""Run with python -B -m unittest discover -s tests -v. No real app or vault."""
import contextlib
import hashlib
import io
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import ag_session_reset as ag


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def make_db(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.closing(sqlite3.connect(path)) as db:
        db.execute("CREATE TABLE ItemTable(key TEXT PRIMARY KEY,value BLOB)")
        db.executemany("INSERT INTO ItemTable VALUES(?,?)", values.items())
        db.commit()


def rows(path):
    with contextlib.closing(sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)) as db:
        assert db.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        return dict(db.execute("SELECT key,value FROM ItemTable"))


def snapshot(root):
    result = {}
    for p in root.rglob("*"):
        result[p.relative_to(root)] = None if p.is_dir() else (
            hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns, p.stat().st_mode)
    return result


class ResetTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="ag-reset-test-")
        self.root = Path(temp.name).resolve()
        self.addCleanup(lambda: self.assertFalse(self.root.exists()))
        self.addCleanup(temp.cleanup)
        self.home = self.root / "home"
        self.home.mkdir()
        self.env = {"HOME": str(self.home), "USERPROFILE": str(self.home),
                    "APPDATA": str(self.home / "roaming"), "LOCALAPPDATA": str(self.home / "local"),
                    "XDG_CONFIG_HOME": str(self.home / "config"), "XDG_CACHE_HOME": str(self.home / "cache")}
        self.enter(patch.dict(os.environ, self.env))
        self.assertEqual(Path.home().resolve(), self.home)
        self.bases = ag.roots(self.home)
        self.assertTrue(all(p.is_relative_to(self.home) for p in self.bases.values()))
        self.tag, self.base = next(iter(self.bases.items()))
        self.gem = self.home / ".gemini"
        self.profile = self.gem / ag.PROFILE
        self.token = self.gem / ag.TOKEN
        self.backup = self.root / "backup-parent"
        self.protected, self.main, self.web = {}, {}, []
        self.enter(patch.object(ag, "idle", side_effect=lambda p: self.assertEqual(p, self.profile)))
        self.vault = self.enter(patch.object(ag, "vault", autospec=True))
        self.enter(patch.object(subprocess, "check_output", side_effect=AssertionError("Native access")))
        self.enter(patch.object(ag.ctypes, "WinDLL", create=True, side_effect=AssertionError("Native vault")))
        self.enter(contextlib.redirect_stdout(io.StringIO()))
        for app in ag.APPS:
            appdir = self.base / app
            db = appdir / "User/globalStorage/state.vscdb"
            keys = (*ag.COMMON, *ag.EXTRA, ag.PREFIX + "trajectorySummaries",
                    "google.antigravity", "personal.preference", ag.PREFIX + "oauthTokenExtra",
                    (ag.PREFIX + "oauthToken").upper())
            data = {k: b"synthetic-" + bytes([n]) for n, k in enumerate(keys)}
            make_db(db, data)
            self.main[db] = data
            workspace = appdir / "User/workspaceStorage/example/state.vscdb"
            make_db(workspace, data)
            self.protected[workspace] = workspace.read_bytes()
            for rel in ("User/settings.json", "User/keybindings.json",
                        "User/globalStorage/unrelated/deeper/state.vscdb",
                        "User/workspaceStorage/example/nested/state.vscdb"):
                self.protect(appdir / rel)
            for name in ag.WEB:
                folder = appdir / name
                put(folder / "nested/payload", b"synthetic cache")
                (folder / "empty").mkdir()
                self.web.append(folder)
        for name in (".antigravity", ".antigravity-ide"):
            self.protect(self.home / name / "extensions/example/data")
        for app in ("antigravity", "antigravity-ide", "antigravity-cli"):
            for name in ("brain", "conversations"):
                self.protect(self.gem / app / name / "example")
        self.protect(self.gem / "antigravity-backup/example")
        self.protect(self.gem / "antigravity-acp/example")
        put(self.profile / "nested/payload", b"synthetic browser")
        put(self.token, b"synthetic token")
        self.web.append(self.profile)
        if os.name == "nt":
            (self.web[0] / "nested/payload").chmod(stat.S_IREAD)

    def enter(self, cm):
        value = cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)
        return value

    def protect(self, path):
        put(path, b"synthetic protected")
        self.protected[path] = path.read_bytes()

    def test_01_dry_run(self):
        before = snapshot(self.root)
        ag.main([])
        ag.main(["--dry-run", "--include-browser-profile", "--backup-dir", str(self.backup)])
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse(self.backup.exists())
        self.assertEqual(self.vault.call_args_list, [unittest.mock.call(False)] * 2)

    def test_02_apply_with_browser(self):
        reads = {}
        original_open = Path.open
        original_iterdir = Path.iterdir

        def tracked(path, mode="r", *args, **kwargs):
            if mode == "rb":
                reads[path] = reads.get(path, 0) + 1
            return original_open(path, mode, *args, **kwargs)

        def directed(path):
            if path.name in ("User", "globalStorage") or path.name == "unrelated":
                raise AssertionError("Unexpected recursive app-data scan")
            return original_iterdir(path)

        with patch.object(Path, "open", tracked), patch.object(Path, "iterdir", directed):
            ag.main(["--apply", "--include-browser-profile", "--backup-dir", str(self.backup)])
        self.vault.assert_called_once_with(True)
        backups = list(self.backup.iterdir())
        self.assertEqual(len(backups), 1)
        dest = backups[0]
        for db, before in self.main.items():
            relative = db.relative_to(self.base)
            app = relative.parts[0]
            expected = set(ag.COMMON) | (set(ag.EXTRA) if app == ag.APPS[0] else set())
            self.assertEqual(rows(db), {k: v for k, v in before.items() if k not in expected})
            self.assertEqual(rows(dest / self.tag / relative), before)
            self.assertGreaterEqual(reads[db], 2)
        self.assertFalse(self.token.exists())
        self.assertEqual((dest / "gemini" / ag.TOKEN).read_bytes(), b"synthetic token")
        for p, val in self.protected.items():
            self.assertEqual(p.read_bytes(), val)
            if p.is_relative_to(self.base):
                copy = dest / self.tag / p.relative_to(self.base)
                if p.parent.name == "User" and p.name == "settings.json" or p.parent.name == "example":
                    self.assertEqual(copy.read_bytes(), val)
                    self.assertGreaterEqual(reads[copy], 2)
                else:
                    self.assertFalse(copy.exists())
        for p in self.web:
            self.assertFalse(p.exists())
            copy = dest / ("gemini" if p == self.profile else self.tag) / (
                Path(ag.PROFILE) if p == self.profile else p.relative_to(self.base))
            self.assertEqual(reads[p / "nested/payload"], 1)
            self.assertEqual(reads[copy / "nested/payload"], 1)
            self.assertIn((copy / "nested/payload").read_bytes(), (b"synthetic browser", b"synthetic cache"))
            if p != self.profile:
                self.assertTrue((copy / "empty").is_dir())
        self.assertFalse((self.home / ".ag-session-reset.lock").exists())

    def test_lock_and_target_preflight(self):
        lock = self.home / ".ag-session-reset.lock"
        lock.mkdir()
        with self.assertRaisesRegex(ag.Stop, "another Python run"):
            ag.main(["--apply"])
        self.assertTrue(lock.is_dir())
        lock.rmdir()
        alias = self.web[0] / "nested" / ".."
        self.assertIn(alias, ag.approved_targets(self.home, self.bases, False, ag.Plan(trees={alias: None})))
        with self.assertRaises(ag.Stop):
            ag.approved_targets(self.home, self.bases, False, ag.Plan(trees={self.home: None}))
        before = snapshot(self.root)
        with patch.object(ag, "approved_targets", side_effect=ag.Stop("preflight")):
            with self.assertRaisesRegex(ag.Stop, "preflight"):
                ag.main(["--apply", "--backup-dir", str(self.backup)])
        self.assertEqual(snapshot(self.root), before)
        self.vault.assert_not_called()

    def test_legacy_optional_and_profile_opt_in(self):
        db = next(iter(self.main))
        with contextlib.closing(sqlite3.connect(db)) as c:
            c.execute("DELETE FROM ItemTable WHERE key=?", (ag.COMMON[-1],))
            c.commit()
        ag.main(["--apply", "--backup-dir", str(self.backup)])
        self.assertTrue((self.profile / "nested/payload").is_file())
        self.assertNotIn(ag.COMMON[-1], rows(db))


class ProcessNameTest(unittest.TestCase):
    def test_only_executable_name(self):
        if os.name == "nt":
            fake = [b'[{"Name":"Antigravity.exe","CommandLine":"private-arguments"}]']
            name = "Antigravity.exe"
        else:
            fake = [b"12 /example/Antigravity\n", b"12 /example/Antigravity private-arguments\n"]
            name = "Antigravity"
        with patch.object(ag, "capture", side_effect=fake):
            with self.assertRaises(ag.Stop) as caught:
                ag.idle(Path("/fictional/profile"))
        self.assertEqual(str(caught.exception), name)


if __name__ == "__main__":
    unittest.main()
