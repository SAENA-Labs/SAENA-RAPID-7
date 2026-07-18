"""VULN-1 reproduction: non-canonical numeric IP encodings bypass the
loopback/private/unspecified rejection in `saena_pilot.domain.validate_domain`.

The domain is bound into evidence and consumed by later units (w6-12 discovery
adapters that MAY fetch). `validate_domain` documents that it rejects loopback,
RFC1918, link-local and the cloud-metadata endpoint — but `ipaddress.ip_address`
only parses canonical dotted/colon forms, so integer / hex / octal / short-form
spellings fall through the `ip is None` branch and are ACCEPTED. A downstream
HTTP client resolves e.g. `2130706433` -> 127.0.0.1: classic SSRF.

Self-contained (no shared fixture beyond the conftest sys.path insert). Fix
belongs in saena_pilot.domain; this test unit's exclusive path is tests only,
so the gap is documented as a strict xfail, not patched here.
"""

from __future__ import annotations

import pytest
from saena_pilot.domain import validate_domain
from saena_pilot.errors import ValidationFailedError


@pytest.mark.parametrize(
    "domain",
    [
        "https://2130706433",  # decimal 127.0.0.1
        "https://0x7f000001",  # hex 127.0.0.1
        "https://0x7f.1",  # mixed hex/short 127.0.0.1
        "https://127.1",  # short-form 127.0.0.1
        "https://0",  # 0.0.0.0 unspecified
        "https://0300.0250.0.1",  # octal 192.168.0.1
    ],
)
@pytest.mark.xfail(
    strict=True,
    reason="VULN-1: non-canonical numeric IP encodings of loopback/private hosts "
    "bypass domain.validate_domain (SSRF-adjacent). Fix in saena_pilot.domain.",
)
def test_numeric_encoded_private_host_should_be_rejected(domain: str) -> None:
    with pytest.raises(ValidationFailedError):
        validate_domain(domain)


def test_canonical_forms_are_rejected_regression_anchor() -> None:
    # Proves the guard DOES reject the canonical spellings — VULN-1 is strictly
    # the non-canonical-encoding gap above, not a total failure of the filter.
    for domain in ("https://127.0.0.1", "https://192.168.0.1", "https://0.0.0.0"):
        with pytest.raises(ValidationFailedError):
            validate_domain(domain)
