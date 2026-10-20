# Copyright 2026
#
# Shared utility functions for scan result processing.

"""
Shared utilities for scan result processing and detection logic.

This module provides common functions used across the adversarial testing
framework to avoid code duplication and ensure consistent behavior.
"""

from __future__ import annotations

from typing import Any

# Severity order from highest to lowest
SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO", "SAFE"]

# Constant-time lookup for severity comparison
SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITY_ORDER)}

# Severities that indicate detection
DETECTION_SEVERITIES = frozenset(("CRITICAL", "HIGH"))


def is_detected(detected: bool, max_severity: str) -> bool:
    """
    Single source of truth for detection threshold.

    Args:
        detected: Whether the scanner flagged something
        max_severity: Maximum severity level from findings

    Returns:
        True if detected AND severity is at HIGH or CRITICAL level
    """
    return detected and max_severity in DETECTION_SEVERITIES


def was_detected(scan_result: dict[str, Any]) -> bool:
    """
    Check if scan result indicates detection.

    Args:
        scan_result: Scan result dictionary with "scanners" key

    Returns:
        True if any scanner detected a threat at CRITICAL/HIGH level
    """
    if "scanners" not in scan_result:
        return False

    for scanner_data in scan_result["scanners"].values():
        if isinstance(scanner_data, dict):
            if is_detected(scanner_data.get("detected", False), scanner_data.get("max_severity", "SAFE")):
                return True

    return False


def has_scanner_errors(scan_result: dict[str, Any]) -> list[str]:
    """
    Return list of scanner names that produced errors (unable to scan).

    Used by the adversarial pipeline to prevent false bypass declarations
    when a scanner failed technically rather than genuinely missing the threat.

    Args:
        scan_result: Scan result dictionary with "scanners" key

    Returns:
        List of scanner names with error states
    """
    errored = []
    for name, scanner_data in scan_result.get("scanners", {}).items():
        if not isinstance(scanner_data, dict):
            continue
        if scanner_data.get("max_severity") == "ERROR":
            errored.append(name)
            continue
        raw = scanner_data.get("raw_result")
        if isinstance(raw, dict):
            if raw.get("error"):
                errored.append(name)
            elif isinstance(raw.get("metadata"), dict) and raw["metadata"].get("error"):
                errored.append(name)
    return errored


def get_scanner_error_details(scan_result: dict[str, Any]) -> dict[str, dict[str, str]]:
    """
    Return detailed error info for each errored scanner.

    Extracts error message and error type from scanner results, handling
    both the direct-invocation adapter pattern (top-level ``error``) and
    the skill-based adapter pattern (``metadata.error``).

    Args:
        scan_result: Scan result dictionary with "scanners" key

    Returns:
        Mapping of ``{scanner_name: {"error": msg, "error_type": type}}``
        for every scanner whose ``max_severity == "ERROR"``.
    """
    details: dict[str, dict[str, str]] = {}
    for name, scanner_data in scan_result.get("scanners", {}).items():
        if not isinstance(scanner_data, dict):
            continue
        # Only process scanners flagged as errors
        if scanner_data.get("max_severity") != "ERROR":
            continue

        error_msg = "Unknown error"
        error_type = "Unknown"

        raw = scanner_data.get("raw_result")
        if isinstance(raw, dict):
            # Direct-invocation adapters: error at top level
            if raw.get("error"):
                error_msg = str(raw["error"])
                error_type = raw.get("error_type") or "Unknown"
            # Skill-based adapters: error nested in metadata
            elif isinstance(raw.get("metadata"), dict) and raw["metadata"].get("error"):
                meta = raw["metadata"]
                error_msg = str(meta["error"])
                error_type = meta.get("error_type") or "Unknown"

        # Truncate overly long messages
        if len(error_msg) > 300:
            error_msg = error_msg[:300] + "...[truncated]"

        details[name] = {"error": error_msg, "error_type": error_type}
    return details


def get_max_severity(findings: list[dict[str, Any]]) -> str:
    """
    Get maximum severity from findings efficiently.

    Uses O(n) complexity instead of O(n*m) by using constant-time lookup.
    Lower rank value = higher severity (CRITICAL=0, SAFE=5).

    Args:
        findings: List of finding dictionaries with "severity" key

    Returns:
        Maximum severity level, or "SAFE" if no findings
    """
    if not findings:
        return "SAFE"

    severities = (
        f.get("severity", "SAFE")
        for f in findings
        if isinstance(f, dict)
    )

    # Use min() because lower rank = higher severity
    return min(severities, key=lambda s: SEVERITY_RANK.get(s, 999))


def scanner_feedback_to_dict(
    scanner_name: str,
    feedback: Any,
) -> dict[str, Any]:
    """
    Convert scanner feedback object to dictionary for JSON serialization.

    Args:
        scanner_name: Name of the scanner
        feedback: Feedback object (may have __dict__ or be dict-like)

    Returns:
        Dictionary representation of the feedback
    """
    if feedback is None:
        return {
            "scanner_name": scanner_name,
            "detected": False,
            "max_severity": "UNKNOWN",
            "blocked_rules": [],
        }

    if hasattr(feedback, "__dict__"):
        return {
            "scanner_name": scanner_name,
            "detected": getattr(feedback, "detected", False),
            "max_severity": getattr(feedback, "max_severity", "UNKNOWN"),
            "blocked_rules": list(getattr(feedback, "blocked_rules", [])),
        }

    if isinstance(feedback, dict):
        return feedback

    return {"raw": str(feedback)}
