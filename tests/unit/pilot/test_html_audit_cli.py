"""Synthetic local-only CLI input/storage security regressions."""

import hashlib
import json
import os
import stat
from pathlib import Path

import pytest
from _pilot_fixtures import make_rapid7_fixture
from saena_pilot.errors import BundleInvalidError, SecretShapedValueError, ValidationFailedError
from saena_pilot.html_audit_cli import generate_local_report


@pytest.fixture
def setup(tmp_path, monkeypatch):
    root = make_rapid7_fixture(tmp_path / "rapid7")
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    data = b"<head><title>Product</title></head>"
    (inputs / "page.html").write_bytes(data)
    manifest = dict(
        tenant_id="tenant-a",
        expected_pages=["https://example.com/a", "https://example.com/missing"],
        snapshots=[
            dict(
                page_url="https://example.com/a",
                file="page.html",
                sha256="sha256:" + hashlib.sha256(data).hexdigest(),
            )
        ],
    )
    (inputs / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setenv("SAENA_PILOT_HOME", str(tmp_path / "store"))
    return root, inputs, manifest


def run(setup):
    root, inputs, _ = setup
    return generate_local_report(
        tenant_id="tenant-a",
        input_root=str(inputs),
        manifest_path="manifest.json",
        rapid7_root=root,
    )


def update(setup):
    _, inputs, manifest = setup
    (inputs / "manifest.json").write_text(json.dumps(manifest))


def test_actual_pipeline_saves_private_guarded_reports(setup):
    path = run(setup)
    data = json.loads((path / "report.json").read_text())
    assert data["measured_page_count"] == 1
    assert data["unmeasured_pages"] == ["https://example.com/missing"]
    assert set(p.name for p in path.iterdir()) == {"report.json", "report.txt", "receipt.json"}
    assert not (path / "run.json").exists()
    assert stat.S_IMODE(path.stat().st_mode) == 0o700
    assert stat.S_IMODE((path / "report.json").stat().st_mode) == 0o600
    assert (setup[1] / "page.html").read_bytes() == b"<head><title>Product</title></head>"


@pytest.mark.parametrize("change", [{"tenant_id": "b"}, {"unexpected": True}])
def test_manifest_identity_and_unknown_keys_refused(setup, change):
    setup[2].update(change)
    update(setup)
    with pytest.raises(ValueError):
        run(setup)


def test_hash_mismatch_refused_before_output(setup):
    (setup[1] / "page.html").write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        run(setup)
    assert not (setup[1].parent / "store").exists()


@pytest.mark.parametrize(
    "path", ["../outside.html", "/etc/passwd", ".env", "nested/../../page.html"]
)
def test_escape_and_non_html_refused(setup, path):
    setup[2]["snapshots"][0]["file"] = path
    update(setup)
    with pytest.raises((ValueError, OSError)):
        run(setup)


def test_symlink_file_refused(setup):
    root, inputs, _ = setup
    (inputs / "page.html").unlink()
    (inputs / "page.html").symlink_to(root / "CLAUDE.md")
    with pytest.raises(OSError):
        run(setup)


def test_symlink_directory_refused(setup):
    root, inputs, _ = setup
    alias = inputs.parent / "alias"
    alias.symlink_to(inputs, target_is_directory=True)
    with pytest.raises(OSError):
        generate_local_report(
            tenant_id="tenant-a",
            input_root=str(alias),
            manifest_path="manifest.json",
            rapid7_root=root,
        )


def test_hardlink_refused(setup):
    inputs = setup[1]
    os.link(inputs / "page.html", inputs / "another.html")
    with pytest.raises(ValueError, match="singly-linked"):
        run(setup)


def test_fifo_refused_without_block(setup):
    inputs = setup[1]
    (inputs / "page.html").unlink()
    os.mkfifo(inputs / "page.html")
    with pytest.raises(ValueError, match="regular"):
        run(setup)


def test_duplicate_manifest_keys_refused(setup):
    (setup[1] / "manifest.json").write_text('{"tenant_id":"tenant-a","tenant_id":"tenant-b"}')
    with pytest.raises(ValueError, match="duplicate"):
        run(setup)


def test_secret_raw_html_refused_even_if_not_reported(setup):
    data = b"<head><title>A</title></head><!-- sk-proj-" + b"a" * 30 + b" -->"
    (setup[1] / "page.html").write_bytes(data)
    setup[2]["snapshots"][0]["sha256"] = "sha256:" + hashlib.sha256(data).hexdigest()
    update(setup)
    with pytest.raises(SecretShapedValueError) as exc:
        run(setup)
    assert "sk-proj-" not in str(exc.value)
    assert not (setup[1].parent / "store").exists()


def test_output_cannot_be_inside_input_or_repo(setup, monkeypatch):
    for location in [setup[0] / "out", setup[1] / "out"]:
        monkeypatch.setenv("SAENA_PILOT_HOME", str(location))
        with pytest.raises(ValidationFailedError):
            run(setup)
        assert not location.exists()


def test_output_symlink_refused(setup, monkeypatch):
    real = setup[1].parent / "real"
    real.mkdir()
    alias = setup[1].parent / "output-link"
    alias.symlink_to(real, target_is_directory=True)
    monkeypatch.setenv("SAENA_PILOT_HOME", str(alias))
    with pytest.raises(OSError):
        run(setup)


def test_bundle_validation_is_not_bypassed(setup):
    (setup[0] / ".claude/skills/manifest.json").unlink(missing_ok=True)
    # Remove the actual bundle manifest irrespective of fixture file name.
    from saena_pilot.bundle import MANIFEST_RELPATH

    (setup[0] / MANIFEST_RELPATH).unlink(missing_ok=True)
    with pytest.raises(BundleInvalidError):
        run(setup)
    assert not (setup[1].parent / "store").exists()


def test_cli_success_and_generic_error_do_not_echo_input(setup, monkeypatch, capsys):
    import saena_pilot.html_audit_cli as cli

    monkeypatch.setattr(cli, "_resolve_rapid7_root", lambda: setup[0])
    args = ["--tenant-id", "tenant-a", "--input-root", str(setup[1]), "--manifest", "manifest.json"]
    assert cli.main(args) == 0
    printed = capsys.readouterr()
    assert (Path(printed.out.strip()) / "report.json").is_file()
    (setup[1] / "manifest.json").write_text('{"sensitive":"secret-payload",')
    assert cli.main(args) == 1
    assert "secret-payload" not in capsys.readouterr().err


def test_output_cannot_write_customer_repo_sibling_of_snapshot_directory(setup, monkeypatch):
    from _pilot_fixtures import make_git_repo

    customer = make_git_repo(setup[1].parent / "customer")
    snapshots = customer / "snapshots"
    snapshots.mkdir()
    for name in ["page.html", "manifest.json"]:
        (snapshots / name).write_bytes((setup[1] / name).read_bytes())
    monkeypatch.setenv("SAENA_PILOT_HOME", str(customer / "reports"))
    with pytest.raises(ValueError, match="Git working trees"):
        generate_local_report(
            tenant_id="tenant-a",
            input_root=str(snapshots),
            manifest_path="manifest.json",
            rapid7_root=setup[0],
        )
    assert not (customer / "reports").exists()


def test_shared_writable_output_ancestor_refused(setup, monkeypatch):
    shared = setup[1].parent / "shared"
    shared.mkdir(mode=0o777)
    shared.chmod(0o777)
    monkeypatch.setenv("SAENA_PILOT_HOME", str(shared / "reports"))
    with pytest.raises(ValueError, match="trusted"):
        run(setup)
