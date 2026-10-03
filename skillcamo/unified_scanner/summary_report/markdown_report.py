# Copyright 2026
#
# Markdown report generation for the summary report.

"""
Generates a comprehensive Markdown summary report with four sections:
1. Overall Security Assessment
2. Scanner Result Summary
3. Severity Distribution
4. Cross-Scanner Consistency Analysis
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .models import SummaryReportData

SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
BAR_CHAR = "\u2588"  # █
MAX_BAR_WIDTH = 40


class MarkdownSummaryReport:
    """Generates the full Markdown summary report."""

    def __init__(self, data: SummaryReportData):
        self.data = data

    def generate(self) -> str:
        """Generate complete Markdown report string."""
        lines: list[str] = []
        lines.extend(self._header())
        lines.extend(self._overall_verdict_section())
        lines.extend(self._scanner_summary_section())
        lines.extend(self._severity_distribution_section())
        lines.extend(self._consistency_section())
        lines.extend(self._footer())
        return "\n".join(lines)

    def save(self, path: Path) -> None:
        """Save Markdown report to file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.generate(), encoding="utf-8")

    # ── Sections ─────────────────────────────────────────────────────

    def _header(self) -> list[str]:
        d = self.data
        duration = self._format_duration(d.duration_seconds)
        return [
            f"# {d.report_title}",
            "",
            f"**Run ID:** `{d.run_id}`",
            f"**Date:** {d.timestamp}",
            f"**Duration:** {duration}",
            f"**Scanners:** {', '.join(d.scanners_used) if d.scanners_used else '-'}",
            "",
            "---",
            "",
        ]

    def _overall_verdict_section(self) -> list[str]:
        v = self.data.overall_verdict
        label = v.verdict_label
        lines: list[str] = [
            "## 1. Overall Security Assessment",
            "",
            f"**Verdict: {label}**",
            "",
            "| Metric | Count |",
            "|--------|-------|",
            f"| Total Skills Scanned | {v.total_skills_scanned} |",
            f"| Safe | {v.safe_skills} |",
            f"| Unsafe | {v.unsafe_skills} |",
            f"| Errors | {v.error_skills} |",
            f"| Total Findings | {v.total_findings} |",
            "",
        ]
        return lines

    def _scanner_summary_section(self) -> list[str]:
        lines: list[str] = [
            "## 2. Scanner Result Summary",
            "",
            "| Scanner | Detected | Clean | Error | Findings | Duration |",
            "|---------|----------|-------|-------|----------|----------|",
        ]

        for s in self.data.scanner_stats:
            dur = f"{s.avg_duration_ms:.0f}ms" if s.avg_duration_ms is not None else "-"
            lines.append(
                f"| {s.scanner_name} | {s.detected_count} | {s.clean_count} | "
                f"{s.error_count} | {s.total_findings} | {dur} |"
            )
        lines.append("")

        # Severity breakdown by scanner
        if self.data.per_scanner_severity:
            lines.append("### Severity Breakdown by Scanner")
            lines.append("")
            header = "| Scanner | " + " | ".join(SEVERITY_ORDER) + " |"
            sep = "|---------|" + "|".join(["-------"] * len(SEVERITY_ORDER)) + "|"
            lines.append(header)
            lines.append(sep)

            for scanner_name in sorted(self.data.per_scanner_severity.keys()):
                sev = self.data.per_scanner_severity[scanner_name]
                cells = [str(sev.get(s, 0)) for s in SEVERITY_ORDER]
                lines.append(f"| {scanner_name} | " + " | ".join(cells) + " |")
            lines.append("")

        return lines

    def _severity_distribution_section(self) -> list[str]:
        dist = self.data.severity_distribution
        if not dist:
            return ["## 3. Severity Distribution", "", "No findings.", ""]

        max_count = max(dist.values()) if dist else 1
        lines: list[str] = [
            "## 3. Severity Distribution",
            "",
            "| Severity | Count | Distribution |",
            "|----------|-------|--------------|",
        ]

        for sev in SEVERITY_ORDER:
            count = dist.get(sev, 0)
            if count == 0:
                continue
            bar_width = int(count / max_count * MAX_BAR_WIDTH) if max_count > 0 else 0
            bar = BAR_CHAR * bar_width
            lines.append(f"| {sev} | {count} | {bar} |")

        lines.append("")
        return lines

    def _consistency_section(self) -> list[str]:
        c = self.data.consistency
        if c is None:
            return [
                "## 4. Cross-Scanner Consistency Analysis",
                "",
                "Skipped: fewer than 2 active scanners.",
                "",
            ]

        lines: list[str] = [
            "## 4. Cross-Scanner Consistency Analysis",
            "",
            f"Overall pairwise agreement rate: **{c.overall_agreement_rate:.1%}**",
            "",
        ]

        # Pairwise agreement matrix
        if c.pairwise_agreements:
            lines.extend([
                "### Pairwise Agreement",
                "",
                "| Scanner A | Scanner B | Agreement | Jaccard | Co-Det | Co-Clean | N |",
                "|-----------|-----------|-----------|---------|--------|----------|---|",
            ])
            for p in c.pairwise_agreements:
                lines.append(
                    f"| {p.scanner_a} | {p.scanner_b} | "
                    f"{p.agreement_rate:.1%} | {p.jaccard_similarity:.1%} | "
                    f"{p.co_detection_rate:.1%} | {p.co_clean_rate:.1%} | "
                    f"{p.total_comparisons} |"
                )
            lines.append("")

        # Sensitivity ranking
        if c.scanner_sensitivity_ranking:
            lines.extend([
                "### Scanner Sensitivity Ranking",
                "",
                "| Rank | Scanner | Detection Rate |",
                "|------|---------|----------------|",
            ])
            for rank, (scanner, rate) in enumerate(c.scanner_sensitivity_ranking, 1):
                lines.append(f"| {rank} | {scanner} | {rate:.1%} |")
            lines.append("")

        # Per-skill consistency matrix
        if c.per_skill_verdicts:
            all_scanners = sorted({
                s
                for v in c.per_skill_verdicts
                for s in v.scanner_verdicts.keys()
            })
            if all_scanners:
                lines.extend([
                    "### Per-Skill Consistency Matrix",
                    "",
                    "| Skill | " + " | ".join(all_scanners) + " |",
                    "|-------|" + "|".join(["------"] * len(all_scanners)) + "|",
                ])
                for v in c.per_skill_verdicts:
                    cells = []
                    for s in all_scanners:
                        verdict = v.scanner_verdicts.get(s, "-")
                        if verdict == "detected":
                            cells.append("**DETECTED**")
                        elif verdict == "clean":
                            cells.append("clean")
                        elif verdict == "error":
                            cells.append("error")
                        else:
                            cells.append("-")
                    lines.append(f"| {v.skill_name} | " + " | ".join(cells) + " |")
                lines.append("")

        return lines

    def _footer(self) -> list[str]:
        return [
            "",
            "---",
            f"*Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} by summary_report module*",
            "",
        ]

    # ── Utilities ────────────────────────────────────────────────────

    @staticmethod
    def _format_duration(seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"
