"""Strict operator-owned local configuration; no network, credentials or issuance."""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

from saena_domain.authz import Role

from saena_forge_console.app import create_app
from saena_forge_console.report_store import ReportCatalog, ReportEntry, _json, _parts, _trusted_dir
from saena_forge_console.verified_auth import Membership, TokenVerifier

CONFIG_LIMIT = 1024 * 1024
KEY_LIMIT = 16 * 1024


class ConfigurationError(ValueError):
    """Sanitized operator-visible failure."""


def _object(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError("invalid object")
    return value


def _text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError("invalid text")
    return value


def _directory(path):
    if not isinstance(path, str):
        raise ValueError("invalid directory")
    p = Path(path)
    if not p.is_absolute() or str(p) != path or any(n in {".", ".."} for n in p.parts):
        raise ValueError("canonical absolute directory required")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in p.parts[1:]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
            _trusted_dir(fd)
        return fd
    except BaseException:
        os.close(fd)
        raise


def _file(fd, relative, limit):
    parts = _parts(relative)
    current = os.dup(fd)
    try:
        for part in parts[:-1]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            os.close(current)
            current = nxt
            _trusted_dir(current)
        target = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current)
        with os.fdopen(target, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_uid not in {0, os.getuid()}
                or info.st_mode & 0o022
                or info.st_size > limit
            ):
                raise ValueError("unsafe configuration file")
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError("file limit")
        return data
    finally:
        os.close(current)


@dataclass(frozen=True)
class LocalConfiguration:
    verifier: TokenVerifier
    catalog: ReportCatalog
    enable_viewer: bool
    member_count: int

    def check(self):
        for entry in self.catalog.entries.values():
            self.catalog.read(entry)
        return {
            "status": "ok",
            "scope": "local_configuration_and_artifacts_only",
            "members": self.member_count,
            "reports": len(self.catalog.entries),
            "viewer_enabled": self.enable_viewer,
            "live_observation_verified": False,
        }

    def app(self):
        # Fail startup on stale/corrupt artifacts rather than expose a broken viewer.
        self.check()
        return create_app(
            token_verifier=self.verifier,
            report_catalog=self.catalog,
            enable_report_viewer=self.enable_viewer,
        )


def load_configuration(path: str) -> LocalConfiguration:
    try:
        p = Path(path)
        if not p.is_absolute() or str(p) != path or p.name.startswith("."):
            raise ValueError("canonical absolute config path required")
        fd = _directory(str(p.parent))
        try:
            config = _json(_file(fd, p.name, CONFIG_LIMIT))
            _object(
                config,
                {
                    "version",
                    "tenant_id",
                    "issuer",
                    "audience",
                    "public_key_file",
                    "memberships",
                    "readers",
                    "report_root",
                    "reports",
                    "enable_viewer",
                },
            )
            if type(config["version"]) is not int or config["version"] != 1:
                raise ValueError("unsupported version")
            tenant = _text(config["tenant_id"])
            if tenant != os.environ.get("SAENA_TENANT_ID"):
                raise ValueError("tenant environment mismatch")
            if type(config["enable_viewer"]) is not bool:
                raise ValueError("boolean viewer flag required")
            raw_members = config["memberships"]
            if not isinstance(raw_members, dict) or not 1 <= len(raw_members) <= 1000:
                raise ValueError("membership limit")
            members = {}
            actors = set()
            for subject, raw in raw_members.items():
                _text(subject)
                _object(raw, {"actor_id", "tenant_id", "roles"})
                if raw["tenant_id"] != tenant:
                    raise ValueError("mixed tenant")
                roles = raw["roles"]
                if (
                    not isinstance(roles, list)
                    or len(roles) > len(Role)
                    or any(not isinstance(r, str) for r in roles)
                    or len(set(roles)) != len(roles)
                ):
                    raise ValueError("invalid roles")
                member = Membership(
                    _text(raw["actor_id"]), tenant, frozenset(Role(r) for r in roles)
                )
                if member.actor_id in actors:
                    raise ValueError("duplicate actor")
                actors.add(member.actor_id)
                members[subject] = member
            readers = config["readers"]
            if (
                not isinstance(readers, list)
                or len(readers) > 1000
                or any(not isinstance(a, str) for a in readers)
                or len(set(readers)) != len(readers)
                or not set(readers) <= actors
            ):
                raise ValueError("invalid readers")
            raw_reports = config["reports"]
            if not isinstance(raw_reports, dict) or len(raw_reports) > 1000:
                raise ValueError("report limit")
            entries = {}
            for report_id, raw in raw_reports.items():
                _object(raw, {"relative_directory", "report_sha256", "receipt_sha256"})
                entries[report_id] = ReportEntry(tenant_id=tenant, **raw)
            root = _text(config["report_root"])
            root_fd = _directory(root)
            os.close(root_fd)
            catalog = ReportCatalog(
                root=root, entries=entries, readers={(tenant, a) for a in readers}
            )
            key = _file(fd, config["public_key_file"], KEY_LIMIT)
            verifier = TokenVerifier(
                public_key_pem=key,
                issuer=_text(config["issuer"]),
                audience=_text(config["audience"]),
                memberships=members,
            )
            return LocalConfiguration(verifier, catalog, config["enable_viewer"], len(members))
        finally:
            os.close(fd)
    except (OSError, ValueError, TypeError, KeyError, RecursionError, OverflowError):
        raise ConfigurationError("local configuration unavailable or invalid") from None


def create_local_app():
    """ASGI factory. Reads only the explicit SAENA_LOCAL_CONFIG absolute path."""
    try:
        return load_configuration(os.environ.get("SAENA_LOCAL_CONFIG", "")).app()
    except (OSError, ValueError, TypeError, KeyError, RecursionError, OverflowError):
        raise ConfigurationError("local configuration unavailable or invalid") from None


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate local configuration without starting a server"
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--check", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        result = load_configuration(args.config).check()
    except (OSError, ValueError, TypeError, KeyError, RecursionError, OverflowError):
        print("local configuration unavailable or invalid", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
