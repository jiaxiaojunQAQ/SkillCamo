# Copyright 2026
#
# Data models for pipeline execution.

"""
Data models for pipeline execution.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class SingleScannerFeedback:
    """单个扫描器的反馈"""

    scanner_name: str
    detected: bool
    findings: list[dict]
    max_severity: str
    blocked_rules: list[str]
    raw_result: dict

    @property
    def is_clean(self) -> bool:
        """检查扫描器是否未检出高风险问题。"""
        from .scan_utils import is_detected
        return not is_detected(self.detected, self.max_severity)


@dataclass
class MultiScannerFeedback:
    """
    多扫描器的统一反馈

    封装所有扫描器的结果，提供便捷的查询方法。
    """

    scanners: dict[str, SingleScannerFeedback]
    summary: dict[str, Any]
    llm_judgement: dict[str, Any] | None = None

    @property
    def all_clean(self) -> bool:
        """严格模式: 所有扫描器都未检出高风险问题。"""
        return all(fb.is_clean for fb in self.scanners.values())

    @property
    def any_clean(self) -> bool:
        """宽松模式: 任一扫描器未检出高风险问题即可。"""
        return any(fb.is_clean for fb in self.scanners.values())

    @property
    def critical_or_high_count(self) -> int:
        """统计 CRITICAL 和 HIGH 级别的发现数量"""
        count = 0
        for fb in self.scanners.values():
            if fb.max_severity in ("CRITICAL", "HIGH"):
                count += 1
        return count

    @property
    def detectors_triggered(self) -> list[str]:
        """获取检测到威胁的扫描器列表"""
        return [
            name for name, fb in self.scanners.items()
            if not fb.is_clean
        ]

    @property
    def detectors_clean(self) -> list[str]:
        """获取未检出高风险问题的扫描器列表。"""
        return [
            name for name, fb in self.scanners.items()
            if fb.is_clean
        ]

    def get_triggered_rules_by_scanner(self) -> dict[str, list[str]]:
        """获取每个扫描器触发的规则"""
        return {
            name: fb.blocked_rules
            for name, fb in self.scanners.items()
            if fb.blocked_rules
        }


@dataclass
class ScanFeedback:
    """
    标准化扫描器反馈

    兼容旧接口。
    """

    detected: bool
    findings: list[dict]
    max_severity: str
    blocked_rules: list[str]
    passed_rules: list[str]
    raw_result: dict

    @property
    def is_clean(self) -> bool:
        """检查是否未检出高风险问题。"""
        from .scan_utils import is_detected
        return not is_detected(self.detected, self.max_severity)
