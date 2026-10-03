# Copyright 2026
#
# Rich Console report generation for the summary report.

"""
Renders a comprehensive summary report to the terminal using Rich:

1. Overall Security Assessment (Panel)
2. Scanner Result Summary (Table)
3. Severity Distribution (Table with bar chart)
4. Cross-Scanner Consistency Analysis (Tables)
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import SummaryReportData

SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
BAR_CHAR = "\u2588"  # █
MAX_BAR_WIDTH = 30

# Rich style mapping
SEVERITY_STYLES = {
    "CRITICAL": "bold red",
    "HIGH": "bright_red",
    "MEDIUM": "yellow",
    "LOW": "blue",
    "INFO": "dim",
}

VERDICT_STYLES = {
    "detected": "bold red",
    "clean": "green",
    "error": "yellow",
    "skipped": "dim",
}


class ConsoleSummaryReport:
    """Renders the summary report to the terminal via Rich."""

    def __init__(self, data: SummaryReportData, console: Console | None = None):
        self.data = data
        self.console = console or Console()

    def print(self) -> None:
        """Print full report to console."""
        self._print_header()
        self._print_overall_verdict()
        self._print_scanner_summary()
        self._print_severity_distribution()
        self._print_consistency()

    # ── Sections ─────────────────────────────────────────────────────

    def _print_header(self) -> None:
        d = self.data
        duration = self._format_duration(d.duration_seconds)
        self.console.print()
        self.console.print(
            Panel(
                f"[bold]{d.report_title}[/bold]\n\n"
                f"Run ID: [cyan]{d.run_id}[/cyan]\n"
                f"Date: {d.timestamp}\n"
                f"Duration: {duration}\n"
                f"Scanners: {', '.join(d.scanners_used) if d.scanners_used else '-'}",
                title="Summary Report",
                border_style="cyan",
            )
        )
        self.console.print()

    def _print_overall_verdict(self) -> None:
        v = self.data.overall_verdict
        label = v.verdict_label
        color = "green" if v.is_safe else "bold red"

        table = Table(title="1. Overall Security Assessment", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        table.add_row("Verdict", f"[{color}]{label}[/{color}]")
        table.add_row("Total Skills", str(v.total_skills_scanned))
        table.add_row("Safe", f"[green]{v.safe_skills}[/green]")
        table.add_row("Unsafe", f"[red]{v.unsafe_skills}[/red]" if v.unsafe_skills > 0 else str(v.unsafe_skills))
        table.add_row("Errors", f"[yellow]{v.error_skills}[/yellow]" if v.error_skills > 0 else str(v.error_skills))
        table.add_row("Total Findings", str(v.total_findings))

        self.console.print(table)
        self.console.print()

    def _print_scanner_summary(self) -> list[str]:
        table = Table(title="2. Scanner Result Summary", show_header=True, header_style="bold cyan")
        table.add_column("Scanner", style="cyan")
        table.add_column("Detected", justify="right")
        table.add_column("Clean", justify="right")
        table.add_column("Error", justify="right")
        table.add_column("Findings", justify="right")
        table.add_column("Duration", justify="right")

        for s in self.data.scanner_stats:
            det_str = f"[red]{s.detected_count}[/red]" if s.detected_count > 0 else "0"
            clean_str = f"[green]{s.clean_count}[/green]" if s.clean_count > 0 else "0"
            err_str = f"[yellow]{s.error_count}[/yellow]" if s.error_count > 0 else "0"
            dur = f"{s.avg_duration_ms:.0f}ms" if s.avg_duration_ms is not None else "-"

            table.add_row(s.scanner_name, det_str, clean_str, err_str, str(s.total_findings), dur)

        self.console.print(table)
        self.console.print()

        # Severity breakdown
        if self.data.per_scanner_severity:
            sev_table = Table(title="Severity Breakdown by Scanner", show_header=True, header_style="bold cyan")
            sev_table.add_column("Scanner", style="cyan")
            for sev in SEVERITY_ORDER:
                sev_table.add_column(sev, justify="right", style=SEVERITY_STYLES.get(sev, ""))

            for scanner_name in sorted(self.data.per_scanner_severity.keys()):
                sev = self.data.per_scanner_severity[scanner_name]
                cells = [str(sev.get(s, 0)) for s in SEVERITY_ORDER]
                sev_table.add_row(scanner_name, *cells)

            self.console.print(sev_table)
            self.console.print()

    def _print_severity_distribution(self) -> list[str]:
        dist = self.data.severity_distribution
        if not dist:
            self.console.print("[dim]No severity data to display.[/dim]")
            self.console.print()
            return

        max_count = max(dist.values()) if dist else 1

        table = Table(title="3. Severity Distribution", show_header=True, header_style="bold cyan")
        table.add_column("Severity", style="bold")
        table.add_column("Count", justify="right")
        table.add_column("Distribution", min_width=MAX_BAR_WIDTH + 2)

        for sev in SEVERITY_ORDER:
            count = dist.get(sev, 0)
            if count == 0 and sev not in dist:
                continue
            bar_width = int(count / max_count * MAX_BAR_WIDTH) if max_count > 0 else 0
            style = SEVERITY_STYLES.get(sev, "")
            bar_text = Text(BAR_CHAR * bar_width, style=style)
            table.add_row(sev, str(count), bar_text)

        self.console.print(table)
        self.console.print()

    def _print_consistency(self) -> None:
        c = self.data.consistency
        if c is None:
            self.console.print("[dim]4. Cross-Scanner Consistency: skipped (fewer than 2 active scanners)[/dim]")
            self.console.print()
            return

        self.console.print(f"[bold cyan]4. Cross-Scanner Consistency Analysis[/bold cyan]")
        self.console.print(f"Overall pairwise agreement: [bold]{c.overall_agreement_rate:.1%}[/bold]")
        self.console.print()

        # Pairwise agreement table
        if c.pairwise_agreements:
            table = Table(title="Pairwise Agreement", show_header=True, header_style="bold cyan")
            table.add_column("Scanner A", style="cyan")
            table.add_column("Scanner B", style="cyan")
            table.add_column("Agreement", justify="right")
            table.add_column("Jaccard", justify="right")
            table.add_column("Co-Det", justify="right")
            table.add_column("Co-Clean", justify="right")
            table.add_column("N", justify="right")

            for p in c.pairwise_agreements:
                agreement_color = "green" if p.agreement_rate >= 0.8 else ("yellow" if p.agreement_rate >= 0.5 else "red")
                table.add_row(
                    p.scanner_a, p.scanner_b,
                    f"[{agreement_color}]{p.agreement_rate:.1%}[/{agreement_color}]",
                    f"{p.jaccard_similarity:.1%}",
                    f"{p.co_detection_rate:.1%}",
                    f"{p.co_clean_rate:.1%}",
                    str(p.total_comparisons),
                )
            self.console.print(table)
            self.console.print()

        # Sensitivity ranking
        if c.scanner_sensitivity_ranking:
            table = Table(title="Scanner Sensitivity Ranking", show_header=True, header_style="bold cyan")
            table.add_column("Rank", justify="right", style="bold")
            table.add_column("Scanner", style="cyan")
            table.add_column("Detection Rate", justify="right")

            for rank, (scanner, rate) in enumerate(c.scanner_sensitivity_ranking, 1):
                rate_color = "red" if rate > 0.7 else ("yellow" if rate > 0.3 else "green")
                table.add_row(str(rank), scanner, f"[{rate_color}]{rate:.1%}[/{rate_color}]")

            self.console.print(table)
            self.console.print()

        # Per-skill consistency matrix
        if c.per_skill_verdicts:
            all_scanners = sorted({
                s
                for v in c.per_skill_verdicts
                for s in v.scanner_verdicts.keys()
            })
            if all_scanners:
                table = Table(title="Per-Skill Consistency Matrix", show_header=True, header_style="bold cyan")
                table.add_column("Skill", style="cyan", max_width=30)
                for s in all_scanners:
                    table.add_column(s, justify="center")

                for v in c.per_skill_verdicts:
                    cells = []
                    for s in all_scanners:
                        verdict = v.scanner_verdicts.get(s, "skipped")
                        style = VERDICT_STYLES.get(verdict, "dim")
                        display = verdict.upper() if verdict == "detected" else verdict
                        cells.append(f"[{style}]{display}[/{style}]")
                    table.add_row(v.skill_name[:30], *cells)

                self.console.print(table)
                self.console.print()

    # ── Utilities ────────────────────────────────────────────────────

    @staticmethod
    def _format_duration(seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"
