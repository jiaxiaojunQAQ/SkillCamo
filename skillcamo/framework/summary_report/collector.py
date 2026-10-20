# Copyright 2026
#
# Data extraction from existing result structures into SummaryReportData.

"""
Collects and normalizes data from different result sources:

1. UnifiedScanResult / dict  — single scan (direct_scan, phased scan)
2. BatchResult               — adversarial batch testing
3. list[UnifiedScanResult | dict] — batch collect-safe scan
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .consistency import ConsistencyAnalyzer
from .models import (
    OverallVerdict,
    PerScannerStats,
    SummaryReportData,
)

if TYPE_CHECKING:
    from ..models import UnifiedScanResult
    from ..pipeline.batch_result import BatchResult

logger = logging.getLogger(__name__)

SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]

# Severities that represent "no finding" — excluded from finding counts and severity tables
NON_FINDING_SEVERITIES = frozenset({"SAFE", "UNKNOWN"})


class SummaryDataCollector:
    """Collects and normalizes data from different result sources."""

    @staticmethod
    def from_unified_scan_result(
        result: UnifiedScanResult | dict,
        run_id: str | None = None,
    ) -> SummaryReportData:
        """Build report data from a single UnifiedScanResult.

        Used after direct_scan or phased scan workflows.
        """
        if isinstance(result, dict):
            return SummaryDataCollector._from_scan_dict(result, run_id)

        return SummaryDataCollector._from_scan_dict(result.to_dict(), run_id)

    @staticmethod
    def from_batch_result(result: BatchResult) -> SummaryReportData:
        """Build report data from a BatchResult.

        Used after adversarial batch testing.
        """
        stats = result.get_statistics()
        overview = stats["overview"]
        by_scanner = stats["by_scanner"]
        by_generator = stats["by_generator"]

        # Build per-scanner stats
        scanner_stats = SummaryDataCollector._build_scanner_stats_from_batch(
            by_scanner, result.skill_results
        )

        # Aggregate severity distribution (exclude non-finding severities)
        severity_dist: dict[str, int] = {}
        per_scanner_sev: dict[str, dict[str, int]] = {}
        for scanner_name, scanner_s in by_scanner.items():
            sev_counts = scanner_s.get("severity_counts", {})
            # Filter out non-finding severities (SAFE, UNKNOWN)
            filtered_sev = {k: v for k, v in sev_counts.items() if k not in NON_FINDING_SEVERITIES}
            per_scanner_sev[scanner_name] = filtered_sev
            for sev, count in filtered_sev.items():
                severity_dist[sev] = severity_dist.get(sev, 0) + count

        # Overall verdict
        total_skills = overview["total_skills"]
        errored = overview["errored"]
        # For adversarial testing — reflect scanner's detection verdict:
        #   "detected"  = scanner flagged the skill → unsafe
        #   "bypassed"  = scanner did NOT flag it (missed the attack) → safe
        #   "clean"     = direct_scan clean → safe
        unsafe = sum(
            1 for r in result.skill_results
            if r.final_outcome == "detected"
        )
        safe = sum(
            1 for r in result.skill_results
            if r.final_outcome in ("bypassed", "clean") and not r.error
        )
        total_findings = sum(
            s.total_findings for s in scanner_stats
        )

        # Cross-scanner consistency
        verdicts = ConsistencyAnalyzer.build_verdicts_from_batch_skill_results(
            result.skill_results
        )
        consistency = ConsistencyAnalyzer.analyze(verdicts)

        # Generators used
        generators = sorted(by_generator.keys()) if by_generator else []

        # Duration
        duration = result.duration_seconds

        return SummaryReportData(
            report_title="Adversarial Batch Summary",
            run_id=result.batch_id,
            timestamp=result.start_time.strftime("%Y-%m-%d %H:%M:%S"),
            duration_seconds=duration,
            overall_verdict=OverallVerdict(
                is_safe=unsafe == 0 and errored == 0,
                total_findings=total_findings,
                total_skills_scanned=total_skills,
                safe_skills=safe,
                unsafe_skills=unsafe,
                error_skills=errored,
                severity_distribution=severity_dist,
            ),
            scanner_stats=scanner_stats,
            severity_distribution=severity_dist,
            per_scanner_severity=per_scanner_sev,
            consistency=consistency,
            scanners_used=sorted(by_scanner.keys()) if by_scanner else [],
            generators_used=generators,
        )

    @staticmethod
    def from_scan_results_list(
        results: list[UnifiedScanResult | dict],
        run_id: str | None = None,
    ) -> SummaryReportData:
        """Build report data from a list of scan results (collect-safe workflow).

        Aggregates across all skills to produce unified stats.
        """
        if not results:
            return SummaryReportData(
                run_id=run_id or "empty",
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )

        # Normalize to dicts
        dicts: list[dict[str, Any]] = []
        for r in results:
            if isinstance(r, dict):
                dicts.append(r)
            else:
                dicts.append(r.to_dict())

        # Aggregate severity and per-scanner data
        total_findings = 0
        severity_dist: dict[str, int] = {}
        per_scanner_sev: dict[str, dict[str, int]] = {}
        scanner_agg: dict[str, dict[str, Any]] = {}
        safe_count = 0
        unsafe_count = 0
        error_count = 0
        total_duration_ms = 0.0

        for rd in dicts:
            summary = rd.get("summary", {})
            is_safe = summary.get("is_safe")
            findings_count = summary.get("total_findings", 0)
            duration_ms = summary.get("scan_duration_ms", 0)
            total_findings += findings_count
            total_duration_ms += duration_ms or 0

            has_failed_scanner = bool(summary.get("scanners_failed"))
            has_error_summary = any(
                ss.get("status") == "failed" or ss.get("is_safe") is None
                for ss in summary.get("scanner_summaries", [])
            )

            if has_failed_scanner or has_error_summary or is_safe is None:
                error_count += 1
            elif is_safe is True:
                safe_count += 1
            elif is_safe is False:
                unsafe_count += 1
            else:
                error_count += 1

            # Severity distribution
            for sev, count in summary.get("findings_by_severity", {}).items():
                severity_dist[sev] = severity_dist.get(sev, 0) + count

            # Per-scanner summaries
            for ss in summary.get("scanner_summaries", []):
                name = ss.get("scanner_name", "unknown")
                status = ss.get("status", "unknown")

                entry = scanner_agg.setdefault(name, {
                    "detected": 0, "clean": 0, "error": 0,
                    "total_findings": 0, "duration_ms": 0.0, "count": 0,
                    "severity_counts": {},
                })
                entry["count"] += 1
                entry["duration_ms"] += ss.get("duration_ms") or 0

                if status == "failed":
                    entry["error"] += 1
                elif ss.get("is_safe") is False:
                    entry["detected"] += 1
                elif ss.get("is_safe") is True:
                    entry["clean"] += 1
                else:
                    entry["error"] += 1

                findings_by_sev = ss.get("findings_by_severity", {})
                entry["total_findings"] += ss.get("total_findings", 0)
                for sev, count in findings_by_sev.items():
                    entry["severity_counts"][sev] = entry["severity_counts"].get(sev, 0) + count
                    per_scanner_sev.setdefault(name, {})[sev] = (
                        per_scanner_sev.get(name, {}).get(sev, 0) + count
                    )

        # Build PerScannerStats list
        scanner_stats = []
        for name, agg in sorted(scanner_agg.items()):
            avg_ms = agg["duration_ms"] / agg["count"] if agg["count"] > 0 else None
            scanner_stats.append(PerScannerStats(
                scanner_name=name,
                detected_count=agg["detected"],
                clean_count=agg["clean"],
                error_count=agg["error"],
                severity_counts=agg["severity_counts"],
                total_findings=agg["total_findings"],
                avg_duration_ms=avg_ms,
            ))

        # Cross-scanner consistency
        verdicts = ConsistencyAnalyzer.build_verdicts_from_scan_results(dicts)
        consistency = ConsistencyAnalyzer.analyze(verdicts)

        # Collect all scanner names
        scanners_used = sorted(scanner_agg.keys())

        return SummaryReportData(
            report_title="Batch Scan Summary",
            run_id=run_id or f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            duration_seconds=total_duration_ms / 1000.0,
            overall_verdict=OverallVerdict(
                is_safe=unsafe_count == 0 and error_count == 0,
                total_findings=total_findings,
                total_skills_scanned=len(dicts),
                safe_skills=safe_count,
                unsafe_skills=unsafe_count,
                error_skills=error_count,
                severity_distribution=severity_dist,
            ),
            scanner_stats=scanner_stats,
            severity_distribution=severity_dist,
            per_scanner_severity=per_scanner_sev,
            consistency=consistency,
            scanners_used=scanners_used,
            generators_used=["direct_scan"],
        )

    # ── Internal helpers ──────────────────────────────────────────────

    @staticmethod
    def _from_scan_dict(result_dict: dict, run_id: str | None = None) -> SummaryReportData:
        """Build from a raw scan result dict."""
        summary = result_dict.get("summary", {})
        is_safe = summary.get("is_safe", True)
        total = summary.get("total_findings", 0)
        duration_ms = summary.get("scan_duration_ms", 0)
        scanners_used = summary.get("scanners_used", [])

        scanner_stats = []
        per_scanner_sev: dict[str, dict[str, int]] = {}
        for ss in summary.get("scanner_summaries", []):
            name = ss.get("scanner_name", "unknown")
            status = ss.get("status", "unknown")
            sev = ss.get("findings_by_severity", {})
            per_scanner_sev[name] = sev

            detected = 0
            clean = 0
            error = 0
            if status == "failed":
                error = 1
            elif ss.get("is_safe") is False:
                detected = 1
            elif ss.get("is_safe") is True:
                clean = 1

            scanner_stats.append(PerScannerStats(
                scanner_name=name,
                detected_count=detected,
                clean_count=clean,
                error_count=error,
                severity_counts=sev,
                total_findings=ss.get("total_findings", 0),
                avg_duration_ms=ss.get("duration_ms"),
            ))

        severity_dist = dict(summary.get("findings_by_severity", {}))

        verdicts = ConsistencyAnalyzer.build_verdicts_from_scan_results([result_dict])
        consistency = ConsistencyAnalyzer.analyze(verdicts)

        return SummaryReportData(
            report_title="Security Scan Summary",
            run_id=run_id or f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            duration_seconds=(duration_ms or 0) / 1000.0,
            overall_verdict=OverallVerdict(
                is_safe=is_safe,
                total_findings=total,
                total_skills_scanned=1,
                safe_skills=1 if is_safe else 0,
                unsafe_skills=0 if is_safe else 1,
                error_skills=0,
                severity_distribution=severity_dist,
            ),
            scanner_stats=scanner_stats,
            severity_distribution=severity_dist,
            per_scanner_severity=per_scanner_sev,
            consistency=consistency,
            scanners_used=scanners_used,
            generators_used=["direct_scan"],
        )

    @staticmethod
    def _build_scanner_stats_from_summary(summary: Any) -> list[PerScannerStats]:
        """Build PerScannerStats from a ScanSummary's scanner_summaries."""
        stats = []
        for ss in summary.scanner_summaries:
            status = ss.status if hasattr(ss, "status") else "unknown"
            is_safe = ss.is_safe if hasattr(ss, "is_safe") else None

            detected = 0
            clean = 0
            error = 0
            if status == "failed":
                error = 1
            elif is_safe is False:
                detected = 1
            elif is_safe is True:
                clean = 1

            sev = ss.findings_by_severity if hasattr(ss, "findings_by_severity") else {}
            stats.append(PerScannerStats(
                scanner_name=ss.scanner_name,
                detected_count=detected,
                clean_count=clean,
                error_count=error,
                severity_counts=dict(sev) if sev else {},
                total_findings=ss.total_findings,
                avg_duration_ms=ss.duration_ms,
            ))
        return stats

    @staticmethod
    def _build_scanner_stats_from_batch(
        by_scanner: dict[str, dict[str, Any]],
        skill_results: list,
    ) -> list[PerScannerStats]:
        """Build PerScannerStats from BatchResult's by_scanner stats."""
        stats = []
        for scanner_name, scanner_data in sorted(by_scanner.items()):
            sev_counts = scanner_data.get("severity_counts", {})
            # Filter non-finding severities before passing to stats
            filtered_sev = {k: v for k, v in sev_counts.items() if k not in NON_FINDING_SEVERITIES}

            # Batch-level scanner summaries do not currently retain duration.
            avg_ms = None  # Batch-level scanner stats don't track per-scanner duration easily

            stats.append(PerScannerStats(
                scanner_name=scanner_name,
                detected_count=scanner_data.get("detected", 0),
                clean_count=scanner_data.get("clean", 0),
                error_count=scanner_data.get("error", 0),
                severity_counts=filtered_sev,
                total_findings=sum(filtered_sev.values()),
                avg_duration_ms=avg_ms,
            ))
        return stats

    @staticmethod
    def _extract_per_scanner_severity_from_findings(
        findings: list,
    ) -> dict[str, dict[str, int]]:
        """Group findings by source_scanner and count severities."""
        result: dict[str, dict[str, int]] = {}
        for f in findings:
            scanner = f.source_scanner if hasattr(f, "source_scanner") else f.get("source_scanner", "unknown")
            severity = str(f.severity.value if hasattr(f.severity, "value") else f.get("severity", "INFO"))
            result.setdefault(scanner, {})
            result[scanner][severity] = result[scanner].get(severity, 0) + 1
        return result
