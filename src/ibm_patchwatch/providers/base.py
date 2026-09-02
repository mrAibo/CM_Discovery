from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class AvailableFix:
    product_id: str
    version: str
    fix_id: str | None = None
    release_date: str | None = None
    source_url: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class PatchProvider(Protocol):
    def latest(self, installed: dict[str, object]) -> AvailableFix | None:
        ...
