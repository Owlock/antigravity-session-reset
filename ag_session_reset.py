"""Local Antigravity session reset. Python 3.10+, standard library only."""
import sys
sys.dont_write_bytecode = True

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

APPS = ("Antigravity", "Antigravity IDE")
WEB = ("Cache", "Code Cache", "Network", "Session Storage", "Local Storage")
PREFIX = "antigravityUnifiedStateSync."
COMMON = (PREFIX + "oauthToken", PREFIX + "userStatus", PREFIX + "modelCredits",
          "jetskiStateSync.agentManagerInitState")
EXTRA = ("antigravityAuthStatus", "antigravityAnalytics.clearcutBuffer",
         "antigravityAnalytics.lastUploadTime", "antigravityOnboarding", PREFIX + "onboarding")
TOKEN = "jetski-standalone-oauth-token"
PROFILE = "antigravity-browser-profile"
LOCK_HELP = ("A reset lock already exists. Check Task Manager (Details) on Windows or "
             "Activity Monitor/System Monitor for another Python run of ag_session_reset.py. "
             "If in doubt, leave the lock alone. Only after it has stopped, remove the empty "
             "~/.ag-session-reset.lock directory and retry.")


class Stop(Exception):
    """A diagnostic suitable for display without printing personal paths."""


def roots(home):
    if os.name == "nt":
        items = {"roaming": Path(os.environ["APPDATA"]), "local": Path(os.environ["LOCALAPPDATA"])}
    elif sys.platform == "darwin":
        items = {"support": home / "Library/Application Support", "cache": home / "Library/Caches"}
    elif sys.platform.startswith("linux"):
        items = {"config": Path(os.getenv("XDG_CONFIG_HOME") or home / ".config"),
                 "cache": Path(os.getenv("XDG_CACHE_HOME") or home / ".cache")}
    else:
        raise Stop("Unsupported operating system.")
    if any(not p.is_absolute() or ".." in p.parts for p in items.values()):
        raise Stop("Expected absolute local OS data roots.")
    return {label: p.resolve() for label, p in items.items()}


def capture(args):
    return subprocess.check_output(args, stderr=subprocess.DEVNULL, timeout=30)


def idle(profile):
    if os.name == "nt":
        shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        query = ("$ErrorActionPreference='Stop';"
                 "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"
                 "ConvertTo-Json -Compress -InputObject @(Get-CimInstance Win32_Process | "
                 "Select-Object Name,CommandLine)")
        rows = [(p["Name"], p["CommandLine"] or "") for p in json.loads(
            capture([str(shell), "-NoProfile", "-NonInteractive", "-Command", query]))]
    else:
        def column(name):
            data = os.fsdecode(capture(["ps", "-Aww", "-o", "pid=", "-o", name + "="]))
            result = {}
            for line in data.splitlines():
                fields = line.split(None, 1)
                if len(fields) == 2:
                    result[fields[0]] = fields[1]
            return result
        names, commands = column("comm"), column("args")
        rows = [(name, commands.get(pid, "")) for pid, name in names.items()]
    if not rows:
        raise Stop("Process inspection unavailable.")
    for raw_name, args in rows:
        display = Path(raw_name).name
        name = display.casefold().removesuffix(".exe")
        if (name.startswith("antigravity") or name == "agy"
                or re.match(r"language[_-]server(?:$|[_-])", name)
                or str(profile).casefold() in args.casefold()):
            raise Stop("".join(c for c in display if c.isprintable()))


def info(path):
    try:
        s = path.lstat()
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(s.st_mode) or getattr(s, "st_file_attributes", 0) & 1024:
        raise Stop("A selected path is a link or junction. Review it manually.")
    return s


def expect(path, directory):
    s = info(path)
    if s is None:
        return False
    predicate = stat.S_ISDIR if directory else stat.S_ISREG
    if not predicate(s.st_mode) or os.path.ismount(path):
        raise Stop("Unexpected file type or mount in a selected location.")
    return True


def cold(db):
    if any(os.path.lexists(str(db) + suffix) for suffix in ("-wal", "-shm", "-journal")):
        raise Stop("SQLite companion file present. Close cleanly; never remove a companion file.")


