# Copyright 2026
#
# Top-level summary report orchestrator.

"""
Public API for generating end-of-run summary reports.

Usage::

    from skillcamo.framework.summary_report import SummaryReportGenerator

    gen = SummaryReportGenerator(title="My Report")
    data = gen.render(result, output_path=Path("report.md"))

Accepts:
- UnifiedScanResult / dict          — single scan
- BatchResult                        — adversarial batch testing
- list[UnifiedScanResult | dict]     — batch collect-safe scan
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Union

from .collector import SummaryDataCollector
from .console_report import ConsoleSummaryReport
from .markdown_report import MarkdownSummaryReport
from .models import SummaryReportData

logger = logging.getLogger(__name__)


class SummaryReportGenerator:
    """Top-level entry point for generating end-of-run summary reports.

    Auto-detects result type, collects data, and renders both Markdown
    file and Rich Console output.
    """

    def __init__(self, title: str = "Security Scan Summary"):
        self.title = title

    def generate_from_scan_result(
        self,
        result: Any,
        run_id: str | None = None,
    ) -> SummaryReportData:
        """Collect data from a single scan result (UnifiedScanResult or dict)."""
        data = SummaryDataCollector.from_unified_scan_result(result, run_id=run_id)
        data.report_title = self.title
        return data

    def generate_from_batch_result(
        self,
        result: Any,
    ) -> SummaryReportData:
        """Collect data from a BatchResult."""
        data = SummaryDataCollector.from_batch_result(result)
        data.report_title = self.title
        return data

    def generate_from_scan_results(
        self,
        results: list,
        run_id: str | None = None,
    ) -> SummaryReportData:
        """Collect data from a list of scan results."""
        data = SummaryDataCollector.from_scan_results_list(results, run_id=run_id)
        data.report_title = self.title
        return data

    def render_console(self, data: SummaryReportData) -> None:
        """Print Rich console report."""
        ConsoleSummaryReport(data).print()

    def render_markdown(self, data: SummaryReportData) -> str:
        """Return Markdown string."""
        return MarkdownSummaryReport(data).generate()

    def save_markdown(self, data: SummaryReportData, path: Path) -> None:
        """Save Markdown report to file."""
        MarkdownSummaryReport(data).save(path)
        logger.info(f"Summary report saved to: {path}")

    def render(
        self,
        result: Any,
        output_path: Path | None = None,
        show_console: bool = True,
    ) -> SummaryReportData:
        """Convenience method: detect type, collect data, render both outputs.

        Args:
            result: Any supported result type (UnifiedScanResult, dict,
                    BatchResult, or list of scan results).
            output_path: If provided, save Markdown file here.
            show_console: If True, print Rich console output.

        Returns:
            The collected SummaryReportData for programmatic use.
        """
        data = self._collect(result)

        if show_console:
            self.render_console(data)

        if output_path is not None:
            self.save_markdown(data, output_path)

        return data

    def _collect(self, result: Any) -> SummaryReportData:
        """Auto-detect result type and collect data."""
        # Import here to avoid circular imports
        from ..models import UnifiedScanResult
        try:
            from ..pipeline.batch_result import BatchResult
        except ImportError:
            BatchResult = None

        if BatchResult is not None and isinstance(result, BatchResult):
            return self.generate_from_batch_result(result)
        elif isinstance(result, UnifiedScanResult):
            return self.generate_from_scan_result(result)
        elif isinstance(result, dict):
            return self.generate_from_scan_result(result)
        elif isinstance(result, list):
            return self.generate_from_scan_results(result)
        else:
            raise TypeError(f"Unsupported result type: {type(result)}")
