"""Synthetic local tokens only; no real credentials or provider claims."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from saena_domain.authz import Role
from saena_forge_console.app import create_app
from saena_forge_console.verified_auth import Membership, TokenVerifier

from svc_forge_console.conftest import run_create_body


@pytest.fixture(scope="module")
def key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def verifier(key, memberships=None):
    return TokenVerifier(
        public_key_pem=key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ),
        issuer="https://issuer.invalid",
        audience="saena-console",
        memberships=memberships
        if memberships is not None
        else {"subject-1": Membership("actor-0001", "acme-corp", frozenset({Role.PROPOSER}))},
    )


def token(key, **changes):
    now = int(time.time())
    claims = {
        "iss": "https://issuer.invalid",
        "aud": "saena-console",
        "sub": "subject-1",
        "jti": "session-0001",
        "iat": now - 5,
        "nbf": now - 5,
        "exp": now + 300,
    }
    claims.update(changes)
    return jwt.encode(claims, key, algorithm="RS256")


@pytest.fixture
def production(key, monkeypatch):
    monkeypatch.setenv("SAENA_TENANT_ID", "acme-corp")
    return TestClient(create_app(token_verifier=verifier(key)))


def test_default_is_fail_closed():
    with pytest.raises(ValueError, match="TokenVerifier"):
        create_app()


def test_verified_identity_and_server_membership(production, key):
    auth = {"Authorization": "Bearer " + token(key, tenant_id="evil", roles=["auditor"])}
    response = production.get("/v1/actor/whoami", headers=auth)
    assert response.status_code == 200
    assert response.json()["tenant_id"] == "acme-corp"
    assert production.post("/v1/runs", headers=auth, json=run_create_body()).status_code == 201
    assert production.get("/v1/lineage/some-ref", headers=auth).status_code == 403


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "evil"},
        {"aud": "wrong"},
        {"aud": ["saena-console"]},
        {"sub": "unknown"},
        {"exp": 1},
        {"nbf": 9999999999},
        {"iat": 9999999999},
        {"exp": None},
        {"jti": ""},
        {"jti": 42},
        {"sub": None},
        {"iat": True},
        {"nbf": "0"},
        {"exp": 9999999999},
    ],
)
def test_invalid_claims_rejected(production, key, claims):
    value = token(key, **claims)
    response = production.get("/v1/actor/whoami", headers={"Authorization": "Bearer " + value})
    assert response.status_code == 401
    assert value not in response.text


@pytest.mark.parametrize("missing", ["iss", "aud", "sub", "jti", "iat", "nbf", "exp"])
def test_required_claims(production, key, missing):
    claims = jwt.decode(token(key), options={"verify_signature": False})
    del claims[missing]
    response = production.get(
        "/v1/actor/whoami",
        headers={"Authorization": "Bearer " + jwt.encode(claims, key, algorithm="RS256")},
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "header", ["X-Saena-Roles", "X-Saena-Actor-Id", "X-Saena-Session-Id", "X-Saena-Actor-Type"]
)
def test_identity_headers_refused(production, key, header):
    response = production.get(
        "/v1/actor/whoami", headers={"Authorization": "Bearer " + token(key), header: "auditor"}
    )
    assert response.status_code == 401


@pytest.mark.parametrize("value", ["", "Bearer x", "Basic x", "Bearer x y"])
def test_bad_bearer(production, value):
    assert production.get("/v1/actor/whoami", headers={"Authorization": value}).status_code == 401


def test_bad_signature(production, key):
    value = token(key)
    parts = value.split(".")
    parts[2] = ("A" if parts[2][0] != "A" else "B") + parts[2][1:]
    assert (
        production.get(
            "/v1/actor/whoami", headers={"Authorization": "Bearer " + ".".join(parts)}
        ).status_code
        == 401
    )


@pytest.mark.parametrize("algorithm", ["none", "HS256"])
def test_algorithm_confusion(production, key, algorithm):
    claims = jwt.decode(token(key), options={"verify_signature": False})
    value = jwt.encode(
        claims,
        "" if algorithm == "none" else "synthetic-secret-for-tests-only-123456",
        algorithm=algorithm,
    )
    assert (
        production.get("/v1/actor/whoami", headers={"Authorization": "Bearer " + value}).status_code
        == 401
    )


def test_tenant_without_header_still_checked(production, key, monkeypatch):
    monkeypatch.setenv("SAENA_TENANT_ID", "other-corp")
    assert (
        production.get(
            "/v1/actor/whoami", headers={"Authorization": "Bearer " + token(key)}
        ).status_code
        == 401
    )
    monkeypatch.delenv("SAENA_TENANT_ID")
    assert (
        production.get(
            "/v1/actor/whoami", headers={"Authorization": "Bearer " + token(key)}
        ).status_code
        == 401
    )


def test_duplicate_auth(production, key):
    auth = ("Authorization", "Bearer " + token(key))
    assert production.get("/v1/actor/whoami", headers=[auth, auth]).status_code == 401


def test_no_unregistered_subject(key, monkeypatch):
    monkeypatch.setenv("SAENA_TENANT_ID", "acme-corp")
    client = TestClient(create_app(token_verifier=verifier(key, {})))
    assert (
        client.get(
            "/v1/actor/whoami", headers={"Authorization": "Bearer " + token(key)}
        ).status_code
        == 401
    )


def test_membership_copy_is_immutable(key):
    source = {"subject-1": Membership("actor-0001", "acme-corp", frozenset())}
    service = verifier(key, source)
    source.clear()
    assert "subject-1" in service._memberships
    with pytest.raises(TypeError):
        service._memberships["other"] = source


def test_network_key_headers_rejected(production, key):
    claims = jwt.decode(token(key), options={"verify_signature": False})
    value = jwt.encode(
        claims, key, algorithm="RS256", headers={"jku": "https://example.invalid/keys"}
    )
    assert (
        production.get("/v1/actor/whoami", headers={"Authorization": "Bearer " + value}).status_code
        == 401
    )


def test_cross_tenant_run_is_not_disclosed(key, monkeypatch):
    monkeypatch.setenv("SAENA_TENANT_ID", "acme-corp")
    config = {
        "subject-1": Membership("actor-0001", "acme-corp", frozenset({Role.PROPOSER})),
        "subject-2": Membership("actor-0002", "other-corp", frozenset({Role.PROPOSER})),
    }
    client = TestClient(create_app(token_verifier=verifier(key, config)))
    created = client.post(
        "/v1/runs", json=run_create_body(), headers={"Authorization": "Bearer " + token(key)}
    )
    assert created.status_code == 201
    run_id = created.json()["run_id"]
    monkeypatch.setenv("SAENA_TENANT_ID", "other-corp")
    response = client.get(
        "/v1/runs/" + run_id, headers={"Authorization": "Bearer " + token(key, sub="subject-2")}
    )
    assert response.status_code == 404


def test_tokens_are_not_logged(production, key, caplog):
    value = token(key, sub="unknown")
    assert (
        production.get("/v1/actor/whoami", headers={"Authorization": "Bearer " + value}).status_code
        == 401
    )
    assert value not in caplog.text


def test_membership_has_no_implicit_permissions(key, monkeypatch):
    monkeypatch.setenv("SAENA_TENANT_ID", "acme-corp")
    client = TestClient(
        create_app(
            token_verifier=verifier(
                key, {"subject-1": Membership("actor-0001", "acme-corp", frozenset())}
            )
        )
    )
    assert (
        client.post(
            "/v1/runs", headers={"Authorization": "Bearer " + token(key)}, json=run_create_body()
        ).status_code
        == 403
    )


def test_private_key_is_not_verification_configuration(key):
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    with pytest.raises(ValueError):
        TokenVerifier(public_key_pem=pem, issuer="issuer", audience="aud", memberships={})


def test_conflicting_modes_refused(key):
    with pytest.raises(ValueError):
        create_app(auth_mode="test_headers", token_verifier=verifier(key))
    with pytest.raises(ValueError):
        create_app(auth_mode="typo", token_verifier=verifier(key))


@pytest.mark.parametrize(
    "field,value",
    [
        ("issuer", ["https://issuer.invalid", "other"]),
        ("audience", ["saena-console"]),
        ("issuer", " "),
        ("audience", " "),
        ("issuer", 123),
        ("audience", 123),
    ],
)
def test_trust_configuration_requires_single_exact_strings(key, field, value):
    config = {
        "public_key_pem": key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ),
        "issuer": "https://issuer.invalid",
        "audience": "saena-console",
        "memberships": {},
    }
    config[field] = value
    with pytest.raises(ValueError, match="trust configuration"):
        TokenVerifier(**config)