def database(path, write=False):
    uri = path.as_uri() + ("?mode=rw" if write else "?mode=ro&immutable=1")
    c = sqlite3.connect(uri, uri=True, isolation_level=None, timeout=2)
    c.execute("PRAGMA temp_store=MEMORY")
    c.execute("PRAGMA trusted_schema=OFF")
    return c


def integrity(c):
    if c.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise Stop("SQLite integrity check failed.")


def edit(c, keys):
    marks = ",".join("?" for _ in keys)
    test = "key COLLATE BINARY IN (" + marks + ")"
    select = "SELECT key,typeof(value),value FROM ItemTable"
    order = " ORDER BY key COLLATE BINARY"
    c.execute("BEGIN IMMEDIATE")
    try:
        if c.execute("SELECT 1 FROM sqlite_master WHERE type='trigger' "
                     "AND lower(tbl_name)='itemtable'").fetchone():
            raise Stop("Unexpected SQLite triggers.")
        kept = c.execute(select + " WHERE NOT (" + test + ")" + order, keys).fetchall()
        count = c.execute("DELETE FROM ItemTable WHERE " + test, keys).rowcount
        if count != len(keys) or c.execute(select + order).fetchall() != kept:
            raise Stop("SQLite rows differ from the approved change.")
        integrity(c)
        c.commit()
    except BaseException:
        c.rollback()
        raise


@dataclass
class Plan:
    files: dict = field(default_factory=dict)   # strict backup: databases, settings, token
    trees: dict = field(default_factory=dict)   # web stores selected for removal
    edits: dict = field(default_factory=dict)
    token: Path | None = None


def inventory(home, bases, browser):
    plan = Plan()
    for tag, base in bases.items():
        for app in APPS:
            root = base / app
            if not expect(root, True):
                continue
            user = root / "User"
            if expect(user, True):
                def add(path):
                    if expect(path, False):
                        if path.name == "state.vscdb":
                            cold(path)
                        plan.files.setdefault(path, Path(tag, app) / path.relative_to(root))
                        return True
                    return False

                add(user / "settings.json")
                global_dir = user / "globalStorage"
                db = global_dir / "state.vscdb"
                if expect(global_dir, True) and add(db):
                    if db.stat().st_nlink != 1:
                        raise Stop("Main database has more than one hard link.")
                    with closing(database(db)) as c:
                        integrity(c)
                        names = {row[0] for row in c.execute("SELECT key FROM ItemTable")}
                    hits = tuple(k for k in COMMON + (EXTRA if app == APPS[0] else ()) if k in names)
                    if hits:
                        plan.edits[db] = hits
                    for k in hits:
                        print(tag, app, k)
                spaces = user / "workspaceStorage"
                if expect(spaces, True):
                    for entry in spaces.iterdir():
                        s = entry.lstat()
                        if (stat.S_ISLNK(s.st_mode) or getattr(s, "st_file_attributes", 0) & 1024):
                            print("Skipped a linked workspace directory.")
                        elif stat.S_ISDIR(s.st_mode) and expect(entry, True):
                            add(entry / "state.vscdb")
            for name in WEB:
                p = root / name
                if expect(p, True) and p not in plan.trees:
                    plan.trees[p] = Path(tag, app, name)
                    print(tag, app, name)

    gem = home / ".gemini"
    if expect(gem, True):
        p = gem / TOKEN
        if expect(p, False):
            plan.token = p
            plan.files[p] = Path("gemini", TOKEN)
            print("~/.gemini/" + TOKEN)
        if browser and expect(gem / PROFILE, True):
            plan.trees[gem / PROFILE] = Path("gemini", PROFILE)
            print("~/.gemini/" + PROFILE)
        if os.path.lexists(gem / "antigravity-acp"):
            print("Manual review: ~/.gemini/antigravity-acp/ (left in place).")
    return plan


def canonical(path, strict):
    return os.path.normcase(os.path.normpath(str(path.resolve(strict=strict))))


