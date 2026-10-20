"""
扫描器状态统计模块

提供从各扫描器原始结果中提取发现并生成状态摘要的函数。
"""

from dataclasses import dataclass
from typing import Any
import logging

logger = logging.getLogger(__name__)

# 相对导入修复
try:
    from models import Severity, SourceScanner, UnifiedFinding
except ImportError:
    from .models import Severity, SourceScanner, UnifiedFinding


@dataclass
class ScannerStatus:
    """扫描器状态摘要"""
    scanner_name: str
    display_name: str
    has_findings: bool
    total_findings: int
    severity_breakdown: dict[str, int]  # {CRITICAL: 0, HIGH: 1, ...}
    status: str  # "success", "error"

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "scanner_name": self.scanner_name,
            "display_name": self.display_name,
            "has_findings": self.has_findings,
            "total_findings": self.total_findings,
            "severity_breakdown": self.severity_breakdown,
            "status": self.status,
        }


def extract_findings_from_scanner(
    scanner_name: str,
    scanner_result: dict,
) -> list[UnifiedFinding]:
    """
    从各扫描器原始结果中提取 findings

    Args:
        scanner_name: 扫描器名称
        scanner_result: 扫描器返回的原始结果字典

    Returns:
        UnifiedFinding 列表
    """
    findings = []

    # 防御性检查：确保 scanner_result 是字典
    if not isinstance(scanner_result, dict):
        logger.warning(
            f"Scanner {scanner_name} returned non-dict result: {type(scanner_result).__name__}. "
            f"Content preview: {str(scanner_result)[:200]}"
        )
        return findings

    # 检查是否有错误
    if scanner_result.get("error"):
        return findings

    # 根据扫描器类型进行特定处理
    if scanner_name == "scan_cisco":
        raw_findings = scanner_result.get("findings", [])
        findings = _extract_scan_cisco_findings(raw_findings)

    elif scanner_name == "scan_hss":
        raw_findings = scanner_result.get("findings", [])
        findings = _extract_scan_hss_findings(raw_findings)

    elif scanner_name == "scan_skill_vetter":
        findings = _extract_scan_vetter_findings(scanner_result)

    elif scanner_name == "scan_skill_auditor":
        findings = _extract_scan_auditor_findings(scanner_result)

    elif scanner_name == "scan_skillfortify":
        raw_findings = scanner_result.get("findings", [])
        findings = _extract_generic_findings(scanner_name, raw_findings)

    elif scanner_name == "scan_skill_slowmist":
        findings = _extract_scan_skill_slowmist_findings(scanner_result)

    else:
        raw_findings = scanner_result.get("findings", [])
        findings = _extract_generic_findings(scanner_name, raw_findings)

    return findings


def _extract_generic_findings(scanner_name: str, raw_findings: list) -> list[UnifiedFinding]:
    """从标准 findings 列表提取 findings。"""
    findings: list[UnifiedFinding] = []
    if not raw_findings:
        return findings

        # 通用处理：假设 findings 已经是标准格式
    for f in raw_findings:
        if isinstance(f, dict):
            findings.append(UnifiedFinding(
                id=f.get("id", f"{scanner_name}-{id(f)}"),
                source_scanner=scanner_name,
                severity=_parse_severity(f.get("severity", "INFO")),
                category=f.get("category", "other"),
                title=f.get("title", ""),
                description=f.get("description", ""),
                file_path=f.get("file_path"),
                line_number=f.get("line_number"),
                snippet=f.get("snippet"),
                remediation=f.get("remediation"),
                metadata=f.get("metadata", {}),
            ))
    return findings


def _parse_severity(severity_str: str) -> Severity:
    """解析严重级别字符串"""
    try:
        return Severity(severity_str.upper())
    except (ValueError, AttributeError):
        return Severity.INFO


