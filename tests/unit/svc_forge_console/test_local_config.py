"""Synthetic operator config and supplied report only; no network/real IdP."""

import json
import os

import pytest
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient
from saena_forge_console.local_config import (
    CONFIG_LIMIT,
    KEY_LIMIT,
    ConfigurationError,
    create_local_app,
    load_configuration,
    main,
)

from svc_forge_console.test_report_api import digest, documents
from svc_forge_console.test_verified_auth import key, token  # noqa: F401


@pytest.fixture
def config(tmp_path, key, monkeypatch):  # noqa: F811
    root = tmp_path.resolve()
    root.chmod(0o700)
    monkeypatch.setenv("SAENA_TENANT_ID", "acme-corp")
    pub = root / "public.pem"
    pub.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    pub.chmod(0o600)
    run = root / "run-one"
    run.mkdir(mode=0o700)
    report, receipt = documents()
    r, c = json.dumps(report).encode(), json.dumps(receipt).encode()
    (run / "report.json").write_bytes(r)
    (run / "receipt.json").write_bytes(c)
    value = {
        "version": 1,
        "tenant_id": "acme-corp",
        "issuer": "https://issuer.invalid",
        "audience": "saena-console",
        "public_key_file": "public.pem",
        "memberships": {
            "subject-1": {
                "actor_id": "actor-0001",
                "tenant_id": "acme-corp",
                "roles": ["proposer"],
            }
        },
        "readers": ["actor-0001"],
        "report_root": str(root),
        "reports": {
            "report-one": {
                "relative_directory": "run-one",
                "report_sha256": digest(r),
                "receipt_sha256": digest(c),
            }
        },
        "enable_viewer": True,
    }
    path = root / "config.json"

    def save():
        path.write_text(json.dumps(value))
        path.chmod(0o600)
        return str(path)

    save()
    monkeypatch.setenv("SAENA_LOCAL_CONFIG", str(path))
    return path, value, save


