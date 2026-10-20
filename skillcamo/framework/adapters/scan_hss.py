"""
ScanHssAdapter - HSS (Hybrid Security Scanner) 适配器

调用 scan_hss/ 模块的三阶段扫描器进行扫描，直接返回原始输出。
"""

import json
import logging
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 相对导入修复
try:
    from ..models import Severity, SourceScanner, ThreatCategory, UnifiedFinding
    from .base import BaseAdapter
    from ..llm_audit import LLMAuditConfig, create_auditor_from_config
except ImportError:
    # 添加 unified_scanner 到路径后使用绝对导入
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models import Severity, SourceScanner, ThreatCategory, UnifiedFinding
    from adapters.base import BaseAdapter
    from llm_audit import LLMAuditConfig, create_auditor_from_config


class ScanHssAdapter(BaseAdapter):
    """
    HSS (Hybrid Security Scanner) 适配器

    源模块: scan_hss/
    入口类: scan_hss.three_phase_scanner.ThreePhaseSecurityScanner
    """

    scanner_name = "scan_hss"
    scanner_display_name = "HSS (Hybrid Security Scanner)"
    # llm-guard / transformers 初始化在并发场景下不稳定，使用全局锁串行化
    _global_init_lock = threading.Lock()
    _global_scan_lock = threading.Lock()
    _global_available: bool | None = None
    _global_availability_error: str | None = None
    _global_shared_scanner = None

    # Phase1 规则ID到威胁类别映射
    RULE_ID_TO_CATEGORY = {
        # Network rules
        "NET001": ThreatCategory.DATA_EXFILTRATION,
        # File rules
        "FILE001": ThreatCategory.HARDCODED_SECRETS,
        "FILE002": ThreatCategory.DATA_DESTRUCTION,
        # Command rules
        "CMD001": ThreatCategory.COMMAND_INJECTION,
        "CMD002": ThreatCategory.COMMAND_INJECTION,
        # Injection rules
        "INJ001": ThreatCategory.COMMAND_INJECTION,
        "INJ002": ThreatCategory.OBFUSCATION,
        "INJ003": ThreatCategory.BACKDOOR,
        # Dependency rules
        "DEP001": ThreatCategory.SUPPLY_CHAIN_ATTACK,
        "DEP002": ThreatCategory.SUPPLY_CHAIN_ATTACK,
        "DEP003": ThreatCategory.SUPPLY_CHAIN_ATTACK,
        # Instruction rules
        "INST001": ThreatCategory.PROMPT_INJECTION,
        "INST002": ThreatCategory.DATA_EXFILTRATION,
        "INST003": ThreatCategory.PROMPT_INJECTION,
        # Info rules
        "OBS001": ThreatCategory.OBFUSCATION,
        "HID001": ThreatCategory.OBFUSCATION,
    }

    # Phase1 严重级别映射
    PHASE1_SEVERITY_MAP = {
        "CRITICAL": Severity.CRITICAL,
        "WARNING": Severity.MEDIUM,
        "INFO": Severity.LOW,
    }

    # Phase2 扫描器到威胁类别映射
    # 注意：已移除 invisible_text（原版 llm-guard 不支持此扫描器）
    LLM_GUARD_TO_CATEGORY = {
        "prompt_injection": ThreatCategory.PROMPT_INJECTION,
        "secrets": ThreatCategory.HARDCODED_SECRETS,
        "gibberish": ThreatCategory.OBFUSCATION,
        "sentiment": ThreatCategory.SOCIAL_ENGINEERING,
        "toxicity": ThreatCategory.HARMFUL_CONTENT,
        "ban_substrings": ThreatCategory.COMMAND_INJECTION,
        "ban_topics": ThreatCategory.MALWARE,
        "code": ThreatCategory.COMMAND_INJECTION,
        "regex": ThreatCategory.HARDCODED_SECRETS,
    }

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        audit_config: LLMAuditConfig | dict | None = None,
    ):
        super().__init__()
        self._model = model
        self._base_url = base_url
        self._audit_config = audit_config
        self._auditor = create_auditor_from_config(audit_config, source="ScanHssAdapter")
        self._hss_module = None
        self._availability_error: str | None = None  # 存储可用性检查失败的详细错误

    def _check_availability(self) -> bool:
        """
        检查 scan_hss 模块是否可用（实际测试初始化）

        不仅仅检查导入，还会实际尝试实例化扫描器并测试扫描功能，
        以捕获：
        - onnxruntime 未安装导致的 meta tensor 错误
        - "Tensor on device cpu is not on the expected device meta!" 设备不匹配错误
        - llm-guard 库未安装的延迟导入错误
        - 其他初始化时依赖问题
        """
        import tempfile

        if self.__class__._global_available is not None:
            self._availability_error = self.__class__._global_availability_error
            if self.__class__._global_available:
                self._hss_module = {"_test_instance": self.__class__._global_shared_scanner}
            return self.__class__._global_available

        with self.__class__._global_init_lock:
            if self.__class__._global_available is not None:
                self._availability_error = self.__class__._global_availability_error
                if self.__class__._global_available:
                    self._hss_module = {"_test_instance": self.__class__._global_shared_scanner}
                return self.__class__._global_available

            try:
                # 添加 scan_hss 父目录到路径（与 scanner.py 保持一致）
                try:
                    from skillcamo.framework.paths import get_scanner_path
                except ImportError:
                    from paths import get_scanner_path

                hss_path = get_scanner_path("scan_hss")
                if str(hss_path.parent) not in sys.path:
                    sys.path.insert(0, str(hss_path.parent))

                # 导入 scan_hss 模块
                from scan_hss.three_phase_scanner import ThreePhaseSecurityScanner

                # 关键：实际尝试实例化，以捕获初始化错误
                # ThreePhaseSecurityScanner.__init__ 会触发 LLMGuardScanner._init_scanners()
                # 这足以捕获 llm-guard/torch 的导入和设备初始化错误
                scanner = ThreePhaseSecurityScanner(
                    model=self._model or "gpt-4o-mini",
                    base_url=self._base_url,
                    phase2_lock=self.__class__._global_scan_lock,
                )

                self._hss_module = {
                    "ThreePhaseSecurityScanner": ThreePhaseSecurityScanner,
                    "_test_instance": scanner,  # 保存测试实例供复用
                }
                self.__class__._global_shared_scanner = scanner
                self.__class__._global_available = True
                self.__class__._global_availability_error = None
                self._availability_error = None
                logger.info("scan_hss scanner is available and initialized")
                return True

            except ImportError as e:
                self._availability_error = f"ImportError: {e}"
                self.__class__._global_available = False
                self.__class__._global_availability_error = self._availability_error
                logger.error(f"scan_hss scanner not available (import error): {e}")
                return False
            except Exception as e:
                # 捕获所有初始化错误（包括 meta tensor、依赖缺失等）
                error_type = type(e).__name__
                error_msg = str(e)
                self._availability_error = f"{error_type}: {error_msg}"
                self.__class__._global_available = False
                self.__class__._global_availability_error = self._availability_error
                logger.error(
                    f"scan_hss scanner not available ({error_type}): {error_msg}"
                )
                return False

    def _calculate_phase2_severity(self, confidence: float, scanner_name: str) -> Severity:
        """计算 Phase2 发现的严重级别"""
        if confidence >= 0.7:
            if scanner_name in ["prompt_injection", "secrets", "ban_substrings"]:
                return Severity.CRITICAL
            return Severity.HIGH
        elif confidence >= 0.5:
            return Severity.MEDIUM
        else:
            return Severity.LOW

    def _convert_phase1_finding(self, finding: dict, skill_path: Path) -> UnifiedFinding:
        """转换 Phase1 静态扫描发现为 UnifiedFinding"""
        rule_id = finding.get("rule_id", "")
        matched_text = finding.get("matched_text", "")

        return UnifiedFinding(
            id=f"hss-p1-{rule_id}-{finding.get('line', 0)}",
            source_scanner=SourceScanner.SCAN_HSS,
            severity=self.PHASE1_SEVERITY_MAP.get(finding.get("severity"), Severity.MEDIUM),
            category=self.RULE_ID_TO_CATEGORY.get(rule_id, ThreatCategory.OTHER),
            title=f"[Phase1] {finding.get('rule_name', rule_id)}",
            description=finding.get("description", ""),
            file_path=finding.get("file"),
            line_number=finding.get("line"),
            snippet=matched_text,
            remediation=f"Review and remove or sanitize the matched pattern: {matched_text}",
            metadata={
                "phase": "phase1",
                "rule_id": rule_id,
                "hss_result": finding,
            },
        )

    def _convert_phase2_finding(self, scanner_name: str, details: dict) -> UnifiedFinding:
        """转换 Phase2 LLM-Guard 发现为 UnifiedFinding"""
        confidence = details.get("confidence", 0.0)
        category = self.LLM_GUARD_TO_CATEGORY.get(scanner_name, ThreatCategory.OTHER)

        desc_parts = [f"LLM-Guard scanner '{scanner_name}' flagged this skill"]
        if details.get("matched_patterns"):
            patterns = [str(p) for p in details["matched_patterns"]]
            desc_parts.append(f"Matched patterns: {', '.join(patterns)}")
        if details.get("matches_count") is not None:
            desc_parts.append(f"Found {details['matches_count']} potential matches")
        if details.get("invisible_count") is not None:
            desc_parts.append(f"Detected {details['invisible_count']} invisible characters")
        if details.get("matched_substrings"):
            subs = [str(s) for s in details["matched_substrings"]]
            desc_parts.append(f"Matched substrings: {', '.join(subs)}")
        if details.get("matched_topics"):
            topics = [str(t) for t in details["matched_topics"]]
            desc_parts.append(f"Matched topics: {', '.join(topics)}")

        return UnifiedFinding(
            id=f"hss-p2-{scanner_name}",
            source_scanner=SourceScanner.SCAN_HSS,
            severity=self._calculate_phase2_severity(confidence, scanner_name),
            category=category,
            title=f"[Phase2] {scanner_name.replace('_', ' ').title()} Detected",
            description=". ".join(desc_parts),
            file_path=None,  # Phase2 是全文件扫描，无具体位置
            remediation=f"Review skill content for {scanner_name.replace('_', ' ')} patterns",
            metadata={
                "phase": "phase2",
                "scanner_name": scanner_name,
                "confidence": confidence,
                "details": details,
            },
        )

    def _convert_phase3_finding(self, phase3: dict) -> list[UnifiedFinding]:
        """
        转换 Phase3 四维度分类结果

        直接返回原始四维度结果，不进行映射转换
        """
        findings = []

        # 检查是否有四维度数据
        if not phase3:
            return findings

        # 类型检查: phase3 必须是字典
        if not isinstance(phase3, dict):
            logger.warning(
                "Phase3 data has unexpected type %s (expected dict). "
                "Data preview: %s",
                type(phase3).__name__,
                str(phase3)[:200] if phase3 else "empty"
            )
            return findings

        # 为每个维度生成一个 Finding（包含所有维度，即使置信度低）
        for dim_name, dim_data in phase3.items():
            if not isinstance(dim_data, dict):
                continue

            confidence = dim_data.get("confidence", 0.0)
            patterns = dim_data.get("patterns", [])
            evidence = dim_data.get("evidence", "")

            # 格式化标题
            dim_title = dim_name.replace("_", " ").title()
            title = f"[Phase3] {dim_title} (confidence: {confidence:.2f})"

            # 格式化描述
            desc_parts = [
                f"Dimension: {dim_name}",
                f"Confidence: {confidence:.2f}",
            ]
            if patterns:
                desc_parts.append(f"Patterns: {', '.join(patterns)}")
            if evidence:
                desc_parts.append(f"Evidence: {evidence}")

            # 根据置信度确定严重级别
            if confidence >= 0.7:
                severity = Severity.CRITICAL
            elif confidence >= 0.5:
                severity = Severity.HIGH
            elif confidence >= 0.3:
                severity = Severity.MEDIUM
            else:
                severity = Severity.LOW

            findings.append(UnifiedFinding(
                id=f"hss-p3-{dim_name}-{uuid.uuid4().hex[:8]}",
                source_scanner=SourceScanner.SCAN_HSS,
                severity=severity,
                category=dim_name,  # 直接使用维度名称
                title=title,
                description=". ".join(desc_parts),
                remediation=f"Review skill for {dim_name.replace('_', ' ')} patterns",
                metadata={
                    "phase": "phase3",
                    "dimension": dim_name,
                    "confidence": confidence,
                    "patterns": patterns,
                    "evidence": evidence,
                },
            ))

        return findings

    def _convert_hss_result(self, skill_path: Path, hss_result: dict) -> list[UnifiedFinding]:
        """将 HSS 三阶段结果转换为 UnifiedFinding 列表"""
        findings = []

        # Phase1: 静态扫描发现
        phase1 = hss_result.get("phase1", {})
        if phase1.get("has_findings"):
            for finding in phase1.get("findings", []):
                findings.append(self._convert_phase1_finding(finding, skill_path))

        # Phase2: LLM-Guard 发现
        phase2 = hss_result.get("phase2", {})
        if phase2.get("flagged"):
            for scanner_name in phase2.get("flagged_scanners", []):
                details = phase2.get("details", {}).get(scanner_name, {})
                findings.append(self._convert_phase2_finding(scanner_name, details))

        # Phase3: 四维度分类（直接返回原始结果）
        phase3 = hss_result.get("phase3")
        if phase3:
            findings.extend(self._convert_phase3_finding(phase3))

        return findings

    def scan(self, skill_path: str | Path, **kwargs) -> dict:
        """使用 scan_hss 扫描技能"""
        start_time = time.time()
        timeout = kwargs.get("timeout")
        skill_path = Path(skill_path)

        # 记录请求审计（扫描器级别）
        if self._auditor and self._auditor.enabled:
            session_id = kwargs.get("session_id")
            self._auditor.log_request(
                provider="scan_hss",
                model=self._model or "gpt-4o-mini",
                prompt=f"Scan skill with scan_hss three-phase scanner (model={self._model}, base_url={self._base_url})",
                system_prompt="HSS (Hybrid Security Scanner) - Three-phase security analysis",
                source="ScanHssAdapter",
                session_id=session_id,
                metadata={
                    "skill_path": str(skill_path),
                    "scanner": "scan_hss",
                    "model": self._model,
                    "base_url": self._base_url,
                    "timeout": timeout,
                },
            )

        # 检查可用性（如果之前检测到不可用，直接返回）
        if not self.is_available():
            logger.debug(f"scan_hss scanner is not available, skipping scan. Error: {self._availability_error}")

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
                    "is_safe": None,  # None means unable to determine (technical error)
                },
            }

        try:
            from scan_hss.three_phase_scanner import ThreePhaseSecurityScanner

            # 创建扫描器实例（复用全局测试实例或创建新实例）
            scanner = self.__class__._global_shared_scanner
            if scanner is None:
                if self._hss_module and "_test_instance" in self._hss_module:
                    scanner = self._hss_module["_test_instance"]
                else:
                    with self.__class__._global_init_lock:
                        scanner = self.__class__._global_shared_scanner
                        if scanner is None:
                            scanner = ThreePhaseSecurityScanner(
                                model=self._model or "gpt-4o-mini",
                                base_url=self._base_url,
                                phase2_lock=self.__class__._global_scan_lock,
                            )
                            self.__class__._global_shared_scanner = scanner

            # 执行扫描（Phase 2 的 llm-guard/torch 锁已注入 scanner 内部）

            # 超时包装：在独立线程中执行扫描，强制超时
            # 仿照 scan_cisco 的模式，防止 scan_hss 内部阻塞（llm_guard 推理、OpenAI HTTP 调用）
            # 导致 ScanRunner 的线程永远无法完成
            if timeout and timeout > 0:
                from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

                ex = ThreadPoolExecutor(max_workers=1)
                future = ex.submit(scanner.scan, skill_path)
                try:
                    result = future.result(timeout=timeout)
                except FuturesTimeoutError:
                    future.cancel()
                    ex.shutdown(wait=False, cancel_futures=True)
                    raise TimeoutError(f"scan_hss exceeded {timeout}s timeout")
                finally:
                    ex.shutdown(wait=False)
            else:
                result = scanner.scan(skill_path)

            # 转换结果
            duration_ms = int((time.time() - start_time) * 1000)

            # 转换详细的三阶段结果为 UnifiedFinding 列表
            unified_findings = self._convert_hss_result(skill_path, result)

            # 如果没有任何发现但状态是 flagged，添加汇总发现
            if result.get("status") == "flagged" and not unified_findings:
                unified_findings.append(UnifiedFinding(
                    id=f"hss-{uuid.uuid4().hex[:8]}",
                    source_scanner=SourceScanner.SCAN_HSS,
                    severity=Severity.HIGH,
                    category=ThreatCategory.OTHER,
                    title="HSS: Skill flagged as suspicious",
                    description=f"Three-phase scanner flagged this skill. Reason: {result.get('aggregation', {}).get('reason', 'unknown')}",
                    file_path=str(skill_path),
                    metadata={
                        "hss_status": result.get("status"),
                        "hss_phase": result.get("phase"),
                        "hss_result": result,
                    },
                ))

            # 聚合信息
            aggregation = result.get("aggregation", {})
            phase1 = result.get("phase1", {})
            phase2 = result.get("phase2", {})
            phase3 = result.get("phase3", {})

            # Calculate is_safe from hss_status
            hss_status = result.get("status")
            is_safe = hss_status == "benign"

            scan_result = {
                "findings": [f.to_dict() for f in unified_findings],
                "metadata": {
                    "scanner": self.scanner_name,
                    "duration_ms": duration_ms,
                    "hss_status": hss_status,
                    "hss_phase": result.get("phase"),
                    "hss_aggregation": aggregation,
                    "findings_by_phase": {
                        "phase1_count": phase1.get("findings_count", 0),
                        "phase2_count": len(phase2.get("flagged_scanners", [])),
                        "phase3_dimensions": list(phase3.keys()) if phase3 else [],
                    },
                    "is_safe": is_safe,
                },
                "raw": result,
                "raw_output_text": json.dumps(result, indent=2, default=str, ensure_ascii=False),
            }

            # 记录成功审计
            if self._auditor and self._auditor.enabled:
                self._auditor.log_response(
                    raw_response=json.dumps(scan_result, ensure_ascii=False),
                    parsed_response={
                        "findings_count": len(unified_findings),
                        "hss_status": hss_status,
                        "is_safe": is_safe,
                        "findings_by_phase": {
                            "phase1_count": phase1.get("findings_count", 0),
                            "phase2_count": len(phase2.get("flagged_scanners", [])),
                            "phase3_dimensions": list(phase3.keys()) if phase3 else [],
                        },
                    },
                    duration_ms=duration_ms,
                )
                self._auditor.save()
                self._auditor.append_to_index()

            return scan_result

        except TimeoutError:
            # 记录超时审计
            if self._auditor and self._auditor.enabled:
                duration_ms = int((time.time() - start_time) * 1000)
                self._auditor.log_response(
                    raw_response="",
                    error=f"TimeoutError: scan_hss exceeded {timeout}s timeout",
                    duration_ms=duration_ms,
                )
                self._auditor.save()
                self._auditor.append_to_index()
            raise  # 让 ScanRunner.run_parallel 的重试逻辑处理
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            duration_ms = int((time.time() - start_time) * 1000)

            # 如果是持久性错误（初始化/配置相关），标记扫描器为不可用
            # 这样可以避免后续重复尝试执行失败的扫描器
            persistent_errors = (
                "ImportError",
                "ModuleNotFoundError",
                "NotImplementedError",
                "RuntimeError",
                "OSError",
            )
            is_persistent = (
                error_type in persistent_errors
                or "meta tensor" in error_msg.lower()
                or "device.*meta" in error_msg.lower()
                or "not on the expected device meta" in error_msg.lower()
                or "onnxruntime" in error_msg.lower()
            )

            if is_persistent:
                self._available = False
                self.__class__._global_available = False
                self.__class__._global_availability_error = f"{error_type}: {error_msg}"
                logger.error(
                    f"scan_hss scanner marked as unavailable due to {error_type}: {error_msg}"
                )
            else:
                logger.warning(f"scan_hss scan failed with {error_type}: {error_msg}")

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
                    "is_persistent_error": is_persistent,
                    "is_safe": None,  # None means unable to determine (technical error)
                },
                "raw_output_text": f"Error: {error_type}: {error_msg}",
            }
