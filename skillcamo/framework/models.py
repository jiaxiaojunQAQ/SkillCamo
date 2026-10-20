"""
统一数据模型 - 为三个扫描器提供一致的输出格式

参考了 skill-scanner 的 models.py 设计，但简化为跨扫描器的通用格式。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """安全发现的严重级别（统一标准）"""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"
    SAFE = "SAFE"


class ThreatCategory(str, Enum):
    """威胁类别（统一分类）"""
    PROMPT_INJECTION = "prompt_injection"
    COMMAND_INJECTION = "command_injection"
    DATA_EXFILTRATION = "data_exfiltration"
    UNAUTHORIZED_TOOL_USE = "unauthorized_tool_use"
    OBFUSCATION = "obfuscation"
    HARDCODED_SECRETS = "hardcoded_secrets"
    SOCIAL_ENGINEERING = "social_engineering"
    RESOURCE_ABUSE = "resource_abuse"
    POLICY_VIOLATION = "policy_violation"
    MALWARE = "malware"
    HARMFUL_CONTENT = "harmful_content"
    SUPPLY_CHAIN_ATTACK = "supply_chain_attack"
    # 新增类别（用于 skill-vetter）
    RED_FLAG = "red_flag"
    PERMISSION_ABUSE = "permission_abuse"
    SUSPICIOUS_NETWORK = "suspicious_network"
    DATA_DESTRUCTION = "data_destruction"
    DENIAL_OF_SERVICE = "denial_of_service"
    PHISHING = "phishing"
    BACKDOOR = "backdoor"
    BIAS_MANIPULATION = "bias_manipulation"
    POISONING = "poisoning"
    MANIPULATION = "manipulation"
    # 新增类别（用于 ClawGuard Auditor）
    INTENT_MISMATCH = "intent_mismatch"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    CAPABILITY_VIOLATION = "capability_violation"
    OTHER = "other"


class SourceScanner(str, Enum):
    """来源扫描器标识

    Canonical scanner ids
    """
    SCAN_SKILL_AUDITOR = "scan_skill_auditor"
    SCAN_CISCO = "scan_cisco"  # Cisco AI Skill Scanner
    SCAN_HSS = "scan_hss"  # LLM-based Security Scanner
    SCAN_SKILL_VETTER = "scan_skill_vetter"  # Skill Vetter (Claude Code)
    SCAN_SKILLFORTIFY = "scan_skillfortify"  # SkillFortify 静态分析
    SCAN_SKILL_SLOWMIST = "scan_skill_slowmist"  # SlowMist Agent Security
    SCAN_EXECSCAN = "scan_execscan"  # Execution-grounded multimodal scanner
    UNIFIED = "unified"  # 统一扫描器自身生成的发现


# 扫描器显示名称映射（无别名，统一使用 scanner id）
SCANNER_DISPLAY_NAMES: dict[str, str] = {
    "scan_skill_auditor": "scan_skill_auditor",
    "scan_cisco": "scan_cisco",
    "scan_hss": "scan_hss",
    "scan_skill_vetter": "scan_skill_vetter",
    "scan_skillfortify": "scan_skillfortify",
    "scan_skill_slowmist": "scan_skill_slowmist",
    "scan_execscan": "scan_execscan",
    "unified": "unified",
}


@dataclass
class UnifiedFinding:
    """统一的安全发现格式"""
    id: str  # 唯一标识符
    source_scanner: SourceScanner | str  # 来源扫描器
    severity: Severity
    category: ThreatCategory | str
    title: str
    description: str
    file_path: str | None = None
    line_number: int | None = None
    snippet: str | None = None
    remediation: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式（JSON可序列化）"""
        # 处理 severity - 可能是枚举或字符串
        if isinstance(self.severity, Severity):
            severity_val = self.severity.value
        else:
            severity_val = str(self.severity)

        # 处理 category
        if isinstance(self.category, ThreatCategory):
            category_val = self.category.value
        else:
            category_val = str(self.category)

        # 处理 source_scanner
        if isinstance(self.source_scanner, SourceScanner):
            source_val = self.source_scanner.value
        else:
            source_val = str(self.source_scanner)

        return {
            "id": self.id,
            "source_scanner": source_val,
            "severity": severity_val,
            "category": category_val,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "snippet": self.snippet,
            "remediation": self.remediation,
            "metadata": self.metadata,
        }

    @classmethod
    def from_skill_scanner(cls, finding: dict) -> "UnifiedFinding":
        """从 skill-scanner 的 Finding 转换"""
        return cls(
            id=finding.get("id", ""),
            source_scanner=SourceScanner.UNIFIED,
            severity=Severity(finding.get("severity", "INFO")),
            category=ThreatCategory(finding.get("category", "other")),
            title=finding.get("title", ""),
            description=finding.get("description", ""),
            file_path=finding.get("file_path"),
            line_number=finding.get("line_number"),
            snippet=finding.get("snippet"),
            remediation=finding.get("remediation"),
            metadata={"original": finding},
        )

    @classmethod
    def from_agent_scan(cls, issue: dict) -> "UnifiedFinding":
        """从 agent-scan 的 Issue 转换"""
        return cls(
            id=issue.get("code", f"agent-scan-{id(issue)}"),
            source_scanner=SourceScanner.UNIFIED,
            severity=Severity.MEDIUM,  # agent-scan 没有明确的severity，默认MEDIUM
            category=ThreatCategory.POLICY_VIOLATION,
            title=issue.get("message", ""),
            description=issue.get("message", ""),
            remediation=issue.get("extra_data", {}).get("suggestion"),
            metadata={"original": issue},
        )


