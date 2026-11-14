"""Single-tenant local SQLite run metadata. No shared schema or remote service."""

from __future__ import annotations

import os
import sqlite3
import stat
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

from saena_domain.identity.tenant import TENANT_ID_PATTERN
from saena_schemas.context.run_context_lifecycle_v1 import RuncontextLifecycle

from saena_forge_console.report_store import _json, _trusted_dir
from saena_forge_console.run_store import RunNotFoundError, RunStoreError, RunTenantIsolationError

APP_ID = 1396786510
DB_LIMIT = 64 * 1024 * 1024
PAYLOAD_LIMIT = 256 * 1024
TOTAL_LIMIT = 16 * 1024 * 1024
ROW_LIMIT = 10000
SCHEMA = {
    "meta": "CREATE TABLE meta (tenant TEXT PRIMARY KEY NOT NULL)",
    "runs": (
        "CREATE TABLE runs (run_id TEXT PRIMARY KEY NOT NULL, "
        "tenant TEXT NOT NULL, payload TEXT NOT NULL)"
    ),
}


class LocalStoreError(RunStoreError):
    """Sanitized persistence failure."""

    def __init__(self):
        super().__init__("local run store unavailable or invalid")


def _directory(path):
    p = Path(path)
    if not p.is_absolute() or str(p) != path or any(x in {".", ".."} for x in p.parts):
        raise ValueError("canonical private directory required")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in p.parts[1:]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
            _trusted_dir(fd)
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError("private owned directory required")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _regular(fd, name, optional=False):
    try:
        target = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    except FileNotFoundError:
        if optional:
            return None
        raise
    try:
        info = os.fstat(target)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size > DB_LIMIT
        ):
            raise ValueError("unsafe database file")
        return info.st_dev, info.st_ino
    finally:
        os.close(target)


def _decode(tenant, run_id, payload):
    if not isinstance(payload, str) or len(payload.encode("utf-8")) > PAYLOAD_LIMIT:
        raise ValueError("payload limit")
    data = _json(payload.encode("utf-8"))
    run = RuncontextLifecycle.model_validate(data)
    if run.tenant_id.root != tenant or run.run_id.root != run_id:
        raise ValueError("row binding mismatch")
    return run