def test_config_producer_api_viewer(config, key, capsys):  # noqa: F811
    path, _, _ = config
    assert main(["--config", str(path), "--check"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["reports"] == result["members"] == 1
    assert result["live_observation_verified"] is False
    client = TestClient(create_local_app())
    assert client.get("/report-viewer").status_code == 200
    assert client.get("/v1/html-audit-reports/report-one").status_code == 401
    response = client.get(
        "/v1/html-audit-reports/report-one", headers={"Authorization": "Bearer " + token(key)}
    )
    assert response.status_code == 200
    assert response.json()["expected_page_count"] == 2
    assert response.json()["measured_page_count"] == 1


@pytest.mark.parametrize(
    "change",
    [
        lambda v: v.update(version=True),
        lambda v: v.update(version=2),
        lambda v: v.update(extra="forbidden"),
        lambda v: v.pop("issuer"),
        lambda v: v.update(issuer=""),
        lambda v: v.update(audience=[]),
        lambda v: v.update(enable_viewer="yes"),
        lambda v: v.update(tenant_id="other-tenant"),
        lambda v: v.update(public_key_file="../public.pem"),
        lambda v: v.update(public_key_file="/public.pem"),
        lambda v: v.update(public_key_file="public.pem/"),
        lambda v: v.update(memberships={}),
        lambda v: v["memberships"]["subject-1"].update(tenant_id="other-tenant"),
        lambda v: v["memberships"]["subject-1"].update(roles=["admin-invalid"]),
        lambda v: v["memberships"]["subject-1"].update(roles=["proposer", "proposer"]),
        lambda v: v["memberships"]["subject-1"].update(roles=[{}]),
        lambda v: v["memberships"].update({"other-subject": dict(v["memberships"]["subject-1"])}),
        lambda v: v.update(readers=["missing-actor"]),
        lambda v: v.update(readers=["actor-0001", "actor-0001"]),
        lambda v: v.update(readers=[{}]),
        lambda v: v.update(reports=[]),
        lambda v: v["reports"]["report-one"].update(tenant_id="other-tenant"),
        lambda v: v["reports"]["report-one"].update(report_sha256="bad"),
        lambda v: v.update(report_root="relative"),
    ],
)
def test_invalid_contract(config, change):
    _, value, save = config
    change(value)
    with pytest.raises(ConfigurationError):
        load_configuration(save())


@pytest.mark.parametrize(
    "kind",
    [
        "duplicate",
        "surrogate",
        "oversize",
        "symlink",
        "hardlink",
        "writable",
        "key-symlink",
        "key-hardlink",
        "key-writable",
        "key-large",
        "private-key",
        "directory-symlink",
        "fifo",
    ],
)
def test_unsafe_files(config, kind, key):  # noqa: F811
    path, value, save = config
    pub = path.parent / "public.pem"
    if kind == "duplicate":
        path.write_text('{"version":1,"version":1}')
    elif kind == "surrogate":
        path.write_text('{"version":"\\ud800"}')
    elif kind == "oversize":
        path.write_bytes(b" " * (CONFIG_LIMIT + 1))
    elif kind == "symlink":
        moved = path.with_name("real.json")
        path.rename(moved)
        path.symlink_to(moved)
    elif kind == "hardlink":
        os.link(path, path.with_name("alias.json"))
    elif kind == "writable":
        path.chmod(0o666)
    elif kind == "key-symlink":
        moved = pub.with_name("real.pem")
        pub.rename(moved)
        pub.symlink_to(moved)
    elif kind == "key-hardlink":
        os.link(pub, pub.with_name("alias.pem"))
    elif kind == "key-writable":
        pub.chmod(0o666)
    elif kind == "key-large":
        pub.write_bytes(b"x" * (KEY_LIMIT + 1))
    elif kind == "private-key":
        pub.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
    elif kind == "directory-symlink":
        link = path.parent / "linked"
        link.symlink_to(path.parent, target_is_directory=True)
        value["public_key_file"] = "linked/public.pem"
        save()
    elif kind == "fifo":
        pub.unlink()
        os.mkfifo(pub)
    with pytest.raises(ConfigurationError):
        load_configuration(str(path))


def test_corrupt_artifact_sanitized(config, capsys):
    path, _, _ = config
    (path.parent / "run-one" / "report.json").write_text("secret customer data")
    assert main(["--config", str(path), "--check"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "local configuration unavailable or invalid\n"
    with pytest.raises(ConfigurationError, match="unavailable or invalid"):
        create_local_app()


def test_missing_environment(config, monkeypatch):
    monkeypatch.delenv("SAENA_TENANT_ID")
    with pytest.raises(ConfigurationError):
        create_local_app()


def test_missing_config_environment(monkeypatch):
    monkeypatch.delenv("SAENA_LOCAL_CONFIG", raising=False)
    with pytest.raises(ConfigurationError):
        create_local_app()


def test_read_grant_not_implied(config, key):  # noqa: F811
    _, value, save = config
    value["readers"] = []
    save()
    client = TestClient(create_local_app())
    assert (
        client.get(
            "/v1/html-audit-reports/report-one", headers={"Authorization": "Bearer " + token(key)}
        ).status_code
        == 403
    )


def test_actual_check_subprocess(config):
    import subprocess
    import sys

    path, _, _ = config
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "saena_forge_console.local_config",
            "--config",
            str(path),
            "--check",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["reports"] == 1
    assert "actor-0001" not in result.stdout
    assert str(path) not in result.stdout


@pytest.mark.parametrize("field", ["memberships", "readers", "reports"])
def test_config_count_limits(config, field):
    _, value, save = config
    if field == "memberships":
        value[field] = {
            f"s-{n}": {"actor_id": f"actor-{n:04}", "tenant_id": "acme-corp", "roles": []}
            for n in range(1001)
        }
    elif field == "readers":
        value[field] = [f"actor-{n:04}" for n in range(1001)]
    else:
        value[field] = {f"r-{n}": dict(value[field]["report-one"]) for n in range(1001)}
    with pytest.raises(ConfigurationError):
        load_configuration(save())


def test_viewer_explicitly_off(config):
    _, value, save = config
    value["enable_viewer"] = False
    save()
    assert TestClient(create_local_app()).get("/report-viewer").status_code == 404
