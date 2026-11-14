"""Read explicitly approved local HTML snapshots and save offline audit reports.

No HTTP, browser, model, subprocess from customer content or customer writes.
The sole subprocess validation is the existing trusted skill-bundle validator.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import stat
import sys
import uuid
from pathlib import Path

from saena_pilot._git import git_toplevel
from saena_pilot.bundle import enforce_bundle
from saena_pilot.cli import _resolve_rapid7_root
from saena_pilot.runstore import ensure_store_outside_repos
from saena_pilot.secretguard import guard_tree

MAX_MANIFEST_BYTES = 256 * 1024
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024


def _parts(value: str, *, absolute: bool) -> tuple[str, ...]:
    if not isinstance(value, str) or not value or Path(value).is_absolute() != absolute:
        raise ValueError("path must have required absolute/relative form")
    parts = tuple(part for part in value.split("/") if part)
    if any(part in {".", ".."} or "\\" in part for part in parts):
        raise ValueError("path traversal refused")
    return parts


def _directory(path: str, *, create: bool = False, trusted_output: bool = False) -> int:
    parts = _parts(path, absolute=True)
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parts:
            if create:
                with contextlib.suppress(FileExistsError):
                    os.mkdir(part, mode=0o700, dir_fd=fd)
            new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = new
            if trusted_output:
                info = os.fstat(fd)
                shared_temp = info.st_uid == 0 and bool(info.st_mode & stat.S_ISVTX)
                if info.st_uid not in {0, os.getuid()} or (
                    info.st_mode & 0o022 and not shared_temp
                ):
                    raise ValueError("output ancestors must be trusted and not shared-writable")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _read(root_fd: int, relative: str, limit: int) -> bytes:
    parts = _parts(relative, absolute=False)
    if not parts or any(part.startswith(".") for part in parts):
        raise ValueError("hidden or empty input path refused")
    parent = os.dup(root_fd)
    file_fd = None
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            os.close(parent)
            parent = child
        file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        info = os.fstat(file_fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise ValueError("input must be a bounded singly-linked regular file")
        with os.fdopen(file_fd, "rb") as stream:
            file_fd = None
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError("input exceeds byte budget")
        return data
    finally:
        if file_fd is not None:
            os.close(file_fd)
        os.close(parent)


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate manifest key")
        result[key] = value
    return result


def generate_local_report(
    *, tenant_id: str, input_root: str, manifest_path: str, rapid7_root: Path, bundle_runner=None
) -> Path:
    """Explicit invocation authorizes only these local bytes; not a live action contract."""
    enforce_bundle(rapid7_root, runner=bundle_runner)
    guard_tree({"tenant_id": tenant_id}, path="html_cli")
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError("explicit tenant required")
    root_fd = _directory(input_root)
    try:
        raw_manifest = _read(root_fd, manifest_path, MAX_MANIFEST_BYTES)
        manifest = json.loads(raw_manifest, object_pairs_hook=_no_duplicates)
        if not isinstance(manifest, dict) or set(manifest) != {
            "tenant_id",
            "expected_pages",
            "snapshots",
        }:
            raise ValueError("invalid manifest fields")
        guard_tree(manifest, path="html_snapshot_manifest")
        if manifest["tenant_id"] != tenant_id:
            raise ValueError("manifest tenant mismatch")
        if not isinstance(manifest["expected_pages"], list) or not isinstance(
            manifest["snapshots"], list
        ):
            raise ValueError("manifest cohorts must be lists")
        if len(manifest["snapshots"]) > 1000:
            raise ValueError("too many snapshots")
        # Imports are lazy: no new dependency/lockfile or hidden installation.
        from saena_site_discovery.page_audit import audit_supplied_html

        from saena_pilot.page_audit_report import build_page_audit_report

        audits = []
        total = 0
        for item in manifest["snapshots"]:
            if (
                not isinstance(item, dict)
                or not {"page_url", "file", "sha256"} <= set(item)
                or set(item) - {"page_url", "file", "sha256", "http_status"}
            ):
                raise ValueError("invalid snapshot fields")
            if not isinstance(item["file"], str) or Path(item["file"]).suffix.lower() not in {
                ".html",
                ".htm",
            }:
                raise ValueError("snapshot must be an HTML file")
            data = _read(root_fd, item["file"], min(MAX_FILE_BYTES, MAX_TOTAL_BYTES - total))
            total += len(data)
            digest = "sha256:" + hashlib.sha256(data).hexdigest()
            if item["sha256"] != digest:
                raise ValueError("snapshot hash mismatch")
            # HTML may contain secrets even if findings do not echo them.
            guard_tree(data.decode("utf-8-sig", errors="strict"), path="html_snapshot")
            audits.append(
                audit_supplied_html(
                    tenant_id=tenant_id,
                    page_url=item["page_url"],
                    html=data,
                    evidence_ref="local-html://sha256/" + digest[7:],
                    http_status=item.get("http_status"),
                )
            )
        report = build_page_audit_report(
            tenant_id=tenant_id, expected_pages=manifest["expected_pages"], audits=audits
        )
    finally:
        os.close(root_fd)
    # Existing store-location policy plus descriptor-relative no-symlink writes.
    store = ensure_store_outside_repos(rapid7_root, Path(input_root))
    # Input may be a snapshots/ subdirectory of a customer repo. Refuse output
    # inside ANY existing Git working tree, not just input_root itself.
    existing_parent = store
    while not existing_parent.exists():
        existing_parent = existing_parent.parent
    for ancestor in (existing_parent, *existing_parent.parents):
        try:
            os.lstat(ancestor / ".git")
        except FileNotFoundError:
            continue
        # Any marker type is refused; permission errors propagate fail-closed.
        raise ValueError("report store must be outside all Git working trees")
    if git_toplevel(existing_parent) is not None:
        raise ValueError("report store must be outside all Git working trees")
    # Reject symlinked configured store, not only its resolved destination.
    from saena_pilot.runstore import runs_root

    output_fd = _directory(str(runs_root().absolute()), create=True, trusted_output=True)
    try:
        run_name = "html-audit-" + str(uuid.uuid4())
        os.mkdir(run_name, mode=0o700, dir_fd=output_fd)
        report_fd = os.open(
            run_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=output_fd
        )
        try:
            receipt = {
                "tenant_id": tenant_id,
                "manifest_sha256": "sha256:" + hashlib.sha256(raw_manifest).hexdigest(),
                "scope": "offline_supplied_html",
                "raw_html_stored": False,
            }
            guard_tree(receipt, path="html_receipt")
            for name, text in [
                ("report.json", report.json_text),
                ("report.txt", report.human_text),
                ("receipt.json", json.dumps(receipt, sort_keys=True) + "\n"),
            ]:
                fd = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=report_fd,
                )
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    stream.write(text)
        finally:
            os.close(report_fd)
    finally:
        os.close(output_fd)
    return store / run_name


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline approved local HTML audit; never live search."
    )
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args(argv)
    try:
        path = generate_local_report(
            tenant_id=args.tenant_id,
            input_root=args.input_root,
            manifest_path=args.manifest,
            rapid7_root=_resolve_rapid7_root(),
        )
    except Exception as exc:
        # Never echo untrusted input, JSON decoder payload, token or filesystem paths.
        print(f"HTML audit refused ({type(exc).__name__}); no success claimed.", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
