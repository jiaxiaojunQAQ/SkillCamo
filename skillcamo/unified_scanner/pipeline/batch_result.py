# Copyright 2026
#
# Result models for batch execution.

"""
Result models for batch execution.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from rich.console import Console
from rich.table import Table

from .result import PipelineResult
from .scan_utils import has_scanner_errors, is_detected

from skillcamo.output_paths import OutputPathsConfig, get_default_output_root


def _default_output_dir() -> Path:
    return get_default_output_root()

logger = logging.getLogger(__name__)


def summarize_final_iteration_scan(scan_result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Summarize scanners from one final iteration result."""
    summary: dict[str, dict[str, Any]] = {}
    scanners = scan_result.get("scanners", {})
    if not isinstance(scanners, dict):
        return summary

    for scanner_name, scanner_data in scanners.items():
        if not isinstance(scanner_data, dict):
            continue
        severity = str(scanner_data.get("max_severity", "UNKNOWN"))
        raw_result = scanner_data.get("raw_result", {})
        has_error = severity == "ERROR"
        if isinstance(raw_result, dict) and (
            raw_result.get("error") or raw_result.get("timed_out")
        ):
            has_error = True

        detected = is_detected(bool(scanner_data.get("detected")), severity)

        entry = summary.setdefault(
            scanner_name,
            {"detected": 0, "clean": 0, "error": 0, "severity_counts": {}},
        )
        if has_error:
            entry["error"] += 1
        elif detected:
            entry["detected"] += 1
        else:
            entry["clean"] += 1

        if severity not in ("SAFE", "UNKNOWN", "ERROR"):
            sev_counts = entry["severity_counts"]
            sev_counts[severity] = sev_counts.get(severity, 0) + 1

    return summary


