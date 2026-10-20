"""Scanner 元数据与可用性检查。"""

from __future__ import annotations

import importlib
import os
import shutil
import sys
from dataclasses import dataclass
from typing import Any

try:
    from .models import SCANNER_DISPLAY_NAMES as MODEL_SCANNER_DISPLAY_NAMES
    from .paths import (
        get_auditor_skill_path,
        get_scanner_path,
        get_skill_vetter_skill_path,
        get_slowmist_skill_path,
    )
except ImportError:
    from models import SCANNER_DISPLAY_NAMES as MODEL_SCANNER_DISPLAY_NAMES  # type: ignore[import-not-found,no-redef]
    from paths import (  # type: ignore[import-not-found,no-redef]
        get_auditor_skill_path,
        get_scanner_path,
        get_skill_vetter_skill_path,
        get_slowmist_skill_path,
    )


ALL_SCANNER_NAMES: frozenset[str] = frozenset({
    "scan_skill_auditor",
    "scan_cisco",
    "scan_hss",
    "scan_skill_vetter",
    "scan_skillfortify",
    "scan_skill_slowmist",
    "scan_execscan",
})

SCANNER_DISPLAY_NAMES = {
    name: MODEL_SCANNER_DISPLAY_NAMES.get(name, name)
    for name in ALL_SCANNER_NAMES
}

SCANNER_CONFIG_ATTRS = {
    "scan_skill_auditor": "scan_skill_auditor",
    "scan_cisco": "scan_cisco",
    "scan_hss": "scan_hss",
    "scan_skill_vetter": "scan_skill_vetter",
    "scan_skillfortify": "scan_skillfortify",
    "scan_skill_slowmist": "scan_skill_slowmist",
    "scan_execscan": "scan_execscan",
}


def normalize_scanner_name(scanner_name: str) -> str:
    """返回 canonical scanner id。"""
    return scanner_name


@dataclass
class AvailabilityRegistry:
    """缓存 scanner 可用性与失败原因。"""

    cache: dict[str, bool]
    reasons: dict[str, str]

    def is_available(self, scanner_name: str) -> bool:
        canonical = normalize_scanner_name(scanner_name)
        if canonical not in self.cache:
            available, reason = check_availability(canonical)
            self.cache[canonical] = available
            if reason:
                self.reasons[canonical] = reason
        return self.cache[canonical]


def check_availability(scanner_name: str) -> tuple[bool, str | None]:
    """检查 scanner 依赖是否可用。"""
    normalized_name = normalize_scanner_name(scanner_name)

    try:
        if normalized_name == "scan_cisco":
            scan_cisco_path = get_scanner_path("scan_cisco")
            if not scan_cisco_path.exists():
                return False, f"扫描器目录不存在: {scan_cisco_path}"
            scan_cisco_str = str(scan_cisco_path)
            if scan_cisco_str not in sys.path:
                sys.path.insert(0, scan_cisco_str)
            importlib.import_module("scan_cisco.core.scanner")
            importlib.import_module("scan_cisco.core.analyzer_factory")
            importlib.import_module("scan_cisco.core.scan_policy")
            return True, None

        if normalized_name == "scan_hss":
            scan_hss_path = get_scanner_path("scan_hss")
            scan_hss_parent_str = str(scan_hss_path.parent)
            if scan_hss_parent_str not in sys.path:
                sys.path.insert(0, scan_hss_parent_str)
            importlib.import_module("scan_hss.three_phase_scanner")
            return True, None

        if normalized_name == "scan_skill_vetter":
            vetter_source = get_skill_vetter_skill_path()
            has_cli = shutil.which("claude") is not None
            has_vetter = vetter_source.exists()
            if not has_cli:
                return False, "Claude CLI 未找到（需要安装 Claude Code）"
            if not has_vetter:
                return False, f"scan_skill_vetter 文件不存在: {vetter_source}"
            return True, None

        if normalized_name == "scan_skill_auditor":
            auditor_path = get_auditor_skill_path()
            has_cli = shutil.which("claude") is not None
            has_auditor = auditor_path.exists()
            if not has_cli:
                return False, "Claude CLI 未找到（需要安装 Claude Code）"
            if not has_auditor:
                return False, f"scan_skill_auditor 文件不存在: {auditor_path}"
            return True, None

        if normalized_name == "scan_skillfortify":
            scan_skillfortify_path = get_scanner_path("scan_skillfortify")
            has_module = scan_skillfortify_path.exists() and (scan_skillfortify_path / "scan_skillfortify").exists()
            if not has_module:
                return False, f"SkillFortify 模块不存在: {scan_skillfortify_path}"
            return True, None

        if normalized_name == "scan_skill_slowmist":
            slowmist_path = get_slowmist_skill_path()
            has_cli = shutil.which("claude") is not None
            has_skill = slowmist_path.exists()
            if not has_cli:
                return False, "Claude CLI 未找到（需要安装 Claude Code）"
            if not has_skill:
                return False, f"slowmist skill 文件不存在: {slowmist_path}"
            return True, None

        if normalized_name == "scan_execscan":
            scan_execscan_path = get_scanner_path("scan_execscan")
            if not scan_execscan_path.exists():
                return False, f"扫描器目录不存在: {scan_execscan_path}"
            try:
                importlib.import_module("skillcamo.defenses.execscan")
            except ImportError as e:
                return False, f"模块导入失败: {e}"
            return True, None

        return False, f"未知扫描器: {scanner_name}"
    except ImportError as e:
        return False, f"模块导入失败: {e}"


def get_enabled_scanners(config: Any, availability: AvailabilityRegistry) -> list[str]:
    """根据配置和可用性返回启用 scanner 列表。"""
    enabled = []
    for name, config_attr in SCANNER_CONFIG_ATTRS.items():
        cfg = getattr(config, config_attr)
        if cfg.enabled and availability.is_available(name):
            enabled.append(name)
    return enabled


def get_availability_report(availability: AvailabilityRegistry) -> dict[str, dict[str, Any]]:
    """返回所有标准 scanner 的可用性报告。"""
    report = {}
    for name, display_name in SCANNER_DISPLAY_NAMES.items():
        availability.is_available(name)
        report[name] = {
            "available": availability.cache.get(name, False),
            "display_name": display_name,
            "reason": availability.reasons.get(name),
        }
    return report