def _extract_scan_cisco_findings(raw_findings: list) -> list[UnifiedFinding]:
    """从 scan_cisco 结果中提取 findings"""
    findings = []
    for f in raw_findings:
        findings.append(UnifiedFinding(
            id=f.get("id", f"cisco-{id(f)}"),
            source_scanner=SourceScanner.SCAN_CISCO,
            severity=_parse_severity(f.get("severity", "INFO")),
            category=f.get("category", "other"),
            title=f.get("title", f.get("rule_id", "")),
            description=f.get("description", ""),
            file_path=f.get("file_path"),
            line_number=f.get("line_number"),
            snippet=f.get("snippet"),
            remediation=f.get("remediation"),
            metadata={"cisco_result": f},
        ))
    return findings


def _extract_scan_hss_findings(raw_findings: list) -> list[UnifiedFinding]:
    """从 scan_hss 结果中提取 findings"""
    findings = []
    for f in raw_findings:
        findings.append(UnifiedFinding(
            id=f.get("id", f"hss-{id(f)}"),
            source_scanner=SourceScanner.SCAN_HSS,
            severity=_parse_severity(f.get("severity", "INFO")),
            category=f.get("category", "other"),
            title=f.get("title", ""),
            description=f.get("description", ""),
            file_path=f.get("file_path"),
            line_number=f.get("line_number"),
            snippet=f.get("snippet"),
            remediation=f.get("remediation"),
            metadata={"hss_result": f},
        ))
    return findings


def _extract_scan_vetter_findings(scanner_result: dict) -> list[UnifiedFinding]:
    """从 scan_skill_vetter 结果中提取 findings

    支持两种格式：
    1. 旧格式: {red_flags: [...]}
    2. 新格式 (adapter): {findings: [{...}], metadata: {...}}
    """
    findings = []

    # 优先使用新格式（adapter 返回的 findings 已经是 UnifiedFinding.to_dict() 格式）
    raw_findings = scanner_result.get("findings", [])
    if raw_findings and isinstance(raw_findings, list) and len(raw_findings) > 0:
        first = raw_findings[0]
        if isinstance(first, dict) and "id" in first and "source_scanner" in first:
            # 这是新格式：findings 已经是 UnifiedFinding.to_dict() 格式
            for f in raw_findings:
                findings.append(UnifiedFinding(**f))
            return findings

    # 旧格式：从 red_flags 字段提取
    red_flags = scanner_result.get("red_flags", [])
    for flag in red_flags:
        findings.append(UnifiedFinding(
            id=f"vetter-{id(flag)}",
            source_scanner=SourceScanner.SCAN_SKILL_VETTER,
            severity=_parse_severity(flag.get("severity", "MEDIUM")),
            category="red_flag",
            title=flag.get("title", ""),
            description=flag.get("description", ""),
            file_path=flag.get("file_path"),
            snippet=flag.get("snippet"),
            remediation=flag.get("remediation"),
            metadata={"vetter_result": flag},
        ))
    return findings


def _extract_scan_auditor_findings(scanner_result: dict) -> list[UnifiedFinding]:
    """从 scan_skill_auditor 结果中提取 findings

    支持新格式 (adapter): {findings: [{...}], metadata: {...}}
    """
    findings = []

    # 新格式：adapter 返回的 findings 已经是 UnifiedFinding.to_dict() 格式
    raw_findings = scanner_result.get("findings", [])
    if raw_findings and isinstance(raw_findings, list) and len(raw_findings) > 0:
        first = raw_findings[0]
        if isinstance(first, dict) and "id" in first and "source_scanner" in first:
            # 这是新格式：findings 已经是 UnifiedFinding.to_dict() 格式
            for f in raw_findings:
                findings.append(UnifiedFinding(**f))
            return findings

    # 旧格式：直接从 findings 字段提取
    auditor_findings = scanner_result.get("findings", [])
    for f in auditor_findings:
        findings.append(UnifiedFinding(
            id=f"auditor-{id(f)}",
            source_scanner=SourceScanner.SCAN_SKILL_AUDITOR,
            severity=_parse_severity(f.get("severity", "MEDIUM")),
            category=f.get("category", "other"),
            title=f.get("title", ""),
            description=f.get("description", ""),
            file_path=f.get("file_path"),
            snippet=f.get("snippet"),
            remediation=f.get("remediation"),
            metadata={"auditor_result": f},
        ))
    return findings


