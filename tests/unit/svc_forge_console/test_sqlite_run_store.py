"""Approved local persistence tests; synthetic tenants only."""

import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from saena_domain.events import generate_uuid7
from saena_forge_console.local_config import create_local_app, load_configuration, main
from saena_forge_console.run_store import RunNotFoundError, RunTenantIsolationError
from saena_forge_console.sqlite_run_store import LocalStoreError, SQLiteRunStore
from saena_schemas.context.run_context_lifecycle_v1 import RuncontextLifecycle

from svc_forge_console.conftest import run_create_body
from svc_forge_console.test_local_config import config  # noqa: F401
from svc_forge_console.test_verified_auth import key, token  # noqa: F401


@pytest.fixture
def store(tmp_path):
    root = tmp_path.resolve()
    root.chmod(0o700)
    s = SQLiteRunStore(str(root), "acme-corp")
    s.initialize()
    return s


def run(tenant="acme-corp", **extra):
    return RuncontextLifecycle.model_validate(
        {
            "run_id": generate_uuid7(),
            "tenant_id": tenant,
            **run_create_body(),
            **extra,
        }
    )


def test_restart_and_update(store):
    r = run()
    store.put("acme-corp", r)
    new = SQLiteRunStore(store.directory, "acme-corp")
    assert new.get("acme-corp", r.run_id.root) == r
    r2 = RuncontextLifecycle.model_validate({**r.model_dump(mode="json"), "base_commit": "b" * 40})
    new.put("acme-corp", r2)
    assert store.get("acme-corp", r.run_id.root).base_commit == r2.base_commit
    assert new.check() == "validated"


def test_missing(store):
    with pytest.raises(RunNotFoundError):
        store.get("acme-corp", generate_uuid7())


def test_tenant_boundaries(store):
    r = run()
    store.put("acme-corp", r)
    with pytest.raises(RunTenantIsolationError):
        store.get("other-corp", r.run_id.root)
    with pytest.raises(RunTenantIsolationError):
        store.put("other-corp", r)
    with pytest.raises(RunTenantIsolationError):
        store.put("acme-corp", run("other-corp"))
    with pytest.raises(LocalStoreError):
        SQLiteRunStore(store.directory, "other-corp").check()


def test_parallel_saves(store):
    rows = [run() for _ in range(12)]

    def save(r):
        return SQLiteRunStore(store.directory, "acme-corp").put("acme-corp", r)

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert len(list(pool.map(save, rows))) == 12
    assert all(store.get("acme-corp", r.run_id.root) == r for r in rows)


def test_check_no_write(tmp_path):
    root = tmp_path.resolve()
    root.chmod(0o700)
    store = SQLiteRunStore(str(root), "acme-corp")
    assert store.check() == "not_created"
    assert list(root.iterdir()) == []
    store.initialize()
    db = root / "runs.sqlite3"
    before = db.read_bytes(), db.stat().st_mtime_ns, set(root.iterdir())
    assert store.check() == "validated"
    assert (db.read_bytes(), db.stat().st_mtime_ns, set(root.iterdir())) == before


@pytest.mark.parametrize(
    "case",
    [
        "symlink",
        "hardlink",
        "mode",
        "fifo",
        "garbage",
        "wal",
        "shm",
        "journal-link",
        "directory-mode",
    ],
)
def test_unsafe_database(store, case):
    from pathlib import Path

    root = Path(store.directory)
    db = root / "runs.sqlite3"
    if case == "symlink":
        db.rename(root / "real")
        db.symlink_to(root / "real")
    elif case == "hardlink":
        os.link(db, root / "other")
    elif case == "mode":
        db.chmod(0o644)
    elif case == "fifo":
        db.unlink()
        os.mkfifo(db)
    elif case == "garbage":
        db.write_bytes(b"not a sqlite database")
    elif case in {"wal", "shm"}:
        (root / ("runs.sqlite3-" + case)).write_bytes(b"unexpected")
    elif case == "journal-link":
        (root / "runs.sqlite3-journal").symlink_to(db)
    elif case == "directory-mode":
        root.chmod(0o755)
    with pytest.raises(LocalStoreError):
        store.check()


@pytest.mark.parametrize(
    "sql",
    [
        "PRAGMA user_version=2",
        "PRAGMA application_id=0",
        "UPDATE meta SET tenant='other-corp'",
        "CREATE TABLE unexpected(value TEXT)",
        "CREATE TRIGGER bad AFTER INSERT ON runs BEGIN DELETE FROM runs; END",
        "UPDATE runs SET payload='{}'",
        "UPDATE runs SET tenant='other-corp'",
    ],
)
def test_corruption_rejected(store, sql):
    from pathlib import Path

    store.put("acme-corp", run())
    with sqlite3.connect(str(Path(store.directory) / "runs.sqlite3")) as c:
        c.execute(sql)
    with pytest.raises(LocalStoreError):
        store.check()


def test_large_or_secret_payload_not_saved(store):
    for value in ["x" * (256 * 1024), "sk-" + "a" * 25]:
        r = run(extra_value=value)
        with pytest.raises(LocalStoreError):
            store.put("acme-corp", r)
        with pytest.raises(RunNotFoundError):
            store.get("acme-corp", r.run_id.root)


