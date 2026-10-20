# Copyright 2026
#
# Intermediate data models for the summary report.

"""
Intermediate data models bridging domain models and report rendering.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PerScannerStats:
    """Aggregated statistics for one scanner across all skills/iterations."""

    scanner_name: str
    detected_count: int = 0
    clean_count: int = 0
    error_count: int = 0
    severity_counts: dict[str, int] = field(default_factory=dict)
    total_findings: int = 0
    avg_duration_ms: float | None = None

    @property
    def total_scanned(self) -> int:
        return self.detected_count + self.clean_count + self.error_count


@dataclass
class OverallVerdict:
    """Overall security assessment."""

    is_safe: bool
    total_findings: int
    total_skills_scanned: int
    safe_skills: int = 0
    unsafe_skills: int = 0
    error_skills: int = 0
    severity_distribution: dict[str, int] = field(default_factory=dict)

    @property
    def verdict_label(self) -> str:
        return "SAFE" if self.is_safe else "UNSAFE"


@dataclass
class ScannerPairAgreement:
    """Agreement metrics for a pair of scanners."""

    scanner_a: str
    scanner_b: str
    agreement_rate: float = 0.0
    co_detection_rate: float = 0.0
    co_clean_rate: float = 0.0
    jaccard_similarity: float = 0.0
    total_comparisons: int = 0


@dataclass
class PerSkillScannerVerdict:
    """Per-skill, per-scanner detection verdict for the consistency matrix."""

    skill_name: str
    scanner_verdicts: dict[str, str] = field(default_factory=dict)
    # scanner_name -> "detected" | "clean" | "error" | "skipped"


@dataclass
class ConsistencyAnalysis:
    """Full cross-scanner consistency analysis."""

    pairwise_agreements: list[ScannerPairAgreement] = field(default_factory=list)
    per_skill_verdicts: list[PerSkillScannerVerdict] = field(default_factory=list)
    overall_agreement_rate: float = 0.0
    most_disagreeable_pair: tuple[str, str] | None = None
    scanner_sensitivity_ranking: list[tuple[str, float]] = field(default_factory=list)
    # (scanner_name, detection_rate) sorted descending


@dataclass
class SummaryReportData:
    """Complete data bundle for the summary report."""

    report_title: str = "Security Scan Summary"
    run_id: str = ""
    timestamp: str = ""
    duration_seconds: float = 0.0

    # Section 1: Overall Verdict
    overall_verdict: OverallVerdict = field(default_factory=lambda: OverallVerdict(is_safe=True, total_findings=0, total_skills_scanned=0))

    # Section 2: Per-Scanner Summary
    scanner_stats: list[PerScannerStats] = field(default_factory=list)

    # Section 3: Severity Distribution
    severity_distribution: dict[str, int] = field(default_factory=dict)
    per_scanner_severity: dict[str, dict[str, int]] = field(default_factory=dict)

    # Section 4: Cross-Scanner Consistency
    consistency: ConsistencyAnalysis | None = None

    # Metadata
    scanners_used: list[str] = field(default_factory=list)
    generators_used: list[str] = field(default_factory=list)