def _extract_scan_skill_slowmist_findings(scanner_result: dict) -> list[UnifiedFinding]:
    """从 scan_skill_slowmist 结果中提取 findings

    支持新格式 (adapter): {findings: [{...}], metadata: {...}}
    """
    findings = []

    # 新格式：adapter 返回的 findings 已经是 UnifiedFinding.to_dict() 格式
    raw_findings = scanner_result.get("findings", [])
    if raw_findings and isinstance(raw_findings, list) and len(raw_findings) > 0:
        first = raw_findings[0]
        if isinstance(first, dict) and "id" in first and "source_scanner" in first:
            # 这是新格式：findings 已经是 UnifiedFinding.to_dict() 格式
            for f in raw_findings:
                findings.append(UnifiedFinding(**f))
            return findings

    # 旧格式：从 red_flags 字段提取
    red_flags = scanner_result.get("red_flags", [])
    for flag in red_flags:
        findings.append(UnifiedFinding(
            id=f"slowmist-{id(flag)}",
            source_scanner=SourceScanner.SCAN_SKILL_SLOWMIST,
            severity=_parse_severity(flag.get("severity", "MEDIUM")),
            category=flag.get("category", "other"),
            title=flag.get("title", ""),
            description=flag.get("description", ""),
            file_path=flag.get("file_path"),
            snippet=flag.get("snippet"),
            remediation=flag.get("remediation"),
            metadata={"slowmist_result": flag},
        ))
    return findings


def summarize_scanner_status(
    scanner_name: str,
    scanner_result: dict,
    display_name: str | None = None,
) -> ScannerStatus:
    """
    从单个扫描器结果生成状态摘要

    Args:
        scanner_name: 扫描器名称
        scanner_result: 扫描器返回的原始结果字典
        display_name: 显示名称（可选）

    Returns:
        ScannerStatus 对象
    """
    if display_name is None:
        try:
            from .models import SCANNER_DISPLAY_NAMES
        except ImportError:
            from models import SCANNER_DISPLAY_NAMES
        display_name = SCANNER_DISPLAY_NAMES.get(scanner_name, scanner_name)

    # 检查是否有错误
    if scanner_result.get("error"):
        return ScannerStatus(
            scanner_name=scanner_name,
            display_name=display_name,
            has_findings=False,
            total_findings=0,
            severity_breakdown={
                "CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0
            },
            status="error",
        )

    # 提取 findings
    findings = extract_findings_from_scanner(scanner_name, scanner_result)

    # 统计各级别数量
    breakdown = {
        "CRITICAL": 0,
        "HIGH": 0,
        "MEDIUM": 0,
        "LOW": 0,
        "INFO": 0,
    }

    for f in findings:
        severity_str = f.severity.value if isinstance(f.severity, Severity) else str(f.severity)
        severity_upper = severity_str.upper()
        if severity_upper in breakdown:
            breakdown[severity_upper] += 1

    return ScannerStatus(
        scanner_name=scanner_name,
        display_name=display_name,
        has_findings=len(findings) > 0,
        total_findings=len(findings),
        severity_breakdown=breakdown,
        status="success",
    )


def get_scanner_statuses(scanner_results: dict[str, dict]) -> list[ScannerStatus]:
    """
    从所有扫描器结果生成状态摘要列表

    Args:
        scanner_results: 扫描器结果字典 {scanner_name: result_dict}

    Returns:
        ScannerStatus 列表
    """
    try:
        from .models import SCANNER_DISPLAY_NAMES
    except ImportError:
        from models import SCANNER_DISPLAY_NAMES

    statuses = []
    for scanner_name, result in scanner_results.items():
        if scanner_name.startswith("_"):
            continue  # 跳过元数据字段
        display_name = SCANNER_DISPLAY_NAMES.get(scanner_name, scanner_name)
        status = summarize_scanner_status(scanner_name, result, display_name)
        statuses.append(status)

    return statuses
