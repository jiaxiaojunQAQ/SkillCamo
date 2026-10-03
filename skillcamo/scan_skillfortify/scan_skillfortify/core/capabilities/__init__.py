"""Capability models for the formal capability lattice.

This is a minimal copy for integration into unified_scanner.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterator


class AccessLevel(IntEnum):
    """Four-element access level lattice: NONE < READ < WRITE < ADMIN."""

    NONE = 0
    READ = 1
    WRITE = 2
    ADMIN = 3


@dataclass(frozen=True)
class Capability:
    """An immutable (resource, access) pair representing a single capability."""

    resource: str
    access: AccessLevel

    def subsumes(self, other: Capability) -> bool:
        """Check if this capability subsumes (covers) another capability."""
        return self.resource == other.resource and self.access >= other.access


class CapabilitySet:
    """A set of capabilities keyed by resource, enforcing least-privilege."""

    def __init__(self) -> None:
        self._caps: dict[str, Capability] = {}

    @classmethod
    def from_list(cls, caps: list[Capability]) -> CapabilitySet:
        """Create a CapabilitySet from a list of capabilities."""
        cs = cls()
        for cap in caps:
            cs.add(cap)
        return cs

    def add(self, cap: Capability) -> None:
        """Add a capability, keeping the highest access level per resource."""
        existing = self._caps.get(cap.resource)
        if existing is None or cap.access > existing.access:
            self._caps[cap.resource] = cap

    def permits(self, required: Capability) -> bool:
        """Check if this capability set permits a required capability."""
        declared = self._caps.get(required.resource)
        if declared is None:
            return False
        return declared.subsumes(required)

    def is_subset_of(self, other: CapabilitySet) -> bool:
        """Check if every capability in this set is permitted by another."""
        for cap in self._caps.values():
            if not other.permits(cap):
                return False
        return True

    def violations_against(self, declared: CapabilitySet) -> list[Capability]:
        """Return capabilities in this set that exceed the declared set."""
        violations: list[Capability] = []
        for cap in self._caps.values():
            if not declared.permits(cap):
                violations.append(cap)
        return violations

    def __len__(self) -> int:
        return len(self._caps)

    def __iter__(self) -> Iterator[Capability]:
        return iter(self._caps.values())

    def __contains__(self, item: object) -> bool:
        if not isinstance(item, Capability):
            return False
        stored = self._caps.get(item.resource)
        return stored is not None and stored == item


__all__ = ["AccessLevel", "Capability", "CapabilitySet"]