def approved_targets(home, bases, browser, plan):
    names = [base / app / name for base in bases.values() for app in APPS for name in WEB]
    names.append(home / ".gemini" / TOKEN)
    if browser:
        names.append(home / ".gemini" / PROFILE)
    candidates = list(plan.trees) + ([plan.token] if plan.token else [])
    # Canonicalize both sides before backup or the first SQLite write.
    allowed = {canonical(p, False) for p in names}
    approved = {}
    for p in candidates:
        key = canonical(p, True)
        if key not in allowed or os.path.ismount(p):
            raise Stop("Removal target outside the approved locations.")
        approved[p] = key
    if len(set(approved.values())) != len(approved):
        raise Stop("Two selected targets resolve to one location.")
    return approved


def stamp(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def tree_state(root):
    """Names, types and metadata only. Never read payloads here."""
    if not expect(root, True):
        raise Stop("A web directory disappeared.")
    result = {Path("."): stamp(root.stat())}
    pending = [root]
    while pending:
        parent = pending.pop()
        for p in parent.iterdir():
            s = info(p)
            if s is None or os.path.ismount(p):
                raise Stop("Tree changed or contains a mount.")
            if stat.S_ISDIR(s.st_mode):
                pending.append(p)
            elif not stat.S_ISREG(s.st_mode):
                raise Stop("Unsupported object in a selected web directory.")
            elif s.st_nlink > 1 and getattr(s, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_READONLY:
                raise Stop("Read-only cache file has multiple hard links.")
            result[p.relative_to(root)] = stamp(s)
    return result


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as reader:
        for block in iter(lambda: reader.read(1024 * 1024), b""):
            h.update(block)
    return path.stat().st_size, h.digest()


def copy_verified(src, dst):
    """Hash the source during copying, then read and hash the destination once."""
    h, size = hashlib.sha256(), 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open("rb") as reader, dst.open("xb") as writer:
        for block in iter(lambda: reader.read(1024 * 1024), b""):
            writer.write(block)
            h.update(block)
            size += len(block)
    expected = (size, h.digest())
    if digest(dst) != expected:
        raise Stop("Backup content mismatch.")
    shutil.copystat(src, dst)
    return expected


def copy_tree(src, dst):
    before = tree_state(src)
    dst.mkdir(parents=True)
    for rel, attr in before.items():
        if rel == Path("."):
            continue
        if stat.S_ISDIR(attr[2]):
            (dst / rel).mkdir(parents=True, exist_ok=True)
        else:
            copy_verified(src / rel, dst / rel)
    if tree_state(src) != before:
        raise Stop("Web directory changed during backup.")
    return before


def remove_tree(root):
    if not expect(root, True):
        raise Stop("Selected directory disappeared.")
    anchor = root.resolve(strict=True)

    def onexc(func, name, exc):
        p = Path(name)
        if (os.name != "nt" or not isinstance(exc, PermissionError)
                or func not in (os.unlink, os.remove, os.rmdir)
                or not p.resolve(strict=True).is_relative_to(anchor)):
            raise exc
        s = info(p)
        if (s is None or not getattr(s, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_READONLY
                or (stat.S_ISREG(s.st_mode) and s.st_nlink > 1)):
            raise exc
        p.chmod(s.st_mode | stat.S_IWRITE)
        func(name)

    if sys.version_info >= (3, 12):
        shutil.rmtree(root, onexc=onexc)
    else:
        shutil.rmtree(root, onerror=lambda func, path, err: onexc(func, path, err[1]))


def vault(apply):
    if os.name == "nt":
        if not apply:
            print("Vault candidate: gemini:antigravity")
            return
        api = ctypes.WinDLL("Advapi32.dll", use_last_error=True).CredDeleteW
        api.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32]
        api.restype = ctypes.c_int
        if api("gemini:antigravity", 1, 0):
            print("Windows credential removed.")
        elif ctypes.get_last_error() == 1168:
            print("Windows credential absent.")
        else:
            raise Stop("Check: cmdkey /list:gemini:antigravity\n"
                       "Only for the confirmed old entry: cmdkey /delete:gemini:antigravity")
    elif sys.platform == "darwin":
        print('Manual: open -a "Keychain Access". Verify unique service, account and keychain.')
        print('security delete-generic-password -s "${AG_SERVICE:?}" -a "${AG_ACCOUNT:?}" "${AG_KEYCHAIN:?}"')
    else:
        print("Manual: seahorse. Verify two attribute pairs uniquely identify one old item.")
        print('secret-tool clear "${AG_KEY1:?}" "${AG_VALUE1:?}" "${AG_KEY2:?}" "${AG_VALUE2:?}"')


@contextmanager
def run_lock(path):
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        raise Stop(LOCK_HELP) from None
    try:
        yield
    finally:
        path.rmdir()


def apply(plan, approved, backup_parent, profile):
    backup_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    name = "antigravity-backup-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    dest = backup_parent / name
    dest.mkdir(mode=0o700)
    print("Backup:", name, flush=True)
    hashes, snapshots = {}, {}
    for p, rel in plan.files.items():
        hashes[p] = copy_verified(p, dest / rel)
        if p.name in ("state.vscdb", "settings.json") and not hashes[p][0]:
            raise Stop("Empty database or settings file.")
    for p, rel in plan.trees.items():
        snapshots[p] = copy_tree(p, dest / rel)
    idle(profile)
    for p, rel in plan.files.items():
        if p.name == "state.vscdb":
            cold(p)
        if digest(p) != hashes[p] or digest(dest / rel) != hashes[p]:
            raise Stop("Strict source or backup verification failed.")
    for p, expected in snapshots.items():
        if tree_state(p) != expected:
            raise Stop("Web directory changed before editing.")
    print("Backup verified.", flush=True)

    for p, keys in plan.edits.items():
        idle(profile)
        cold(p)
        if digest(p) != hashes[p]:
            raise Stop("Main database changed after backup.")
        with closing(database(p, True)) as c:
            edit(c, keys)
    for p, key in approved.items():
        idle(profile)
        if canonical(p, True) != key or os.path.ismount(p):
            raise Stop("A validated removal path changed.")
        if p == plan.token:
            if not expect(p, False) or digest(p) != hashes[p]:
                raise Stop("Token changed after backup.")
            p.unlink()
        else:
            if tree_state(p) != snapshots[p]:
                raise Stop("Web directory changed after backup.")
            remove_tree(p)
        if os.path.lexists(p):
            raise Stop("Selected target still present.")
    for p, keys in plan.edits.items():
        cold(p)
        with closing(database(p)) as c:
            integrity(c)
            if set(keys).intersection(row[0] for row in c.execute("SELECT key FROM ItemTable")):
                raise Stop("Target rows still present.")
    for p in plan.files.keys() - plan.edits.keys() - {plan.token}:
        if digest(p) != hashes[p]:
            raise Stop("Protected settings or database changed.")
    idle(profile)
    vault(True)
    print("Local checks complete. Follow the browser steps.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--include-browser-profile", action="store_true")
    parser.add_argument("--backup-dir", type=Path)
    opts = parser.parse_args(argv)
    home = Path.home().resolve(strict=True)
    lock = home / ".ag-session-reset.lock"
    if os.path.lexists(lock):
        raise Stop(LOCK_HELP)
    profile = home / ".gemini" / PROFILE
    idle(profile)
    bases = roots(home)

    def inspect():
        plan = inventory(home, bases, opts.include_browser_profile)
        return plan, approved_targets(home, bases, opts.include_browser_profile, plan)

    if not opts.apply:
        inspect()
        vault(False)
        print("Dry run complete. No backup or changes.")
        return

    parent = (opts.backup_dir or home / ".ag-session-backups").expanduser().resolve()
    protected = [lock, home / ".gemini", home / ".antigravity", home / ".antigravity-ide"]
    protected.extend(base / app for base in bases.values() for app in APPS)
    if any(parent.is_relative_to(p) for p in protected):
        raise Stop("Choose a private backup directory outside application data.")
    if any((p / ".git").exists() for p in (parent, *parent.parents)):
        raise Stop("Choose a backup directory outside Git.")
    with run_lock(lock):
        idle(profile)
        plan, approved = inspect()
        apply(plan, approved, parent, profile)


if __name__ == "__main__":
    try:
        main()
    except Stop as error:
        sys.exit(str(error))
    except (OSError, RuntimeError, KeyError, ValueError, sqlite3.Error, subprocess.SubprocessError) as error:
        sys.exit(type(error).__name__ + ": stopped. Keep any backup and consult the recovery guide.")