def test_v2_factory_restart(config, key, capsys):  # noqa: F811
    path, value, save = config
    directory = path.parent / "private-db"
    directory.mkdir(mode=0o700)
    value.update(version=2, run_store={"kind": "sqlite", "directory": str(directory)})
    save()
    assert main(["--config", str(path), "--check"]) == 0
    assert json.loads(capsys.readouterr().out)["run_store"] == "not_created"
    assert list(directory.iterdir()) == []
    auth = {"Authorization": "Bearer " + token(key)}
    first = TestClient(create_local_app())
    r = first.post("/v1/runs", headers=auth, json=run_create_body())
    assert r.status_code == 201
    second = TestClient(create_local_app())
    loaded = second.get("/v1/runs/" + r.json()["run_id"], headers=auth)
    assert loaded.status_code == 200
    assert loaded.json() == r.json()
    assert load_configuration(str(path)).check()["run_store"] == "validated"


def test_fresh_process_reads_saved_run(store):
    import subprocess
    import sys

    r = run()
    store.put("acme-corp", r)
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            "import sys; from saena_forge_console.sqlite_run_store import SQLiteRunStore; "
            's=SQLiteRunStore(sys.argv[1],"acme-corp"); '
            'print(s.get("acme-corp",sys.argv[2]).state.value)',
            store.directory,
            r.run_id.root,
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "INTAKE"


def test_aborted_transaction_preserves_committed_row(store):
    import subprocess
    import sys
    from pathlib import Path

    r = run()
    store.put("acme-corp", r)
    db = str(Path(store.directory) / "runs.sqlite3")
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            "import os,sqlite3,sys; c=sqlite3.connect(sys.argv[1]); "
            'c.execute("BEGIN IMMEDIATE"); c.execute("DELETE FROM runs"); os._exit(7)',
            db,
        ],
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 7
    reopened = SQLiteRunStore(store.directory, "acme-corp")
    reopened.initialize()
    assert reopened.get("acme-corp", r.run_id.root) == r


def test_database_lock_fails_without_overwrite(store):
    from pathlib import Path

    r = run()
    with sqlite3.connect(str(Path(store.directory) / "runs.sqlite3")) as blocker:
        blocker.execute("BEGIN IMMEDIATE")
        with pytest.raises(LocalStoreError):
            store.put("acme-corp", r)
    with pytest.raises(RunNotFoundError):
        store.get("acme-corp", r.run_id.root)


def test_no_sql_injection(store):
    with pytest.raises(RunNotFoundError):
        store.get("acme-corp", "' OR 1=1 --")
    assert store.check() == "validated"


@pytest.mark.parametrize("case", ["wal", "journal-link", "directory-link"])
def test_precheck_rejects_unsafe_uninitialized(tmp_path, case):
    root = tmp_path.resolve()
    root.chmod(0o700)
    target = root
    if case == "wal":
        (root / "runs.sqlite3-wal").write_text("bad")
    elif case == "journal-link":
        (root / "runs.sqlite3-journal").symlink_to(root / "missing")
    else:
        target = root / "linked"
        target.symlink_to(root, target_is_directory=True)
    with pytest.raises(LocalStoreError):
        SQLiteRunStore(str(target), "acme-corp").check()
    assert not (root / "runs.sqlite3").exists()


@pytest.mark.parametrize(
    "setting",
    [
        None,
        {},
        {"kind": "memory", "directory": "/tmp"},
        {"kind": "sqlite", "directory": "relative"},
        {"kind": "sqlite", "directory": "/tmp", "extra": True},
    ],
)
def test_v2_invalid_setting(config, setting):  # noqa: F811
    from saena_forge_console.local_config import ConfigurationError

    _, value, save = config
    value.update(version=2, run_store=setting)
    with pytest.raises(ConfigurationError):
        load_configuration(save())


def test_same_name_trigger_not_hidden(store):
    from pathlib import Path

    with sqlite3.connect(str(Path(store.directory) / "runs.sqlite3")) as c:
        c.execute("CREATE TRIGGER meta AFTER INSERT ON runs BEGIN DELETE FROM runs; END")
        c.execute("PRAGMA writable_schema=ON")
        c.execute("UPDATE sqlite_master SET rowid=10 WHERE type='table' AND name='meta'")
        c.execute(
            "UPDATE sqlite_master SET rowid=11 "
            "WHERE type='index' AND name='sqlite_autoindex_meta_1'"
        )
        c.execute("PRAGMA writable_schema=OFF")
    from saena_forge_console.sqlite_run_store import SCHEMA

    with sqlite3.connect(str(Path(store.directory) / "runs.sqlite3")) as reopened:
        reopened.execute("PRAGMA trusted_schema=OFF")
        assert (
            dict(reopened.execute("SELECT name,sql FROM sqlite_master WHERE sql IS NOT NULL"))
            == SCHEMA
        )
    with pytest.raises(LocalStoreError):
        store.check()
    with pytest.raises(LocalStoreError):
        store.put("acme-corp", run())


def test_orphan_journal_rejected_without_creation(tmp_path):
    root = tmp_path.resolve()
    root.chmod(0o700)
    journal = root / "runs.sqlite3-journal"
    journal.write_bytes(b"orphan")
    journal.chmod(0o600)
    s = SQLiteRunStore(str(root), "acme-corp")
    with pytest.raises(LocalStoreError):
        s.check()
    with pytest.raises(LocalStoreError):
        s.initialize()
    assert not (root / "runs.sqlite3").exists()
