"""Deployed-domain validation.

The domain is used for discovery/verification identity ONLY — this unit never
fetches it. Validation is fail-closed against SSRF-adjacent shapes anyway,
because the value is bound into evidence and later units will consume it:

- https scheme only (no http, no other scheme)
- hostname required; no userinfo (credentials in URLs are refused)
- literal loopback (localhost / 127.0.0.0/8 / ::1), private ranges (10/8,
  172.16/12, 192.168/16), link-local 169.254/16 (incl. the metadata endpoint
  169.254.169.254), unspecified/reserved/multicast addresses, and the
  `.internal` / `.local` suffixes are all rejected.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from saena_pilot.errors import ValidationFailedError

_REJECTED_HOST_SUFFIXES = (".internal", ".local", ".localhost")
_REJECTED_HOSTS = ("localhost", "internal", "local")


def _reject(domain: str, reason: str) -> ValidationFailedError:
    return ValidationFailedError(
        f"--domain {domain!r} rejected: {reason}",
        context={"domain": domain, "reason": reason},
    )


def validate_domain(domain: str) -> str:
    """Validate and return the normalized origin (`https://<host>[:port]`).

    Raises `ValidationFailedError` on any rejected shape.
    """
    try:
        parts = urlsplit(domain)
    except ValueError as exc:
        raise _reject(domain, f"unparsable URL ({exc})") from exc

    if parts.scheme != "https":
        raise _reject(domain, f"scheme must be https, got {parts.scheme or '(none)'!r}")
    if parts.username is not None or parts.password is not None:
        raise _reject(domain, "userinfo (credentials) in the URL is not allowed")

    try:
        hostname = parts.hostname
    except ValueError as exc:
        raise _reject(domain, f"invalid host ({exc})") from exc
    if not hostname:
        raise _reject(domain, "hostname is required")

    lowered = hostname.lower().rstrip(".")
    if lowered in _REJECTED_HOSTS:
        raise _reject(domain, f"host {lowered!r} is not a deployed public domain")
    if any(lowered.endswith(suffix) for suffix in _REJECTED_HOST_SUFFIXES):
        raise _reject(domain, f"host suffix of {lowered!r} is not a deployed public domain")

    ip: ipaddress.IPv4Address | ipaddress.IPv6Address | None
    try:
        ip = ipaddress.ip_address(lowered)
    except ValueError:
        ip = None
    if ip is not None and (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        raise _reject(domain, f"IP literal {lowered!r} is loopback/private/link-local/reserved")

    port = f":{parts.port}" if parts.port is not None else ""
    return f"https://{lowered}{port}"
