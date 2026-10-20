"""
ScanCiscoAdapter - Cisco AI Skill Scanner 适配器

调用 scan_cisco/scan_cisco/ 模块进行扫描。
"""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

# 相对导入修复
try:
    from models import Severity, SourceScanner, ThreatCategory, UnifiedFinding
    from adapters.base import BaseAdapter
    from llm_audit import LLMAuditConfig, create_auditor_from_config
except ImportError:
    # 直接导入
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models import Severity, SourceScanner, ThreatCategory, UnifiedFinding
    from adapters.base import BaseAdapter
    from llm_audit import LLMAuditConfig, create_auditor_from_config

logger = logging.getLogger(__name__)


class ScanCiscoAdapter(BaseAdapter):
    """
    Cisco AI Skill Scanner 适配器

    源模块: scan_cisco/scan_cisco/
    入口类: scan_cisco.core.scanner.SkillScanner
    """

    scanner_name = "scan_cisco"
    scanner_display_name = "Cisco AI Skill Scanner"

    # scan_cisco 特有的威胁类别，不在 unified ThreatCategory 中
    # 将这些映射到 "other" 以避免枚举错误
    CISCO_SPECIFIC_CATEGORIES = {
        "autonomy_abuse",
        "skill_discovery_abuse",
        "transitive_trust_abuse",
        "tool_chaining_abuse",
        "unicode_steganography",
    }

    def __init__(
        self,
        model: str | None = None,
        audit_config: LLMAuditConfig | dict | None = None,
    ):
        super().__init__()
        self._model = model
        self._audit_config = audit_config
        self._auditor = create_auditor_from_config(audit_config, source="ScanCiscoAdapter")
        self._scan_cisco_module = None
        self._availability_error: str | None = None

    def _normalize_category(self, category_str: str | None) -> ThreatCategory:
        """
        安全地转换 scan_cisco 威胁类别到 unified ThreatCategory。

        如果类别不在 unified ThreatCategory 中，映射到 "other"。
        """
        if not category_str:
            return ThreatCategory.OTHER

        # 检查是否是 scan_cisco 特有类别
        if category_str in self.CISCO_SPECIFIC_CATEGORIES:
            logger.debug(
                "Mapping scan_cisco-specific category '%s' to 'other'",
                category_str
            )
            return ThreatCategory.OTHER

        # 尝试转换为 ThreatCategory 枚举
        try:
            return ThreatCategory(category_str)
        except ValueError:
            # 未知类别，映射到 "other"
            logger.debug(
                "Unknown threat category '%s' from scan_cisco, mapping to 'other'",
                category_str
            )
            return ThreatCategory.OTHER

    def _check_availability(self) -> bool:
        """检查 scan_cisco 模块是否可用"""
        try:
            # 添加 scan_cisco/ 到路径
            try:
                from skillcamo.framework.paths import get_scanner_path
            except ImportError:
                from paths import get_scanner_path
            scan_cisco_path = get_scanner_path("scan_cisco")
            if str(scan_cisco_path) not in sys.path:
                sys.path.insert(0, str(scan_cisco_path))

            # 导入 scan_cisco 模块
            from scan_cisco.core.scanner import SkillScanner
            from scan_cisco.core.analyzer_factory import build_core_analyzers
            from scan_cisco.core.scan_policy import ScanPolicy

            self._scan_cisco_module = {
                "SkillScanner": SkillScanner,
                "build_core_analyzers": build_core_analyzers,
                "ScanPolicy": ScanPolicy,
            }
            self._availability_error = None
            logger.info("scan_cisco scanner is available and initialized")
            return True
        except ImportError as e:
            error_msg = f"{type(e).__name__}: {e}"
            self._availability_error = error_msg
            logger.error(f"scan_cisco not available: {error_msg}")
            return False
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            self._availability_error = error_msg
            logger.error(f"scan_cisco initialization failed: {error_msg}")
            return False

    def scan(self, skill_path: str | Path, **kwargs) -> dict:
        """使用 scan_cisco 扫描技能"""
        start_time = time.time()
        skill_path = Path(skill_path)

        # 记录请求审计（扫描器级别）
        if self._auditor and self._auditor.enabled:
            session_id = kwargs.get("session_id")
            self._auditor.log_request(
                provider="scan_cisco",
                model=self._model or "default",
                prompt=f"Scan skill with scan_cisco (model={self._model})",
                system_prompt="Cisco AI Skill Security Scanner",
                source="ScanCiscoAdapter",
                session_id=session_id,
                metadata={
                    "skill_path": str(skill_path),
                    "scanner": "scan_cisco",
                    "model": self._model,
                },
            )

        if not self.is_available():
            logger.debug(f"scan_cisco scanner is not available, skipping scan. Error: {self._availability_error}")

            # 记录错误审计
            if self._auditor and self._auditor.enabled:
                duration_ms = int((time.time() - start_time) * 1000)
                self._auditor.log_response(
                    raw_response="",
                    error=self._availability_error or "Scanner not available",
                    duration_ms=duration_ms,
                )
                self._auditor.save()
                self._auditor.append_to_index()

            return {
                "findings": [],
                "metadata": {
                    "scanner": self.scanner_name,
                    "error": self._availability_error or "Scanner not available (unknown error)",
                    "error_type": "ScannerUnavailable",
                },
            }

        try:
            from scan_cisco.core.scanner import SkillScanner
            from scan_cisco.core.scan_policy import ScanPolicy

            # 创建策略和分析器（使用 balanced 预设策略）
            policy = ScanPolicy.from_preset("balanced")
            if self._model:
                from scan_cisco.core.analyzer_factory import build_analyzers
                analyzers = build_analyzers(policy=policy, use_llm=True, llm_model=self._model)
            else:
                analyzers = self._scan_cisco_module["build_core_analyzers"](policy=policy)

            # 创建扫描器实例
            scanner = SkillScanner(analyzers=analyzers)

            # 执行扫描
            # 使用 lenient 模式以容忍 YAML 解析错误
            result = scanner.scan_skill(skill_path, lenient=True)

            # 转换结果
            duration_ms = int((time.time() - start_time) * 1000)

            unified_findings = []
            for finding in result.findings:
                # 转换为统一格式
                unified_finding = UnifiedFinding(
                    id=finding.id,
                    source_scanner=SourceScanner.SCAN_CISCO,
                    severity=Severity(finding.severity.value),
                    category=self._normalize_category(finding.category.value if finding.category else None),
                    title=finding.title,
                    description=finding.description,
                    file_path=str(finding.file_path) if finding.file_path else None,
                    line_number=finding.line_number if finding.line_number else None,
                    snippet=finding.snippet,
                    remediation=finding.remediation,
                    metadata={
                        "analyzer": finding.analyzer,
                        "rule_id": finding.rule_id if hasattr(finding, 'rule_id') else None,
                    },
                )
                unified_findings.append(unified_finding)

            scan_result = {
                "findings": [f.to_dict() for f in unified_findings],
                "metadata": {
                    "scanner": self.scanner_name,
                    "duration_ms": duration_ms,
                    "analyzers_used": [a.__class__.__name__ for a in analyzers],
                    "max_severity": result.max_severity.value if result.max_severity else "INFO",
                    "skill_name": result.skill_name,
                },
                "raw": {"num_findings": len(result.findings)},
                "raw_output_text": json.dumps(
                    result.to_dict() if hasattr(result, "to_dict") else str(result),
                    indent=2, default=str, ensure_ascii=False,
                ),
            }

            # 记录成功审计
            if self._auditor and self._auditor.enabled:
                self._auditor.log_response(
                    raw_response=json.dumps(scan_result, ensure_ascii=False),
                    parsed_response={
                        "findings_count": len(unified_findings),
                        "max_severity": result.max_severity.value if result.max_severity else "INFO",
                        "analyzers_used": [a.__class__.__name__ for a in analyzers],
                    },
                    duration_ms=duration_ms,
                )
                self._auditor.save()
                self._auditor.append_to_index()

            return scan_result

        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            duration_ms = int((time.time() - start_time) * 1000)

            # 对 YAML 解析错误的特殊处理
            is_yaml_error = "YAML" in error_msg or "frontmatter" in error_msg.lower()

            logger.error(f"scan_cisco scan failed with {error_type}: {error_msg}")

            # 记录错误审计
            if self._auditor and self._auditor.enabled:
                self._auditor.log_response(
                    raw_response="",
                    error=f"{error_type}: {error_msg}",
                    duration_ms=duration_ms,
                )
                self._auditor.save()
                self._auditor.append_to_index()

            return {
                "findings": [],
                "metadata": {
                    "scanner": self.scanner_name,
                    "error": error_msg,
                    "error_type": error_type,
                    "skill_path": str(skill_path) if is_yaml_error else None,
                    "hint": "SKILL.md contains malformed YAML frontmatter" if is_yaml_error else None,
                },
                "raw_output_text": f"Error: {error_type}: {error_msg}",
            }
