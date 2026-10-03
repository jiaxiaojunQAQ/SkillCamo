# Copyright 2026
#
# Result models for pipeline execution.

"""
Result models for pipeline execution.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class PipelineAttempt:
    """单次尝试记录"""

    iteration: int
    timestamp: datetime
    skill_path: Path
    detected: bool
    scan_result: dict[str, Any]
    analysis: dict[str, Any]  # 生成器的反馈分析
    notes: str = ""
    iteration_timing: dict[str, Any] | None = None  # 每迭代计时信息
    update_context: dict[str, Any] | None = None  # scanner 信息到策略的映射


@dataclass
class PipelineResult:
    """Pipeline 执行结果"""

    success: bool
    total_iterations: int
    attempts: list[PipelineAttempt]
    final_skill_path: Path | None = None
    duration_seconds: float = 0.0
    start_time: datetime | None = None
    end_time: datetime | None = None
    # Candidate scanner evaluations the inner-loop optimizer actually spent on
    # this skill (None for non-inner-loop generators). The honest budget metric.
    evals_used: int | None = None

    def get_statistics(self) -> dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        detected_count = sum(1 for a in self.attempts if a.detected)
        clean_count = len(self.attempts) - detected_count

        # 统计触发的规则
        all_rules: set[str] = set()
        for attempt in self.attempts:
            if "scanners" in attempt.scan_result:
                for scanner_data in attempt.scan_result["scanners"].values():
                    if isinstance(scanner_data, dict):
                        rules = scanner_data.get("blocked_rules", [])
                        all_rules.update(rules)

        final_outcome = "unknown"
        if self.attempts:
            final_outcome = "bypassed" if not self.attempts[-1].detected else "detected"

        return {
            "attempt_count": len(self.attempts),
            "total_iterations": self.total_iterations,
            "detected_iterations": detected_count,
            "clean_iterations": clean_count,
            "final_outcome": final_outcome,
            "unique_rules_triggered": sorted(all_rules),
            "duration_seconds": self.duration_seconds,
            "evals_used": self.evals_used,
        }

    def save_summary(self, output_dir: Path) -> None:
        """
        保存结果摘要（运行级别统计）

        注意：每个迭代的详细信息（扫描结果+分析反馈）已保存在 scan_result.json 中。
        此方法只保存运行级别的统计信息。

        Args:
            output_dir: 输出目录
        """
        import json

        output_dir.mkdir(parents=True, exist_ok=True)

        summary = {
            "success": self.success,
            "total_iterations": self.total_iterations,
            "duration_seconds": self.duration_seconds,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "final_skill_path": str(self.final_skill_path) if self.final_skill_path else None,
            "statistics": self.get_statistics(),
        }

        summary_file = output_dir / "summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
