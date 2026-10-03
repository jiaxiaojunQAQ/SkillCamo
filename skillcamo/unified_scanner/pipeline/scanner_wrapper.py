# Copyright 2026
#
# Scanner wrapper for unified interface to skill-scanner and agent-scan.

"""
Scanner wrapper providing a unified interface to multiple scanner backends.

Supports:
- skill-scanner: The core skill security scanner
- agent-scan: MCP server and skill scanner
- unified: Integrated scanner with 6 backends (scan_cisco, scan_hss, etc.)
"""

from __future__ import annotations

import asyncio
import logging
import sys
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from .models import (
    ScanFeedback,
    MultiScannerFeedback,
    SingleScannerFeedback,
)
from .scan_utils import get_max_severity, is_detected
from ..capabilities import ALL_SCANNER_NAMES

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..config import UnifiedScannerConfig


class ScannerWrapper:
    """
    Deprecated legacy wrapper for historical scanner backends.

    Prefer `UnifiedScannerWrapper`, which routes through
    `skillcamo.unified_scanner` and canonical scanner IDs.
    """

    def __init__(
        self,
        scanner_type: str = "skill-scanner",
        scanner_path: Path | None = None,
        verbose: bool = False,
    ):
        """
        Initialize the scanner wrapper.

        Args:
            scanner_type: Type of scanner to use ("skill-scanner" or "agent-scan")
            scanner_path: Custom path to the scanner module
            verbose: Enable verbose logging
        """
        warnings.warn(
            "ScannerWrapper is deprecated and will be removed in a future release. "
            "Use UnifiedScannerWrapper instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.scanner_type = scanner_type
        self.scanner_path = scanner_path or self._default_scanner_path()
        self.verbose = verbose

    def _default_scanner_path(self) -> Path:
        """Get the default scanner path based on scanner type."""
        project_root = Path(__file__).parent.parent

        if self.scanner_type == "skill-scanner":
            return project_root / "2026_skill_scanner" / "skill-scanner"
        elif self.scanner_type == "agent-scan":
            return project_root / "2026_skill_scanner" / "agent-scan"

        raise ValueError(f"Unknown scanner type: {self.scanner_type}")

    def scan(self, skill_directory: Path) -> ScanFeedback:
        """
        Scan a skill directory and return standardized feedback.

        Args:
            skill_directory: Path to the skill directory to scan

        Returns:
            ScanFeedback with detection results
        """
        if not skill_directory.exists():
            return ScanFeedback(
                detected=False,
                findings=[],
                max_severity="ERROR",
                blocked_rules=[],
                passed_rules=[],
                raw_result={"error": f"Skill directory not found: {skill_directory}"},
            )

        if self.scanner_type == "skill-scanner":
            return self._scan_with_skill_scanner(skill_directory)
        elif self.scanner_type == "agent-scan":
            return self._scan_with_agent_scan(skill_directory)

        raise ValueError(f"Unknown scanner type: {self.scanner_type}")

    def _scan_with_skill_scanner(self, skill_directory: Path) -> ScanFeedback:
        """
        Scan using skill-scanner.

        Args:
            skill_directory: Path to the skill directory

        Returns:
            ScanFeedback with standardized results
        """
        scanner_lib = self.scanner_path

        # Add scanner to Python path
        sys.path.insert(0, str(scanner_lib))

        try:
            from skill_scanner import scan_skill

            if self.verbose:
                logger.info(f"Scanning {skill_directory} with skill-scanner")

            result = scan_skill(skill_directory)

            # Convert findings to dict format
            findings_dict = []
            blocked_rules = []

            for finding in result.findings:
                findings_dict.append({
                    "id": finding.id,
                    "rule_id": finding.rule_id,
                    "category": finding.category.value if finding.category else "unknown",
                    "severity": finding.severity.value if finding.severity else "unknown",
                    "title": finding.title,
                    "description": finding.description,
                    "file_path": str(finding.file_path) if finding.file_path else None,
                    "line_number": finding.line_number,
                    "snippet": finding.snippet,
                })
                blocked_rules.append(finding.rule_id)

            # Determine max severity using efficient utility
            max_severity = get_max_severity(findings_dict)

            return ScanFeedback(
                detected=not result.is_safe,
                findings=findings_dict,
                max_severity=max_severity,
                blocked_rules=list(set(blocked_rules)),
                passed_rules=[],
                raw_result={
                    "skill_name": result.skill_name,
                    "skill_directory": str(result.skill_directory),
                    "is_safe": result.is_safe,
                    "finding_count": len(result.findings),
                },
            )

        except ImportError as e:
            logger.error(f"Failed to import skill-scanner: {e}")
            return ScanFeedback(
                detected=False,
                findings=[],
                max_severity="ERROR",
                blocked_rules=[],
                passed_rules=[],
                raw_result={"error": f"Failed to import skill-scanner: {e}"},
            )
        except Exception as e:
            logger.error(f"Error scanning with skill-scanner: {e}")
            return ScanFeedback(
                detected=False,
                findings=[],
                max_severity="ERROR",
                blocked_rules=[],
                passed_rules=[],
                raw_result={"error": str(e)},
            )
        finally:
            # Remove from path
            if str(scanner_lib) in sys.path:
                sys.path.remove(str(scanner_lib))

    def _scan_with_agent_scan(self, skill_directory: Path) -> ScanFeedback:
        """
        Scan using agent-scan.

        Args:
            skill_directory: Path to the skill directory

        Returns:
            ScanFeedback with standardized results
        """
        scanner_lib = self.scanner_path / "src"

        # Add scanner to Python path
        sys.path.insert(0, str(scanner_lib))

        try:
            from agent_scan.pipelines import InspectArgs, inspect_pipeline

            if self.verbose:
                logger.info(f"Scanning {skill_directory} with agent-scan")

            async def _scan():
                inspect_args = InspectArgs(
                    timeout=10,
                    tokens=[],
                    paths=[str(skill_directory)],
                    all_users=False,
                    scan_skills=True,
                )
                results = await inspect_pipeline(inspect_args)
                return results

            result = asyncio.run(_scan())

            if not result or len(result) == 0:
                return ScanFeedback(
                    detected=False,
                    findings=[],
                    max_severity="SAFE",
                    blocked_rules=[],
                    passed_rules=[],
                    raw_result={"error": "No results from agent-scan"},
                )

            # Process first result
            scan_result = result[0]

            # Extract findings from issues
            findings_dict = []
            blocked_rules = []

            if scan_result.issues:
                for issue in scan_result.issues:
                    findings_dict.append({
                        "id": issue.code,
                        "rule_id": issue.code,
                        "category": "security",
                        "severity": "HIGH",  # agent-scan doesn't expose severity
                        "title": issue.code,
                        "description": issue.message,
                        "file_path": None,
                        "line_number": None,
                        "snippet": None,
                    })
                    blocked_rules.append(issue.code)

            # Determine max severity
            max_severity = "CRITICAL" if findings_dict else "SAFE"

            return ScanFeedback(
                detected=len(findings_dict) > 0,
                findings=findings_dict,
                max_severity=max_severity,
                blocked_rules=list(set(blocked_rules)),
                passed_rules=[],
                raw_result={
                    "path": scan_result.path,
                    "client": scan_result.client,
                    "issue_count": len(scan_result.issues),
                },
            )

        except ImportError as e:
            logger.error(f"Failed to import agent-scan: {e}")
            return ScanFeedback(
                detected=False,
                findings=[],
                max_severity="ERROR",
                blocked_rules=[],
                passed_rules=[],
                raw_result={"error": f"Failed to import agent-scan: {e}"},
            )
        except Exception as e:
            logger.error(f"Error scanning with agent-scan: {e}")
            return ScanFeedback(
                detected=False,
                findings=[],
                max_severity="ERROR",
                blocked_rules=[],
                passed_rules=[],
                raw_result={"error": str(e)},
            )
        finally:
            # Remove from path
            if str(scanner_lib) in sys.path:
                sys.path.remove(str(scanner_lib))


# ============================================================================
# Unified Scanner Wrapper (for unified_scanner integration)
# ============================================================================


class UnifiedScannerWrapper:
    """
    统一扫描器包装器

    直接使用 UnifiedSkillScanner 替换原有的 ScannerWrapper。
    支持统一框架中的全部标准扫描器，并消费标准化结果结构。
    """

    # 支持的扫描器列表（canonical IDs）
    # 直接派生自 capabilities.ALL_SCANNER_NAMES（单一真源），避免手动维护两份列表导致
    # 漂移 —— 历史上 scan_fusion / scan_execscan_trusted / scan_iaep 都曾因漏列而被
    # 误判为 "Unknown scanner"。
    SUPPORTED_SCANNERS = sorted(ALL_SCANNER_NAMES)

    def __init__(
        self,
        enabled_scanners: list[str] | None = None,
        parallel: bool = True,
        verbose: bool = False,
        enable_experiment_logging: bool = False,
        experiment_output_dir: str | Path | None = None,
        progress_callback: Callable | None = None,
        scanner_config: "UnifiedScannerConfig | None" = None,
    ):
        """
        初始化统一扫描器包装器

        Args:
            enabled_scanners: 要启用的扫描器列表，None 表示全部
            parallel: 是否并行执行
            verbose: 详细输出
            enable_experiment_logging: 是否启用实验日志（保存完整 scan_result.json）
            experiment_output_dir: 实验日志输出目录，None 时使用默认值
            progress_callback: 进度回调函数，签名为 callback(current, total, message)
            scanner_config: 已加载的 UnifiedScannerConfig（含 timeout 等配置），None 则从 env 加载
        """
        # 动态导入 unified_scanner
        self._unified_scanner = None
        self._import_unified_scanner()
        normalized_enabled_scanners = None
        if enabled_scanners is not None:
            unknown = [name for name in enabled_scanners if name not in self.SUPPORTED_SCANNERS]
            if unknown:
                raise ValueError(f"Unknown scanner(s): {', '.join(unknown)}")
            normalized_enabled_scanners = list(dict.fromkeys(enabled_scanners))

        # 设置实验日志输出目录
        if experiment_output_dir is None:
            from ...output_paths import get_default_output_root
            experiment_output_dir = get_default_output_root()

        # 初始化扫描器
        sandbox_enabled = bool(
            scanner_config is not None
            and getattr(getattr(scanner_config, "sandbox", None), "enabled", False)
        )
        if self._unified_scanner is not None and sandbox_enabled:
            # 沙盒模式：把扫描委托给一次性 Docker 容器（scanner 逻辑零改动）
            from ..sandbox.scanner import SandboxedSkillScanner
            self.unified_scanner = SandboxedSkillScanner(
                config=scanner_config,
                enabled_scanners=normalized_enabled_scanners,
            )
        elif self._unified_scanner is not None:
            self.unified_scanner = self._unified_scanner.UnifiedSkillScanner(
                enabled_scanners=normalized_enabled_scanners,
                parallel=parallel,
                config=scanner_config,
                enable_experiment_logging=enable_experiment_logging,
                experiment_output_dir=experiment_output_dir,
                progress_callback=progress_callback,
            )
        else:
            logger.warning("UnifiedSkillScanner not available, using mock mode")
            self.unified_scanner = None

        self.verbose = verbose

    def _import_unified_scanner(self) -> None:
        """动态导入 unified_scanner 模块"""
        try:
            try:
                from skillcamo.unified_scanner.scanner import UnifiedSkillScanner
            except ImportError:
                from ..scanner import UnifiedSkillScanner
            self._unified_scanner = type(
                "Module",
                (),
                {"UnifiedSkillScanner": UnifiedSkillScanner}
            )
            logger.info("Successfully imported UnifiedSkillScanner")

        except ImportError as e:
            logger.error(f"Failed to import unified_scanner: {e}")
            self._unified_scanner = None

    @property
    def scanner_type(self) -> str:
        """保持兼容性，返回扫描器类型"""
        return "unified"

    def save_scan_result_external(
        self,
        result: dict,
        iter_dir: Path,
        skill_path: Path | None = None,
        analysis: dict | None = None
    ) -> None:
        """
        保存扫描结果到外部指定的目录（统一日志存储入口）

        Args:
            result: 扫描结果字典
            iter_dir: 迭代目录路径
            skill_path: 可选的技能路径，用于复制 skill 副本
            analysis: 生成器的分析反馈（可选）
        """
        if self.unified_scanner is None:
            logger.warning("UnifiedSkillScanner not available, skipping save")
            return

        self.unified_scanner.save_scan_result_external(
            result=result,
            iter_dir=iter_dir,
            skill_path=skill_path,
            analysis=analysis,
        )

    def scan(self, skill_directory: Path) -> MultiScannerFeedback:
        """
        扫描技能目录

        Args:
            skill_directory: 技能目录路径

        Returns:
            MultiScannerFeedback 包含所有扫描器的结果
        """
        if not skill_directory.exists():
            return MultiScannerFeedback(
                scanners={},
                summary={
                    "all_clean": False,
                    "error": f"Skill directory not found: {skill_directory}",
                },
            )

        if self.unified_scanner is None:
            # Mock 模式：返回空结果
            return self._mock_scan_result(skill_directory)

        # 调用 unified_scanner
        result = self.unified_scanner.scan(skill_directory)

        # --- Retry failed scanners (single pass) ---
        failed_scanners = (
            result.get("summary", {}).get("scanners_failed", [])
        )
        if failed_scanners:
            logger.info(
                "Retrying %d failed scanner(s): %s",
                len(failed_scanners),
                failed_scanners,
            )
            retry_result = self.scan_selective(
                skill_directory, failed_scanners
            )
            # Merge retried SingleScannerFeedback into main result
            parsed = self._parse_unified_result(result)
            for name, fb in retry_result.scanners.items():
                if name in parsed.scanners and fb.max_severity == "ERROR":
                    # Still failing after retry — keep original error
                    continue
                parsed.scanners[name] = fb
            # Recalculate all_clean
            parsed.summary["all_clean"] = all(
                fb.is_clean for fb in parsed.scanners.values()
            )
            return parsed

        # 解析结果
        return self._parse_unified_result(result)

    def scan_selective(self, skill_directory: Path, scanner_names: list[str]) -> MultiScannerFeedback:
        """
        仅扫描指定的 scanner 子集 — 用于 pipeline 重试出错的扫描器。

        Args:
            skill_directory: 技能目录路径
            scanner_names: 要运行的扫描器 canonical ID 列表

        Returns:
            MultiScannerFeedback 仅包含指定扫描器的结果
        """
        if not skill_directory.exists():
            return MultiScannerFeedback(
                scanners={},
                summary={
                    "all_clean": False,
                    "error": f"Skill directory not found: {skill_directory}",
                },
            )

        if self.unified_scanner is None:
            return self._mock_scan_result(skill_directory)

        result = self.unified_scanner.scan_selective(skill_directory, scanner_names)
        return self._parse_unified_result(result)

    def _normalize_scanner_name(self, scanner_name: str) -> str:
        """返回 scanner canonical id。"""
        return scanner_name

    def _parse_unified_result(self, result: dict) -> MultiScannerFeedback:
        """
        解析 unified_scanner 返回的结果

        Args:
            result: unified_scanner.scan() 返回的字典

        Returns:
            MultiScannerFeedback
        """
        scanner_feedbacks = {}

        scanner_results = result.get("scanner_results", {})
        if not isinstance(scanner_results, dict):
            scanner_results = {}

        for scanner_name, scanner_result in scanner_results.items():
            if not isinstance(scanner_result, dict):
                continue

            # 规范化扫描器名称用于内部处理
            normalized_name = self._normalize_scanner_name(scanner_name)

            # 检查错误（顶层 error key 或 metadata.error，适配 scan_execscan 等 adapter 的报错格式）
            metadata_error = (
                isinstance(scanner_result.get("metadata"), dict)
                and scanner_result["metadata"].get("error")
            )
            if scanner_result.get("error") or metadata_error:
                scanner_feedbacks[normalized_name] = SingleScannerFeedback(
                    scanner_name=normalized_name,
                    detected=False,
                    findings=[],
                    max_severity="ERROR",
                    blocked_rules=[],
                    raw_result=scanner_result,
                )
                continue

            # 提取 findings
            findings = scanner_result.get("findings", [])
            if not isinstance(findings, list):
                findings = []

            blocked_rules = []
            for f in findings:
                if isinstance(f, dict):
                    rule_id = (
                        f.get("rule_id")
                        or f.get("id")
                        or f.get("title", "")
                    )
                    blocked_rules.append(rule_id)

            # 确定最大严重级别 using efficient utility
            max_severity = get_max_severity(findings)

            scanner_feedbacks[normalized_name] = SingleScannerFeedback(
                scanner_name=normalized_name,
                detected=is_detected(len(findings) > 0, max_severity),
                findings=findings,
                max_severity=max_severity,
                blocked_rules=blocked_rules,
                raw_result=scanner_result,
            )

        # 从 summary 中获取信息
        summary_data = result.get("summary", {})

        summary = {
            "all_clean": all(
                fb.is_clean for fb in scanner_feedbacks.values()
            ) if scanner_feedbacks else False,
            "total_findings": summary_data.get("total_findings", 0),
            "critical_count": summary_data.get("findings_by_severity", {}).get("critical", 0),
            "high_count": summary_data.get("findings_by_severity", {}).get("high", 0),
            "scanners_used": summary_data.get("scanners_used", []),
            "scanners_failed": summary_data.get("scanners_failed", []),
        }

        return MultiScannerFeedback(
            scanners=scanner_feedbacks,
            summary=summary,
            llm_judgement=result.get("llm_judgement") if isinstance(result.get("llm_judgement"), dict) else None,
        )

    def _mock_scan_result(self, skill_directory: Path) -> MultiScannerFeedback:
        """
        Mock 扫描结果（当 unified_scanner 不可用时）

        Args:
            skill_directory: 技能目录路径

        Returns:
            Mock MultiScannerFeedback
        """
        logger.warning(f"Using mock scan result for {skill_directory}")

        return MultiScannerFeedback(
            scanners={
                "mock": SingleScannerFeedback(
                    scanner_name="mock",
                    detected=False,
                    findings=[],
                    max_severity="SAFE",
                    blocked_rules=[],
                    raw_result={"mock": True},
                )
            },
            summary={
                "all_clean": True,
                "total_findings": 0,
                "critical_count": 0,
                "high_count": 0,
                "scanners_used": ["mock"],
                "scanners_failed": [],
            },
        )
