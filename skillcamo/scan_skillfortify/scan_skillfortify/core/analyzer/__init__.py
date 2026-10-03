"""Data models for the static analyzer: Severity, Finding, AnalysisResult.

This is a minimal copy for integration into unified_scanner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from scan_skillfortify.core.capabilities import CapabilitySet


class Severity(IntEnum):
    """Four-level severity scale for analysis findings."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass(frozen=True)
class Finding:
    """A single security finding produced by the static analyzer."""

    skill_name: str
    severity: Severity
    message: str
    attack_class: str
    finding_type: str
    evidence: str
    file_path: str | None = None
    line_number: int | None = None


@dataclass
class AnalysisResult:
    """The complete result of analyzing a single skill."""

    skill_name: str
    is_safe: bool
    findings: list[Finding] = field(default_factory=list)
    inferred_capabilities: CapabilitySet | None = None

    @property
    def max_severity(self) -> Severity | None:
        """Return the highest severity among all findings, or None if safe."""
        if not self.findings:
            return None
        return max(f.severity for f in self.findings)


__all__ = ["Severity", "Finding", "AnalysisResult"]
