# Copyright 2026
#
# Summary report module — public API.

"""
Summary report generation for skill security scanning.

Generates comprehensive end-of-run reports with:
- Overall security assessment
- Per-scanner result summary
- Severity distribution
- Cross-scanner consistency analysis

Output formats: Markdown file + Rich Console.
"""

from .collector import SummaryDataCollector
from .consistency import ConsistencyAnalyzer
from .models import (
    ConsistencyAnalysis,
    OverallVerdict,
    PerScannerStats,
    PerSkillScannerVerdict,
    ScannerPairAgreement,
    SummaryReportData,
)
from .summary_report import SummaryReportGenerator

__all__ = [
    "SummaryReportGenerator",
    "SummaryReportData",
    "SummaryDataCollector",
    "ConsistencyAnalyzer",
    "PerScannerStats",
    "OverallVerdict",
    "ScannerPairAgreement",
    "PerSkillScannerVerdict",
    "ConsistencyAnalysis",
]