def evaluate_final_iteration(scan_result: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one final iteration for restore/summary semantics."""
    if not isinstance(scan_result, dict):
        return {
            "scanner_summary": {},
            "conclusive_safe": False,
            "detected": False,
            "has_errors": True,
            "final_outcome": "error",
        }

    scanner_summary = summarize_final_iteration_scan(scan_result)
    no_scanners = bool(scan_result.get("no_scanners_ran"))
    has_errors = no_scanners or bool(has_scanner_errors(scan_result))
    detected = any(
        stats.get("detected", 0) > 0
        for stats in scanner_summary.values()
    )
    conclusive_safe = bool(scanner_summary) and not detected and not has_errors

    if detected:
        final_outcome = "detected"
    elif conclusive_safe:
        final_outcome = "bypassed"
    else:
        final_outcome = "error"

    return {
        "scanner_summary": scanner_summary,
        "conclusive_safe": conclusive_safe,
        "detected": detected,
        "has_errors": has_errors,
        "final_outcome": final_outcome,
    }


@dataclass
class BatchSkillResult:
    """批量执行中单个技能的结果。"""

    spec: Any  # SkillSpec
    success: bool
    generator: str = "SkillCamo"
    result: PipelineResult | None = None
    error: str | None = None
    output_dir: Path | None = None
    scan_detected: bool | None = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None
    # Pre-computed fields restored from state.json
    _cached_final_outcome: str | None = field(default=None, repr=False)
    _cached_scanner_summary: dict[str, dict[str, Any]] | None = field(default=None, repr=False)
    _cached_total_iterations: int | None = field(default=None, repr=False)

    @property
    def duration_seconds(self) -> float:
        """执行时长（秒）。"""
        if self.end_time:
            delta = self.end_time - self.start_time
            return delta.total_seconds()
        return 0.0

    @property
    def status(self) -> str:
        """状态字符串。"""
        if self.error:
            return "error"
        if self.generator == "direct_scan":
            if self.result is not None:
                return "detected" if not self.result.success else "clean"
            return "detected" if self.scan_detected else "clean"
        if self.success:
            return "success"
        if self.result and self.result.success:
            return "success"
        if self.result:
            return "failed"
        return "pending"

    @property
    def final_outcome(self) -> str:
        """统一的最终结果标签。"""
        if self.error:
            return "error"
        if self._cached_final_outcome is not None:
            return self._cached_final_outcome
        if self.generator == "direct_scan":
            if self.result is not None:
                return "detected" if not self.result.success else "clean"
            return "detected" if self.scan_detected else "clean"
        if self.result is None:
            return "pending"
        return "bypassed" if self.result.success else "detected"

    @property
    def scanner_summary(self) -> dict[str, dict[str, Any]]:
        """聚合本 skill 的 scanner 结果（仅取最后一次迭代）。"""
        if self._cached_scanner_summary is not None:
            return self._cached_scanner_summary

        if not self.result or not self.result.attempts:
            return {}

        attempt = self.result.attempts[-1]
        return summarize_final_iteration_scan(attempt.scan_result)

    @property
    def total_iterations(self) -> int:
        """总迭代次数。"""
        if self._cached_total_iterations is not None:
            return self._cached_total_iterations
        return self.result.total_iterations if self.result else 0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        output_dir = self.output_dir
        if output_dir is None and self.result and self.result.final_skill_path:
            output_dir = self.result.final_skill_path.parent.parent

        return {
            "name": self.spec.name if hasattr(self.spec, "name") else "unknown",
            "path": str(self.spec.path) if hasattr(self.spec, "path") and self.spec.path else None,
            "generator": self.generator,
            "status": self.status,
            "success": self.success,
            "final_outcome": self.final_outcome,
            "detected": self.scan_detected,
            "scanner_summary": self.scanner_summary,
            "iterations": self.total_iterations,
            "evals_used": self.result.evals_used if self.result else None,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
            "output_dir": str(output_dir) if output_dir else None,
        }


@dataclass
class BatchResult:
    """批量执行的汇总结果。"""

    batch_id: str
    total_skills: int
    completed: int = 0
    errored: int = 0
    skipped: int = 0
    skill_results: list[BatchSkillResult] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None
    output_dir: Path = field(default_factory=_default_output_dir)

    # 全局配置快照
    global_settings: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        """总执行时长（秒）。"""
        if self.end_time:
            delta = self.end_time - self.start_time
            return delta.total_seconds()
        return 0.0

    def add_result(self, result: BatchSkillResult) -> None:
        """添加单个技能结果。"""
        self.skill_results.append(result)
        if result.success:
            self.completed += 1
        else:
            self.errored += 1

    def mark_skipped(self, spec: Any, reason: str) -> None:
        """标记一个技能为跳过。"""
        result = BatchSkillResult(
            spec=spec,
            success=False,
            error=f"Skipped: {reason}",
        )
        self.skill_results.append(result)
        self.skipped += 1

    def finalize(self) -> None:
        """完成批量运行，设置结束时间。"""
        self.end_time = datetime.now()

    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息。"""
        by_generator: dict[str, dict[str, Any]] = {}
        by_scanner: dict[str, dict[str, Any]] = {}

        for result in self.skill_results:
            generator = result.generator
            gen_stats = by_generator.setdefault(
                generator,
                {
                    "total": 0,
                    "completed": 0,
                    "errored": 0,
                    "bypassed": 0,
                    "detected": 0,
                    "clean": 0,
                    "total_iterations": 0,
                    "avg_iterations": 0.0,
                    "bypass_rate": 0.0,
                    "detection_rate": 0.0,
                },
            )
            gen_stats["total"] += 1
            if result.error:
                gen_stats["errored"] += 1
            else:
                gen_stats["completed"] += 1

            if generator == "direct_scan":
                if result.final_outcome == "detected":
                    gen_stats["detected"] += 1
                elif result.final_outcome == "clean":
                    gen_stats["clean"] += 1
            else:
                gen_stats["total_iterations"] += result.total_iterations
                if result.final_outcome == "bypassed":
                    gen_stats["bypassed"] += 1
                elif result.final_outcome == "detected":
                    gen_stats["detected"] += 1

            for scanner_name, scanner_stats in result.scanner_summary.items():
                entry = by_scanner.setdefault(
                    scanner_name,
                    {
                        "detected": 0,
                        "clean": 0,
                        "error": 0,
                        "severity_counts": {},
                    },
                )
                entry["detected"] += scanner_stats.get("detected", 0)
                entry["clean"] += scanner_stats.get("clean", 0)
                entry["error"] += scanner_stats.get("error", 0)
                sev_counts = entry["severity_counts"]
                for severity, count in scanner_stats.get("severity_counts", {}).items():
                    sev_counts[severity] = sev_counts.get(severity, 0) + count

        for generator, stats in by_generator.items():
            total = stats["total"]
            if total > 0:
                if generator == "direct_scan":
                    stats["detection_rate"] = stats["detected"] / total
                else:
                    stats["avg_iterations"] = stats["total_iterations"] / total
                    stats["detection_rate"] = stats["detected"] / total
                    stats["bypass_rate"] = stats["bypassed"] / total
            stats.pop("total_iterations", None)

        return {
            "batch_id": self.batch_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "overview": {
                "total_skills": self.total_skills,
                "completed": self.completed,
                "errored": self.errored,
                "skipped": self.skipped,
                "duration_seconds": self.duration_seconds,
            },
            "by_generator": by_generator,
            "by_scanner": by_scanner,
        }

    def save_json_report(
        self,
        path: Optional[Path] = None,
        output_config: Optional["OutputPathsConfig"] = None,
        filename: str = "batch_result.json",
    ) -> None:
        """保存 JSON 格式报告。"""
        if path is None and output_config is None:
            raise ValueError("必须提供 path 或 output_config")
        if path is None:
            path = output_config.get_output_path("adversarial", "json", filename)

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        report = {
            "statistics": self.get_statistics(),
            "global_settings": self.global_settings,
            "skills": [r.to_dict() for r in self.skill_results],
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"JSON report saved to: {path}")

    def save_markdown_report(
        self,
        path: Optional[Path] = None,
        output_config: Optional["OutputPathsConfig"] = None,
        filename: str = "batch_result.md",
    ) -> None:
        """保存 Markdown 格式报告。"""
        if path is None and output_config is None:
            raise ValueError("必须提供 path 或 output_config")
        if path is None:
            path = output_config.get_output_path("adversarial", "markdown", filename)

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        stats = self.get_statistics()
        overview = stats["overview"]
        by_generator = stats["by_generator"]
        by_scanner = stats["by_scanner"]

        lines = [
            "# Adversarial Batch Test Report",
            "",
            f"**Run ID:** `{self.batch_id}`",
            f"**Date:** {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Duration:** {self._format_duration(self.duration_seconds)}",
            "",
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
        ]

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

        lines.extend([
            "",
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

        lines.extend([
            "",
            "## Results by Skill",
            "",
            "| Skill | Generator | Status | Outcome | Iterations | Duration |",
            "|-------|-----------|--------|---------|------------|----------|",
        ])

        for r in self.skill_results:
            status_icon = self._get_status_icon(r.status)
            iterations = str(r.total_iterations)
            duration = self._format_duration(r.duration_seconds)
            name = r.spec.name if hasattr(r.spec, "name") else "unknown"
            lines.append(f"| {name} | {r.generator} | {status_icon} {r.status} | {r.final_outcome} | {iterations} | {duration} |")

        if self.errored > 0:
            lines.extend([
                "",
                "## Errors",
                "",
            ])
            for r in self.skill_results:
                if r.error:
                    lines.append(f"### {r.spec.name if hasattr(r.spec, 'name') else 'unknown'}")
                    lines.append(f"```\n{r.error}\n```")

        lines.extend([
            "",
            "---",
            f"*Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        ])

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"Markdown report saved to: {path}")

    def print_summary(self) -> None:
        """打印格式化的统计摘要到控制台。"""
        console = Console()
        stats = self.get_statistics()
        overview = stats["overview"]
        by_scanner = stats["by_scanner"]

        # ── Overview ──
        table = Table(title="Batch Summary", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")
        table.add_row("Total Skills", str(overview["total_skills"]))
        table.add_row("Completed", str(overview["completed"]))
        table.add_row("Errored", str(overview["errored"]))
        table.add_row("Skipped", str(overview["skipped"]))
        table.add_row("Duration", self._format_duration(overview["duration_seconds"]))
        console.print(table)

        # ── By Scanner ──
        if by_scanner:
            scanner_table = Table(title="Scanner Results", show_header=True, header_style="bold cyan")
            scanner_table.add_column("Scanner")
            scanner_table.add_column("Detected", justify="right", style="bold red")
            scanner_table.add_column("Clean", justify="right", style="green")
            scanner_table.add_column("Error", justify="right", style="yellow")
            scanner_table.add_column("Severities")

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
            console.print(scanner_table)

        # ── Per-Skill ──
        skill_table = Table(title="Skill Results", show_header=True, header_style="bold cyan")
        skill_table.add_column("Skill")
        skill_table.add_column("Generator")
        skill_table.add_column("Outcome")
        skill_table.add_column("Iterations", justify="right")
        skill_table.add_column("Duration", justify="right")

        for r in self.skill_results:
            icon = self._get_status_icon(r.status)
            name = r.spec.name if hasattr(r.spec, "name") else "unknown"
            iterations = str(r.total_iterations)
            duration = self._format_duration(r.duration_seconds)
            outcome_style = "green" if r.final_outcome in ("clean", "success") else "red" if r.final_outcome in ("detected", "error") else "yellow"
            skill_table.add_row(
                name,
                r.generator,
                f"[{outcome_style}]{icon} {r.final_outcome}[/{outcome_style}]",
                iterations,
                duration,
            )
        console.print(skill_table)

    def _format_duration(self, seconds: float) -> str:
        """格式化时长。"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"

    def _get_status_icon(self, status: str) -> str:
        """获取状态图标。"""
        icons = {
            "success": "✓",
            "clean": "✓",
            "detected": "!",
            "failed": "✗",
            "error": "⚠",
            "pending": "⋯",
        }
        return icons.get(status, "?")
