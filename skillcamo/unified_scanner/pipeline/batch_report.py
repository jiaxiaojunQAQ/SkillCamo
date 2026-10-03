# Copyright 2026
#
# Report generation utilities for batch execution.

"""
Report generation utilities for batch execution.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

from .batch_result import BatchResult

from skillcamo.output_paths import OutputPathsConfig

logger = logging.getLogger(__name__)
console = Console()


class BatchReportGenerator:
    """批量执行报告生成器。"""

    def __init__(self, result: BatchResult, verbose: bool = False):
        self.result = result
        self.verbose = verbose

    def generate_json(self) -> str:
        data = {
            "statistics": self.result.get_statistics(),
            "global_settings": self.result.global_settings,
            "skills": [],
        }

        for skill_result in self.result.skill_results:
            skill_data = skill_result.to_dict()

            if self.verbose and skill_result.result:
                skill_data["attempts"] = [
                    {
                        "iteration": a.iteration,
                        "timestamp": a.timestamp.isoformat(),
                        "detected": a.detected,
                        "scan_result": a.scan_result,
                        "analysis": a.analysis,
                    }
                    for a in skill_result.result.attempts
                ]
                skill_data["statistics"] = skill_result.result.get_statistics()

            data["skills"].append(skill_data)

        return json.dumps(data, indent=2, ensure_ascii=False, default=str)

    def generate_markdown(self) -> str:
        lines = [
            "# Adversarial Batch Test Report",
            "",
            f"**Run ID:** `{self.result.batch_id}`",
            f"**Date:** {self.result.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Duration:** {self._format_duration(self.result.duration_seconds)}",
            "",
        ]

        lines.extend([
            "## Configuration",
            "",
            "| Setting | Value |",
            "|---------|-------|",
        ])

        for key, value in self.result.global_settings.items():
            lines.append(f"| {key} | {value} |")
        lines.append("")

        stats = self.result.get_statistics()
        overview = stats["overview"]
        by_generator = stats["by_generator"]
        by_scanner = stats["by_scanner"]

        lines.extend([
            "## Overview",
            "",
            "| Metric | Count |",
            "|--------|-------|",
            f"| Total Skills | {overview['total_skills']} |",
            f"| Tests Completed | {overview['completed']} |",
            f"| Tests Errored | {overview['errored']} |",
            f"| Skipped | {overview['skipped']} |",
            f"| Duration | {self._format_duration(overview['duration_seconds'])} |",
            "",
            "## By Generator",
            "",
            "| Generator | Total | Completed | Errored | Primary Metrics |",
            "|-----------|-------|-----------|---------|-----------------|",
        ])

        for generator, gen_stats in sorted(by_generator.items()):
            if generator == "direct_scan":
                metrics = (
                    f"detected={gen_stats['detected']}, clean={gen_stats['clean']}, "
                    f"detection_rate={gen_stats['detection_rate']:.1%}"
                )
            else:
                metrics = (
                    f"bypassed={gen_stats['bypassed']}, detected={gen_stats['detected']}, "
                    f"avg_iterations={gen_stats['avg_iterations']:.1f}, bypass_rate={gen_stats['bypass_rate']:.1%}"
                )
            lines.append(
                f"| {generator} | {gen_stats['total']} | {gen_stats['completed']} | {gen_stats['errored']} | {metrics} |"
            )
        lines.append("")

        lines.extend([
            "## By Scanner",
            "",
            "| Scanner | Detected | Clean | Error | Severities |",
            "|---------|----------|-------|-------|------------|",
        ])
        if by_scanner:
            for scanner_name, scanner_stats in sorted(by_scanner.items()):
                severity_summary = ", ".join(
                    f"{severity}={count}"
                    for severity, count in sorted(scanner_stats["severity_counts"].items())
                )
                lines.append(
                    f"| {scanner_name} | {scanner_stats['detected']} | {scanner_stats['clean']} | "
                    f"{scanner_stats['error']} | {severity_summary or '-'} |"
                )
        else:
            lines.append("| - | 0 | 0 | 0 | - |")
        lines.append("")

        lines.extend([
            "## Results by Skill",
            "",
            "| Skill | Generator | Status | Outcome | Iterations | Duration |",
            "|-------|-----------|--------|---------|------------|----------|",
        ])

        for r in self.result.skill_results:
            status_icon = self._get_status_icon(r.status)
            outcome = r.final_outcome
            iterations = str(r.result.total_iterations) if r.result else "-"
            duration = self._format_duration(r.duration_seconds)
            name = r.spec.name if hasattr(r.spec, "name") else "unknown"
            lines.append(f"| {name} | {r.generator} | {status_icon} {r.status} | {outcome} | {iterations} | {duration} |")

        if self.verbose:
            lines.extend([
                "",
                "## Detailed Results",
                "",
            ])

            for r in self.result.skill_results:
                name = r.spec.name if hasattr(r.spec, "name") else "unknown"
                lines.extend([
                    f"### {name}",
                    "",
                    f"- **Generator:** {r.generator}",
                    f"- **Status:** {r.status}",
                    f"- **Final Outcome:** {r.final_outcome}",
                    f"- **Duration:** {self._format_duration(r.duration_seconds)}",
                    "",
                ])

                if r.result:
                    lines.append("**Attempts:**")
                    for attempt in r.result.attempts:
                        if r.generator == "direct_scan":
                            detected_str = "Detected" if attempt.detected else "Clean"
                        else:
                            detected_str = "Detected" if attempt.detected else "Bypassed"
                        lines.append(f"  - Iteration {attempt.iteration}: {detected_str}")
                    lines.append("")

                if r.error:
                    lines.extend([
                        "**Error:**",
                        "```",
                        r.error,
                        "```",
                        "",
                    ])

        if self.result.errored > 0:
            lines.extend([
                "",
                "## Errors",
                "",
            ])
            for r in self.result.skill_results:
                if r.error:
                    lines.extend([
                        f"### {r.spec.name if hasattr(r.spec, 'name') else 'unknown'}",
                        "```",
                        r.error,
                        "```",
                        "",
                    ])

        if self.verbose:
            lines.extend([
                "",
                "## Triggered Rules",
                "",
            ])

            all_rules: dict[str, int] = {}
            for r in self.result.skill_results:
                if r.result:
                    for attempt in r.result.attempts:
                        if "scanners" in attempt.scan_result:
                            for scanner_data in attempt.scan_result["scanners"].values():
                                if isinstance(scanner_data, dict):
                                    rules = scanner_data.get("blocked_rules", [])
                                    for rule in rules:
                                        all_rules[rule] = all_rules.get(rule, 0) + 1

            if all_rules:
                lines.append("| Rule | Trigger Count |")
                lines.append("|------|---------------|")
                for rule, count in sorted(all_rules.items(), key=lambda x: -x[1]):
                    lines.append(f"| {rule} | {count} |")
            else:
                lines.append("No rules were triggered.")
            lines.append("")

        lines.extend([
            "",
            "---",
            f"*Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        ])

        return "\n".join(lines)

    def save(
        self,
        output_dir: Optional[Path] = None,
        output_config: Optional["OutputPathsConfig"] = None,
    ) -> list[Path]:
        if output_dir is None and output_config is None:
            raise ValueError("必须提供 output_dir 或 output_config")
        if output_dir is None:
            output_dir = output_config.get_module_dir("adversarial", "json")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        saved_paths = []

        json_path = output_dir / "summary.json"
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(self.generate_json())
        saved_paths.append(json_path)
        logger.info(f"JSON report saved to: {json_path}")

        md_path = output_dir / "summary.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self.generate_markdown())
        saved_paths.append(md_path)
        logger.info(f"Markdown report saved to: {md_path}")

        return saved_paths

    def print_summary(self) -> None:
        stats = self.result.get_statistics()
        overview = stats["overview"]
        by_generator = stats["by_generator"]
        by_scanner = stats["by_scanner"]

        console.print("\n[bold cyan]Batch Execution Summary[/bold cyan]\n")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Value")

        table.add_row("Total Skills", str(overview["total_skills"]))
        table.add_row("Tests Completed", f"[green]{overview['completed']}[/green]")
        table.add_row("Tests Errored", f"[red]{overview['errored']}[/red]" if overview['errored'] > 0 else "Errored: 0")
        table.add_row("Skipped", str(overview["skipped"]))
        table.add_row("Duration", self._format_duration(overview["duration_seconds"]))

        console.print(table)

        generator_table = Table(title="By Generator", show_header=True)
        generator_table.add_column("Generator", style="cyan")
        generator_table.add_column("Total")
        generator_table.add_column("Completed")
        generator_table.add_column("Errored")
        generator_table.add_column("Primary Metrics")
        for generator, gen_stats in sorted(by_generator.items()):
            if generator == "direct_scan":
                metrics = (
                    f"detected={gen_stats['detected']}, clean={gen_stats['clean']}, "
                    f"detection_rate={gen_stats['detection_rate']:.1%}"
                )
            else:
                metrics = (
                    f"bypassed={gen_stats['bypassed']}, detected={gen_stats['detected']}, "
                    f"avg_iter={gen_stats['avg_iterations']:.1f}, bypass_rate={gen_stats['bypass_rate']:.1%}"
                )
            generator_table.add_row(
                generator,
                str(gen_stats["total"]),
                str(gen_stats["completed"]),
                str(gen_stats["errored"]),
                metrics,
            )
        console.print(generator_table)

        scanner_table = Table(title="By Scanner", show_header=True)
        scanner_table.add_column("Scanner", style="cyan")
        scanner_table.add_column("Detected")
        scanner_table.add_column("Clean")
        scanner_table.add_column("Error")
        scanner_table.add_column("Severities")
        if by_scanner:
            for scanner_name, scanner_stats in sorted(by_scanner.items()):
                severity_summary = ", ".join(
                    f"{severity}={count}"
                    for severity, count in sorted(scanner_stats["severity_counts"].items())
                )
                scanner_table.add_row(
                    scanner_name,
                    str(scanner_stats["detected"]),
                    str(scanner_stats["clean"]),
                    str(scanner_stats["error"]),
                    severity_summary or "-",
                )
        else:
            scanner_table.add_row("-", "0", "0", "0", "-")
        console.print(scanner_table)

        console.print("\n[bold]Results by Skill:[/bold]\n")

        result_table = Table(show_header=True)
        result_table.add_column("Skill", style="cyan")
        result_table.add_column("Generator")
        result_table.add_column("Status")
        result_table.add_column("Outcome")
        result_table.add_column("Iterations")
        result_table.add_column("Duration")

        for r in self.result.skill_results:
            status_icon = self._get_status_icon(r.status)
            status_color = "green" if r.status in ("success", "clean") else "red"
            iterations = str(r.result.total_iterations) if r.result else "-"
            duration = self._format_duration(r.duration_seconds)
            name = r.spec.name if hasattr(r.spec, "name") else "unknown"

            result_table.add_row(
                name,
                r.generator,
                f"[{status_color}]{status_icon} {r.status}[/{status_color}]",
                r.final_outcome,
                iterations,
                duration,
            )

        console.print(result_table)
        console.print(f"\n[bold]Output:[/bold] {self.result.output_dir}\n")

    def _format_duration(self, seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"

    def _get_status_icon(self, status: str) -> str:
        icons = {
            "success": "✓",
            "clean": "✓",
            "detected": "!",
            "failed": "✗",
            "error": "⚠",
            "pending": "⋯",
        }
        return icons.get(status, "?")
