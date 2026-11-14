"""Local pinned-key verification. No IdP/network/key discovery or token issuance."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from fastapi import Request
from saena_domain.authz import Role
from saena_domain.identity import ActorContext

from saena_forge_console.authn import RequestActor
from saena_forge_console.errors import auth_error


@dataclass(frozen=True, slots=True)
class Membership:
    actor_id: str
    tenant_id: str
    roles: frozenset[Role]

    def __post_init__(self) -> None:
        object.__setattr__(self, "roles", frozenset(self.roles))
        if any(not isinstance(role, Role) for role in self.roles):
            raise ValueError("membership roles must be Role values")
        ActorContext.from_payload(
            {
                "actor_id": self.actor_id,
                "tenant_id": self.tenant_id,
                "session_id": "configuration-check",
                "actor_type": "human",
            }
        )


class TokenVerifier:
    """One issuer/audience/key, immutable server membership; no client-selected keys."""

    def __init__(
        self,
        *,
        public_key_pem: bytes,
        issuer: str,
        audience: str,
        memberships: Mapping[str, Membership],
        max_ttl_seconds: int = 3600,
    ) -> None:
        if (
            not issuer
            or not audience
            or type(max_ttl_seconds) is not int
            or not 1 <= max_ttl_seconds <= 3600
        ):
            raise ValueError("invalid trust configuration")
        key = load_pem_public_key(public_key_pem)
        if not isinstance(key, RSAPublicKey) or key.key_size < 2048:
            raise ValueError("RS256 public key of at least 2048 bits required")
        if any(
            not isinstance(k, str) or not k.strip() or not isinstance(v, Membership)
            for k, v in memberships.items()
        ):
            raise ValueError("invalid membership configuration")
        self._key = key
        self._issuer = issuer
        self._audience = audience
        self._memberships = MappingProxyType(dict(memberships))
        self._max_ttl = max_ttl_seconds

    def authenticate(self, request: Request) -> RequestActor:
        try:
            for name in (
                "x-saena-actor-id",
                "x-saena-session-id",
                "x-saena-actor-type",
                "x-saena-roles",
            ):
                if name in request.headers:
                    raise ValueError("identity headers forbidden")
            values = request.headers.getlist("authorization")
            if len(values) != 1 or len(values[0]) > 16384:
                raise ValueError("authorization required")
            scheme, token = values[0].split(" ")
            if scheme.lower() != "bearer" or not token:
                raise ValueError("bearer required")
            header = jwt.get_unverified_header(token)
            if set(header) - {"alg", "typ", "kid"} or header.get("alg") != "RS256":
                raise ValueError("unsupported header")
            claims = jwt.decode(
                token,
                self._key,
                algorithms=["RS256"],
                issuer=self._issuer,
                audience=self._audience,
                options={
                    "require": ["sub", "jti", "iat", "nbf", "exp", "iss", "aud"],
                    "strict_aud": True,
                },
            )
            if any(type(claims[k]) is not int for k in ("iat", "nbf", "exp")):
                raise ValueError("integer dates required")
            if (
                not claims["iat"] <= claims["nbf"] < claims["exp"]
                or not 0 < claims["exp"] - claims["iat"] <= self._max_ttl
            ):
                raise ValueError("invalid lifetime")
            member = self._memberships[claims["sub"]]
            if os.environ.get("SAENA_TENANT_ID") != member.tenant_id:
                raise ValueError("pod tenant mismatch")
            tenants = request.headers.getlist("x-saena-tenant-id")
            if tenants and tenants != [member.tenant_id]:
                raise ValueError("requested tenant mismatch")
            actor = ActorContext.from_payload(
                {
                    "actor_id": member.actor_id,
                    "tenant_id": member.tenant_id,
                    "actor_type": "human",
                    "session_id": claims["jti"],
                }
            )
            return RequestActor(actor=actor, roles=member.roles)
        except (ValueError, TypeError, KeyError, jwt.PyJWTError):
            raise auth_error(
                "authentication_failed", detail="verified authentication required"
            ) from None
