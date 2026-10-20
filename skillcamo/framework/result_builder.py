"""标准扫描结果构造工具。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from .models import (
        BatchScanResult,
        BatchScanSummary,
        SCANNER_DISPLAY_NAMES,
        ScannerSummary,
        ScanSummary,
        Severity,
        UnifiedScanResult,
    )
    from .scanner_status import extract_findings_from_scanner
except ImportError:
    from models import (  # type: ignore[import-not-found,no-redef]
        BatchScanResult,
        BatchScanSummary,
        SCANNER_DISPLAY_NAMES,
        ScannerSummary,
        ScanSummary,
        Severity,
        UnifiedScanResult,
    )
    from scanner_status import extract_findings_from_scanner  # type: ignore[import-not-found,no-redef]


def build_error_result(skill_path: Path, message: str, error_type: str) -> dict[str, Any]:
    """构建标准化错误结果。"""
    summary = ScanSummary(
        total_findings=0,
        critical=0,
        high=0,
        medium=0,
        low=0,
        info=0,
        is_safe=False,
        scan_duration_ms=0,
        scanners_used=[],
        scanners_failed=[],
        scanner_summaries=[],
    )
    result = UnifiedScanResult(
        skill_path=str(skill_path),
        findings=[],
        summary=summary,
        scanner_results={},
    ).to_dict()
    result["error"] = message
    result["error_type"] = error_type
    return result


def calculate_summary(
    scanner_results: dict[str, dict],
    duration_ms: int,
) -> ScanSummary:
    """根据各扫描器原始结果构建标准摘要。"""
    scanner_findings: dict[str, list[Any]] = {}
    scanners_used = []
    scanners_failed = []
    scanner_summaries = []

    for scanner_name, result in scanner_results.items():
        if scanner_name.startswith("_"):
            continue

        display_name = SCANNER_DISPLAY_NAMES.get(scanner_name, scanner_name)

        if result.get("error"):
            scanners_failed.append(scanner_name)
            scanner_summaries.append(
                ScannerSummary(
                    scanner_name=scanner_name,
                    display_name=display_name,
                    total_findings=0,
                    critical=0,
                    high=0,
                    medium=0,
                    low=0,
                    info=0,
                    is_safe=None,
                    status="failed",
                    duration_ms=None,
                )
            )
            continue

        if result.get("skipped"):
            scanner_summaries.append(
                ScannerSummary(
                    scanner_name=scanner_name,
                    display_name=display_name,
                    total_findings=0,
                    critical=0,
                    high=0,
                    medium=0,
                    low=0,
                    info=0,
                    is_safe=None,
                    status="skipped",
                    duration_ms=None,
                )
            )
            continue

        scanners_used.append(scanner_name)
        findings = extract_findings_from_scanner(scanner_name, result)
        scanner_findings[scanner_name] = findings

        sc_critical = sum(1 for f in findings if f.severity == Severity.CRITICAL)
        sc_high = sum(1 for f in findings if f.severity == Severity.HIGH)
        sc_medium = sum(1 for f in findings if f.severity == Severity.MEDIUM)
        sc_low = sum(1 for f in findings if f.severity == Severity.LOW)
        sc_info = sum(1 for f in findings if f.severity == Severity.INFO)

        scanner_summaries.append(
            ScannerSummary(
                scanner_name=scanner_name,
                display_name=display_name,
                total_findings=len(findings),
                critical=sc_critical,
                high=sc_high,
                medium=sc_medium,
                low=sc_low,
                info=sc_info,
                is_safe=(sc_critical == 0 and sc_high == 0),
                status="success",
                duration_ms=result.get("metadata", {}).get("duration_ms"),
            )
        )

    all_findings: list[Any] = []
    for findings in scanner_findings.values():
        all_findings.extend(findings)

    critical = sum(1 for f in all_findings if f.severity == Severity.CRITICAL)
    high = sum(1 for f in all_findings if f.severity == Severity.HIGH)
    medium = sum(1 for f in all_findings if f.severity == Severity.MEDIUM)
    low = sum(1 for f in all_findings if f.severity == Severity.LOW)
    info = sum(1 for f in all_findings if f.severity == Severity.INFO)

    if not scanners_used:
        is_safe = None
    else:
        is_safe = (critical == 0 and high == 0)

    return ScanSummary(
        total_findings=len(all_findings),
        critical=critical,
        high=high,
        medium=medium,
        low=low,
        info=info,
        is_safe=is_safe,
        scan_duration_ms=duration_ms,
        scanners_used=scanners_used,
        scanners_failed=scanners_failed,
        scanner_summaries=scanner_summaries,
    )


def build_unified_scan_result(
    skill_path: Path,
    scanner_results: dict[str, dict],
    summary: ScanSummary,
) -> dict[str, Any]:
    """将原始扫描器结果转换为统一结果结构。"""
    normalized_results = {
        k: v for k, v in scanner_results.items() if not k.startswith("_")
    }
    findings: list[dict[str, Any]] = []
    for scanner_name, scanner_result in normalized_results.items():
        findings.extend(
            finding.to_dict()
            for finding in extract_findings_from_scanner(scanner_name, scanner_result)
        )

    result = UnifiedScanResult(
        skill_path=str(skill_path),
        findings=findings,
        summary=summary,
        scanner_results=normalized_results,
    ).to_dict()
    result["findings"] = findings
    return result


def build_batch_result(
    results: list[dict[str, Any]],
    *,
    target_type: str,
    target_path: str | Path | None = None,
) -> dict[str, Any]:
    """构建标准化批量结果。"""
    safe_items = 0
    unsafe_items = 0
    error_items = 0
    total_findings = 0

    for result in results:
        summary = result.get("summary", {})
        total_findings += summary.get("total_findings", 0)
        if result.get("error"):
            error_items += 1
            continue
        is_safe = summary.get("is_safe")
        if is_safe is True:
            safe_items += 1
        elif is_safe is False:
            unsafe_items += 1
        else:
            # is_safe is None（无法判定）归入 error
            error_items += 1

    batch_result = BatchScanResult(
        target_type=target_type,
        target_path=str(target_path if target_path is not None else ""),
        items=results,
        summary=BatchScanSummary(
            total_items=len(results),
            safe_items=safe_items,
            unsafe_items=unsafe_items,
            error_items=error_items,
            total_findings=total_findings,
        ),
    )
    return batch_result.to_dict()
