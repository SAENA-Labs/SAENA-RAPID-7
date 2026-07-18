"""Framework discovery seam (w6-11 placeholder — w6-12 fills adapters).

This module defines the typed interface only. The default `discover()` is
honest about what this unit knows: nothing — it returns `UNKNOWN` unless an
adapter (landing in `tools/saena-pilot/src/saena_pilot/discovery/` in unit
w6-12) positively identifies the framework. No adapter may guess: a result is
either a positive detection or `UNKNOWN`/`UNSUPPORTED`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Protocol


class SupportStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    """Outcome of framework discovery over the customer root."""

    framework: str
    status: SupportStatus
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "framework": self.framework,
            "status": self.status.value,
            "detail": self.detail,
        }


class DiscoveryAdapter(Protocol):
    """One framework detector (w6-12). Returns a positive `DiscoveryResult`
    or `None` when this adapter cannot identify the repo."""

    def detect(self, customer_root: Path) -> DiscoveryResult | None: ...


#: Honest default when no adapter matches (or none are installed yet).
UNKNOWN_RESULT = DiscoveryResult(
    framework="unknown",
    status=SupportStatus.UNKNOWN,
    detail=(
        "framework discovery adapters are not installed in this unit (w6-12 "
        "provides them); no detection was attempted"
    ),
)


def discover(customer_root: Path, adapters: Sequence[DiscoveryAdapter] = ()) -> DiscoveryResult:
    """Run adapters in order; first positive detection wins, else UNKNOWN."""
    for adapter in adapters:
        result = adapter.detect(customer_root)
        if result is not None:
            return result
    return UNKNOWN_RESULT