class SQLiteRunStore:
    def __init__(self, directory: str, tenant_id: str):
        if not isinstance(tenant_id, str) or not TENANT_ID_PATTERN.fullmatch(tenant_id):
            raise LocalStoreError()
        self.directory = directory
        self.tenant_id = tenant_id

    @contextmanager
    def _connection(self, *, write=False, create=False):
        fd = None
        connection = None
        created = False
        try:
            fd = _directory(self.directory)
            # No WAL mode: avoid unexpected shared-memory side effects.
            for sidecar in ("runs.sqlite3-wal", "runs.sqlite3-shm"):
                try:
                    os.stat(sidecar, dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                raise ValueError("unsupported WAL sidecar")
            journal = _regular(fd, "runs.sqlite3-journal", optional=True)
            identity = _regular(fd, "runs.sqlite3", optional=True)
            if identity is None:
                if journal is not None:
                    raise ValueError("orphan journal")
                if not create:
                    raise FileNotFoundError("store missing")
                target = os.open(
                    "runs.sqlite3",
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=fd,
                )
                os.close(target)
                created = True
                identity = _regular(fd, "runs.sqlite3")
                os.fsync(fd)
            uri = (
                "file:"
                + quote(str(Path(self.directory) / "runs.sqlite3"), safe="/")
                + "?mode="
                + ("rw" if write else "ro")
            )
            connection = sqlite3.connect(uri, uri=True, timeout=2, isolation_level=None)
            if _regular(fd, "runs.sqlite3") != identity:
                raise ValueError("database replaced")
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.execute("PRAGMA busy_timeout=2000")
            if write:
                connection.execute("PRAGMA synchronous=FULL")
                if connection.execute("PRAGMA journal_mode").fetchone()[0] != "delete":
                    raise ValueError("unsupported journal mode")
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            if created:
                for statement in SCHEMA.values():
                    connection.execute(statement)
                connection.execute("INSERT INTO meta(tenant) VALUES (?)", (self.tenant_id,))
                connection.execute(f"PRAGMA application_id={APP_ID}")
                connection.execute("PRAGMA user_version=1")
            self._validate(connection)
            yield connection
            if write:
                connection.execute("COMMIT")
            else:
                connection.execute("ROLLBACK")
            if _regular(fd, "runs.sqlite3") != identity:
                raise ValueError("database replaced")
        except (RunNotFoundError, RunTenantIsolationError):
            raise
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            sqlite3.Error,
            RecursionError,
            OverflowError,
        ):
            raise LocalStoreError() from None
        finally:
            if connection is not None:
                connection.close()
            if fd is not None:
                os.close(fd)

    def _validate(self, connection):
        if (
            connection.execute("PRAGMA application_id").fetchone()[0] != APP_ID
            or connection.execute("PRAGMA user_version").fetchone()[0] != 1
        ):
            raise ValueError("unsupported database")
        objects = connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master").fetchall()
        expected = [("table", name, name, sql) for name, sql in SCHEMA.items()]
        expected.extend(("index", "sqlite_autoindex_" + name + "_1", name, None) for name in SCHEMA)
        if sorted(objects) != sorted(expected):
            raise ValueError("unexpected database schema")
        if connection.execute("SELECT tenant FROM meta").fetchall() != [(self.tenant_id,)]:
            raise ValueError("database tenant mismatch")
        if connection.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise ValueError("corrupt database")
        count, size = connection.execute(
            "SELECT count(*), coalesce(sum(length(CAST(payload AS BLOB))),0) FROM runs"
        ).fetchone()
        if count > ROW_LIMIT or size > TOTAL_LIMIT:
            raise ValueError("store limit")
        for run_id, tenant, payload in connection.execute(
            "SELECT run_id, tenant, payload FROM runs"
        ):
            if tenant != self.tenant_id:
                raise ValueError("row tenant mismatch")
            _decode(tenant, run_id, payload)

    def check(self):
        try:
            fd = _directory(self.directory)
            try:
                for sidecar in ("runs.sqlite3-wal", "runs.sqlite3-shm"):
                    try:
                        os.stat(sidecar, dir_fd=fd, follow_symlinks=False)
                    except FileNotFoundError:
                        continue
                    raise ValueError("unsupported WAL sidecar")
                journal = _regular(fd, "runs.sqlite3-journal", optional=True)
                exists = _regular(fd, "runs.sqlite3", optional=True) is not None
            finally:
                os.close(fd)
            if not exists:
                if journal is not None:
                    raise ValueError("orphan journal")
                return "not_created"
            with self._connection():
                return "validated"
        except (OSError, ValueError, TypeError):
            raise LocalStoreError() from None

    def initialize(self):
        with self._connection(write=True, create=True):
            pass

    def put(self, tenant_id, run):
        if tenant_id != self.tenant_id or run.tenant_id.root != self.tenant_id:
            raise RunTenantIsolationError("run tenant mismatch")
        try:
            payload = run.model_dump_json()
            stored = _decode(tenant_id, run.run_id.root, payload)
        except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
            raise LocalStoreError() from None
        with self._connection(write=True) as connection:
            connection.execute(
                "INSERT INTO runs(run_id,tenant,payload) VALUES (?,?,?) "
                "ON CONFLICT(run_id) DO UPDATE SET payload=excluded.payload",
                (run.run_id.root, tenant_id, payload),
            )
            self._validate(connection)
        return stored

    def get(self, tenant_id, run_id):
        if tenant_id != self.tenant_id:
            raise RunTenantIsolationError("run tenant mismatch")
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload FROM runs WHERE run_id=? AND tenant=?", (run_id, tenant_id)
            ).fetchone()
            if row is None:
                raise RunNotFoundError("run not found")
            return _decode(tenant_id, run_id, row[0])
