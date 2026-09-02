from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class AvailableFix:
    product_id: str
    version: str
    fix_id: str | None = None
    kind: str = "unknown"
    release_date: str | None = None
    source_url: str | None = None

    # Never assume cumulative semantics. Providers must set this from IBM
    # metadata/readmes for the exact fix/release.
    cumulative: bool | None = None
    supersedes: tuple[str, ...] = ()
    prerequisites: tuple[str, ...] = ()
    corequisites: tuple[str, ...] = ()
    applies_to: tuple[str, ...] = ()
    applicability_notes: tuple[str, ...] = ()

    metadata: dict[str, object] = field(default_factory=dict)


class PatchProvider(Protocol):
    def available_fixes(self, installed: dict[str, object]) -> list[AvailableFix]:
        """Return applicable candidates; do not collapse them to 'latest'."""
        ...