@dataclass
class ScannerSummary:
    """单个扫描器的摘要信息"""
    scanner_name: str
    total_findings: int
    critical: int
    high: int
    medium: int
    low: int
    info: int
    is_safe: bool | None  # None 表示未进行判定（如扫描失败）
    status: str  # 'success', 'failed', 'skipped'
    display_name: str = ""  # 显示名称（友好名称）
    duration_ms: int | None = None  # 执行时间（失败

    def __post_init__(self):
        """自动设置 display_name"""
        if not self.display_name:
            self.display_name = SCANNER_DISPLAY_NAMES.get(self.scanner_name, self.scanner_name)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "scanner_name": self.scanner_name,
            "display_name": self.display_name,
            "total_findings": self.total_findings,
            "findings_by_severity": {
                "critical": self.critical,
                "high": self.high,
                "medium": self.medium,
                "low": self.low,
                "info": self.info,
            },
            "is_safe": self.is_safe,
            "status": self.status,
            "duration_ms": self.duration_ms,
        }


@dataclass
class ScanSummary:
    """扫描摘要信息"""
    total_findings: int
    critical: int
    high: int
    medium: int
    low: int
    info: int
    is_safe: bool | None  # None 表示无法判定（如所有扫描器均失败）
    scan_duration_ms: int
    scanners_used: list[str] = field(default_factory=list)
    scanners_failed: list[str] = field(default_factory=list)
    scanner_summaries: list[ScannerSummary] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "total_findings": self.total_findings,
            "findings_by_severity": {
                "critical": self.critical,
                "high": self.high,
                "medium": self.medium,
                "low": self.low,
                "info": self.info,
            },
            "is_safe": self.is_safe,
            "scan_duration_ms": self.scan_duration_ms,
            "scanners_used": self.scanners_used,
            "scanners_failed": self.scanners_failed,
            "scanner_summaries": [s.to_dict() for s in self.scanner_summaries],
        }


@dataclass
class UnifiedScanResult:
    """统一扫描结果"""
    scanner_name: str = "unified_skill_scanner"
    scan_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    skill_path: str = ""
    findings: list[UnifiedFinding] = field(default_factory=list)
    summary: ScanSummary | None = None
    scanner_results: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式（JSON可序列化）"""
        return {
            "scanner_name": self.scanner_name,
            "scan_timestamp": self.scan_timestamp.isoformat(),
            "skill_path": self.skill_path,
            "findings": [
                f.to_dict() if hasattr(f, "to_dict") else f
                for f in self.findings
            ],
            "summary": self.summary.to_dict() if self.summary else None,
            "scanner_results": self.scanner_results,
        }

    def calculate_summary(
        self,
        duration_ms: int,
        scanners_used: list[str],
        scanners_failed: list[str],
        scanner_findings: dict[str, list[UnifiedFinding]],
    ) -> None:
        """计算摘要信息，包含每个scanner的独立摘要"""
        # 整体统计
        critical = sum(1 for f in self.findings if f.severity == Severity.CRITICAL)
        high = sum(1 for f in self.findings if f.severity == Severity.HIGH)
        medium = sum(1 for f in self.findings if f.severity == Severity.MEDIUM)
        low = sum(1 for f in self.findings if f.severity == Severity.LOW)
        info = sum(1 for f in self.findings if f.severity == Severity.INFO)

        # 计算每个scanner的摘要
        scanner_summaries = []
        for scanner_name in scanners_used:
            findings = scanner_findings.get(scanner_name, [])
            sc_critical = sum(1 for f in findings if f.severity == Severity.CRITICAL)
            sc_high = sum(1 for f in findings if f.severity == Severity.HIGH)
            sc_medium = sum(1 for f in findings if f.severity == Severity.MEDIUM)
            sc_low = sum(1 for f in findings if f.severity == Severity.LOW)
            sc_info = sum(1 for f in findings if f.severity == Severity.INFO)

            scanner_summaries.append(ScannerSummary(
                scanner_name=scanner_name,
                total_findings=len(findings),
                critical=sc_critical,
                high=sc_high,
                medium=sc_medium,
                low=sc_low,
                info=sc_info,
                is_safe=(sc_critical == 0 and sc_high == 0),
                status="success",
            ))

        # 为失败的scanner添加摘要
        for scanner_name in scanners_failed:
            scanner_summaries.append(ScannerSummary(
                scanner_name=scanner_name,
                total_findings=0,
                critical=0,
                high=0,
                medium=0,
                low=0,
                info=0,
                is_safe=None,  # None 表示未进行安全判定（技术问题，非安全问题）
                status="failed",
            ))

        if not scanners_used:
            is_safe = None
        else:
            is_safe = (critical == 0 and high == 0)

        self.summary = ScanSummary(
            total_findings=len(self.findings),
            critical=critical,
            high=high,
            medium=medium,
            low=low,
            info=info,
            is_safe=is_safe,
            scan_duration_ms=duration_ms,
            scanners_used=scanners_used,
            scanners_failed=scanners_failed,
            scanner_summaries=scanner_summaries,
        )


@dataclass
class BatchScanSummary:
    """批量扫描摘要"""

    total_items: int
    safe_items: int
    unsafe_items: int
    error_items: int
    total_findings: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_items": self.total_items,
            "safe_items": self.safe_items,
            "unsafe_items": self.unsafe_items,
            "error_items": self.error_items,
            "total_findings": self.total_findings,
        }


@dataclass
class BatchScanResult:
    """批量扫描结果"""

    target_type: str
    target_path: str
    items: list[dict[str, Any]] = field(default_factory=list)
    summary: BatchScanSummary | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_type": self.target_type,
            "target_path": self.target_path,
            "item_count": len(self.items),
            "items": self.items,
            "summary": self.summary.to_dict() if self.summary else None,
        }
