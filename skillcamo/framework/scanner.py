"""
统一扫描器 - 轻量包装器实现

整合底层扫描器，提供一致的输入输出接口。

特性:
    - 按扫描器分组返回原始输出
    - 并行执行多个扫描器
    - 超时控制和错误隔离
    - 支持启用/禁用特定扫描器

使用示例:
    from unified_scanner import UnifiedSkillScanner

    scanner = UnifiedSkillScanner()
    result = scanner.scan("/path/to/skill")
    # result 是按扫描器分组的原始输出字典
    # 例如: {"scan_cisco": {...}, "scan_hss": {...}, ...}
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _get_default_output_root() -> Path:
    try:
        from ..output_paths import get_default_output_root
    except ImportError:
        from skillcamo.output_paths import get_default_output_root
    return get_default_output_root()

# 支持作为包使用或直接运行
try:
    from unified_scanner.config import UnifiedScannerConfig
    from unified_scanner.capabilities import (
        SCANNER_DISPLAY_NAMES,
        AvailabilityRegistry,
        get_availability_report,
        get_enabled_scanners,
        normalize_scanner_name,
    )
    from unified_scanner.batch import scan_all as scan_all_targets
    from unified_scanner.batch import scan_directory as scan_directory_targets
    from unified_scanner.result_builder import (
        build_error_result,
        build_unified_scan_result,
        calculate_summary,
    )
    from unified_scanner.runner import ScanRunner
    from unified_scanner.logging_store import ExperimentLogStore, save_json_atomic
    from unified_scanner.llm_output_judgement import LLMOutputAdjudicator
    from unified_scanner.scanner_invocations import (
        load_adapter_class,
        scan_cisco,
        scan_with_adapter,
    )
    from skillcamo.framework.paths import (
        get_env_file_path,
    )
    from unified_scanner.models import ThreatCategory
    from unified_scanner.ccsw_provider import resolve_ccsw_provider_env
except ImportError:
    # 直接运行时的导入
    sys.path.insert(0, str(Path(__file__).parent))
    from config import UnifiedScannerConfig
    from capabilities import (
        SCANNER_DISPLAY_NAMES,
        AvailabilityRegistry,
        get_availability_report,
        get_enabled_scanners,
        normalize_scanner_name,
    )
    from batch import scan_all as scan_all_targets
    from batch import scan_directory as scan_directory_targets
    from result_builder import (
        build_error_result,
        build_unified_scan_result,
        calculate_summary,
    )
    from runner import ScanRunner
    from logging_store import ExperimentLogStore, save_json_atomic
    from llm_output_judgement import LLMOutputAdjudicator
    from scanner_invocations import (
        load_adapter_class,
        scan_cisco,
        scan_with_adapter,
    )
    from paths import (
        get_env_file_path,
    )
    from models import ThreatCategory
    from ccsw_provider import resolve_ccsw_provider_env


CLAUDE_BASED_SCANNERS = frozenset({
    "scan_skill_vetter",
    "scan_skill_auditor",
    "scan_skill_slowmist",
})


class UnifiedSkillScanner:
    """
    统一技能扫描器（轻量包装器实现）

    底层扫描器:
    - scan_skill_auditor: ClawGuard Auditor (CG-A) (企业级深度安全分析)
    - scan_cisco: Cisco AI Skill Scanner (静态+YARA+LLM)
    - scan_hss: LLM-based Security Scanner (8维度语义分析)
    - scan_skill_vetter: Skill Vetter (静态代码审查+LLM)
    - scan_skillfortify: SkillFortify (静态分析)
    - scan_skill_slowmist: SlowMist Agent Security (知识库安全模式检测)
    - scan_execscan: Execution-grounded multimodal scanner (多模态执行模拟)
    """

    SCANNER_DISPLAY_NAMES = SCANNER_DISPLAY_NAMES

    def __init__(
        self,
        enabled_scanners: list[str] | None = None,
        parallel: bool = True,
        save_individual_results: bool = False,
        results_dir: str | Path | None = None,
        config: UnifiedScannerConfig | None = None,
        enable_experiment_logging: bool = False,
        experiment_output_dir: str | Path | None = None,
        progress_callback: callable | None = None,
    ):
        """
        初始化统一扫描器

        Args:
            enabled_scanners: 要启用的扫描器列表，None 表示启用所有可用扫描器
            parallel: 是否并行执行多个扫描器
            save_individual_results: 是否保存每个扫描器的单独结果
            results_dir: 单独结果文件的保存目录（默认 {PROJECT_ROOT}/outputs）
            config: 扫描器配置对象
            enable_experiment_logging: 是否启用实验日志记录
            experiment_output_dir: 实验日志输出根目录（默认 {PROJECT_ROOT}/outputs/experiment_logs）
            progress_callback: 进度回调函数，签名为 callback(current, total, message)
        """
        # 加载配置：仅从项目根目录的 .env 文件加载
        if config is None:
            root_env_file = get_env_file_path()

            if root_env_file.exists():
                self.config = UnifiedScannerConfig.from_env_file(root_env_file)
            else:
                self.config = UnifiedScannerConfig.from_env()
        else:
            self.config = config

        self.save_individual_results = save_individual_results
        if results_dir is None:
            results_dir = _get_default_output_root()
        self.results_dir = Path(results_dir)

        self.enable_experiment_logging = enable_experiment_logging
        if experiment_output_dir is None:
            experiment_output_dir = _get_default_output_root() / "experiment_logs"
        self.experiment_output_dir = Path(experiment_output_dir)
        self._experiment_store = ExperimentLogStore(
            enabled=enable_experiment_logging,
            output_dir=self.experiment_output_dir,
        )

        self._availability = AvailabilityRegistry(cache={}, reasons={})
        self._scanner_availability = self._availability.cache
        self._availability_reasons = self._availability.reasons

        # 进度回调（线程安全）
        self._progress_callback: Callable | None = progress_callback
        self._progress_lock = threading.Lock() if progress_callback else None

        # 确定要使用的扫描器（canonical scanner IDs）
        if enabled_scanners is None:
            self.enabled_scanners = get_enabled_scanners(self.config, self._availability)
        else:
            # 显式指定时保留所有 scanner（包括不可用的）
            # 不可用 scanner 会在 ScanRunner 中产生 error result，而非被静默丢弃
            normalized_enabled_scanners = []
            for scanner_name in enabled_scanners:
                normalized_name = self._normalize_scanner_name(scanner_name)
                if normalized_name not in normalized_enabled_scanners:
                    normalized_enabled_scanners.append(normalized_name)
                    # 记录不可用 scanner 的原因
                    if not self._is_scanner_available(scanner_name):
                        reason = self._availability_reasons.get(normalized_name, "unknown")
                        logger.warning(
                            "Scanner '%s' explicitly requested but not available: %s",
                            scanner_name, reason,
                        )
            self.enabled_scanners = normalized_enabled_scanners

        # 设置 Claude CLI 并发限制（只设置一次，所有实例共享）
        self._init_claude_cli_concurrent_limit()

    def _init_claude_cli_concurrent_limit(self) -> None:
        """初始化 Claude CLI 并发限制"""
        try:
            from unified_scanner.adapters.skill_scanner_base import SkillBasedScannerAdapter
        except ImportError:
            from adapters.skill_scanner_base import SkillBasedScannerAdapter

        # 记录配置值
        logger.info(f"Initializing Claude CLI concurrent limit: {self.config.max_claude_concurrent}")

        SkillBasedScannerAdapter.set_claude_cli_concurrent_limit(
            self.config.max_claude_concurrent
            # 注意：不使用 force=True，以保持全局并发控制的一致性
        )

    def _is_scanner_available(self, scanner_name: str) -> bool:
        """检查扫描器是否可用"""
        return self._availability.is_available(scanner_name)

    def _normalize_scanner_name(self, scanner_name: str) -> str:
        """规范化扫描器名称（canonical scanner id）

        Args:
            scanner_name: 扫描器名称

        Returns:
            标准化的扫描器名称
        """
        return normalize_scanner_name(scanner_name)

    def _report_progress(self, current: int, total: int, message: str) -> None:
        """线程安全的进度报告

        Args:
            current: 当前进度
            total: 总数
            message: 进度消息
        """
        if self._progress_callback and self._progress_lock:
            with self._progress_lock:
                self._progress_callback(current, total, message)

    def _get_enabled_scanners(self) -> list[str]:
        """获取配置中启用的扫描器"""
        return get_enabled_scanners(self.config, self._availability)

    def scan(self, skill_path: str | Path) -> dict:
        """
        扫描单个技能目录 — 走 batch 路径 (batch=1)

        Args:
            skill_path: 技能目录路径

        Returns:
            按扫描器分组的原始输出字典，例如：
            {
                "scan_cisco": {...},  # Cisco 原始输出
                "scan_hss": {...},    # HSS 原始输出
                ...
                "summary": {...},     # 扫描摘要
            }
        """
        skill_path = Path(skill_path)

        if not skill_path.exists():
            return build_error_result(skill_path, "Skill path does not exist", "file_not_found")

        batch_result = self.scan_all([skill_path])
        items = batch_result.get("items", [])
        return items[0] if items else build_error_result(skill_path, "Empty batch result", "batch_error")

    def _scan_single_skill(self, skill_path: str | Path) -> dict:
        """
        扫描单个 skill 的所有 scanner（始终并行）— 供 scan_batch 回调

        Args:
            skill_path: 技能目录路径

        Returns:
            标准化扫描结果字典
        """
        skill_path = Path(skill_path)

        if not skill_path.exists():
            return build_error_result(skill_path, "Skill path does not exist", "file_not_found")

        # 创建 ScanRunner，始终并行执行所有 scanner
        runner = ScanRunner(
            enabled_scanners=self.enabled_scanners,
            is_available=self._is_scanner_available,
            normalize_name=self._normalize_scanner_name,
            get_scan_method=lambda name: getattr(self, f"_{name}"),
            get_timeout=lambda s: self.config.get_scanner_timeout(s),
            max_workers=self.config.max_workers,
            global_timeout=max((self.config.get_scanner_timeout(s) for s in self.enabled_scanners), default=0),
            max_retries=self.config.max_retries,
            skill_name=skill_path.name,
            progress_callback=self._report_progress,
        )

        raw_results = runner.run_parallel(skill_path)
        raw_results, top_level_judgement = self._apply_llm_judgement(raw_results)

        # 记录超时扫描器（日志）
        timeout_scanners = [
            name for name, r in raw_results.items()
            if isinstance(r, dict) and r.get("timed_out")
        ]
        if timeout_scanners:
            logger.warning(
                "超时扫描器 (重试耗尽，结果已排除): %s",
                ", ".join(timeout_scanners),
            )

        duration_ms = raw_results.get("_duration_ms", 0)
        summary = calculate_summary(raw_results, duration_ms)

        # 如果启用实验日志，初始化会话并保存结果（过滤超时）
        if self.enable_experiment_logging:
            self._init_experiment_session()
            iter_dir = self._create_iteration_dir(skill_path)
            filtered_results = {
                k: v for k, v in raw_results.items()
                if not (isinstance(v, dict) and v.get("timed_out"))
            }
            filtered_summary = calculate_summary(filtered_results, duration_ms)
            payload = build_unified_scan_result(skill_path, filtered_results, filtered_summary)
            if isinstance(top_level_judgement, dict):
                payload["llm_judgement"] = top_level_judgement
            self._save_scan_result(payload, iter_dir)

        payload = build_unified_scan_result(skill_path, raw_results, summary)
        if isinstance(top_level_judgement, dict):
            payload["llm_judgement"] = top_level_judgement
        return payload

    def scan_selective(self, skill_path: str | Path, scanner_names: list[str]) -> dict:
        """
        仅扫描指定的 scanner 子集 — 用于 pipeline 重试出错的扫描器。

        复用 ``_scan_single_skill`` 的核心逻辑，但将 enabled_scanners 过滤为
        仅包含 *scanner_names* 中指定的扫描器。

        Args:
            skill_path: 技能目录路径
            scanner_names: 要运行的扫描器 canonical ID 列表

        Returns:
            标准化扫描结果字典（与 ``scan()`` 返回格式一致）
        """
        skill_path = Path(skill_path)

        if not skill_path.exists():
            return build_error_result(skill_path, "Skill path does not exist", "file_not_found")

        # 过滤 enabled_scanners：只保留指定的、且实际可用的
        filtered = [s for s in scanner_names if s in self.enabled_scanners]
        if not filtered:
            return build_error_result(skill_path, "No scanners to run", "no_scanners")

        runner = ScanRunner(
            enabled_scanners=filtered,
            is_available=self._is_scanner_available,
            normalize_name=self._normalize_scanner_name,
            get_scan_method=lambda name: getattr(self, f"_{name}"),
            get_timeout=lambda s: self.config.get_scanner_timeout(s),
            max_workers=self.config.max_workers,
            global_timeout=max((self.config.get_scanner_timeout(s) for s in filtered), default=0),
            max_retries=self.config.max_retries,
            skill_name=skill_path.name,
            progress_callback=self._report_progress,
        )

        raw_results = runner.run_parallel(skill_path)
        raw_results, top_level_judgement = self._apply_llm_judgement(raw_results)

        duration_ms = raw_results.get("_duration_ms", 0)
        summary = calculate_summary(raw_results, duration_ms)

        payload = build_unified_scan_result(skill_path, raw_results, summary)
        if isinstance(top_level_judgement, dict):
            payload["llm_judgement"] = top_level_judgement
        return payload

    def _apply_llm_judgement(self, raw_results: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
        """Judge Claude-based scanner outputs and map them into the unified scanner result shape."""
        judgement_config = getattr(self.config, "llm_judgement", None)
        if judgement_config is None or not getattr(judgement_config, "enabled", False):
            return raw_results, None

        claude_scanners = [
            name for name, output in raw_results.items()
            if name in CLAUDE_BASED_SCANNERS and isinstance(output, dict) and not name.startswith("_")
        ]
        if not claude_scanners:
            return raw_results, None

        adjudicator = LLMOutputAdjudicator(
            provider=judgement_config.provider,
            model=judgement_config.model,
            api_key=judgement_config.api_key,
            base_url=judgement_config.base_url,
            timeout=judgement_config.timeout,
        )

        updated_results = dict(raw_results)
        top_level_judgement: dict[str, Any] | None = None

        for index, scanner_name in enumerate(claude_scanners):
            scanner_output = raw_results.get(scanner_name, {})
            judgement = adjudicator.adjudicate(scanner_name, scanner_output)
            if not getattr(judgement_config, "save_audit", True):
                judgement = {key: value for key, value in judgement.items() if key != "audit"}
            updated_results[scanner_name] = self._merge_judgement_into_scanner_result(
                scanner_name,
                scanner_output,
                judgement,
            )
            if len(claude_scanners) == 1 and index == 0:
                top_level_judgement = judgement

        return updated_results, top_level_judgement

    def _merge_judgement_into_scanner_result(
        self,
        scanner_name: str,
        scanner_output: dict[str, Any],
        judgement: dict[str, Any],
    ) -> dict[str, Any]:
        """Project a scanner-level LLM judgement into the standard scanner result fields."""
        if not isinstance(scanner_output, dict):
            scanner_output = {}

        metadata = scanner_output.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        merged = {
            **scanner_output,
            "metadata": {**metadata, "scanner": scanner_name},
            "llm_judgement": judgement,
        }

        if judgement.get("status") != "success":
            merged["findings"] = []
            merged["error"] = judgement.get("error") or "LLM judgement failed"
            merged["error_type"] = "LLMJudgementError"
            merged["metadata"] = {**merged["metadata"], "is_safe": None}
            return merged

        severity = str(judgement.get("severity", "LOW")).upper()
        reason = str(judgement.get("reason", ""))
        evidence = judgement.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = [str(evidence)]

        finding = {
            "id": f"{scanner_name}-llm-judgement",
            "source_scanner": scanner_name,
            "severity": severity,
            "category": ThreatCategory.OTHER.value,
            "title": "LLM judgement",
            "description": reason,
            "file_path": None,
            "line_number": None,
            "snippet": None,
            "remediation": None,
            "metadata": {
                "evidence": [str(item) for item in evidence],
                "confidence": judgement.get("confidence"),
            },
        }
        merged["findings"] = [finding]
        merged["metadata"] = {
            **merged["metadata"],
            "is_safe": severity not in {"CRITICAL", "HIGH"},
        }
        merged.pop("error", None)
        merged.pop("error_type", None)
        return merged

    def _load_adapter_class(self, module_name: str, class_name: str):
        """按包模式优先加载适配器类，回退到脚本模式导入。"""
        return load_adapter_class(module_name, class_name)

    def _scan_with_adapter(
        self,
        skill_path: Path,
        *,
        scanner_name: str,
        module_name: str,
        class_name: str,
        adapter_kwargs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """使用统一适配器调用路径执行扫描。"""
        return scan_with_adapter(
            skill_path,
            scanner_name=scanner_name,
            module_name=module_name,
            class_name=class_name,
            timeout=self.config.get_scanner_timeout(scanner_name),
            adapter_kwargs=adapter_kwargs,
            loader=self._load_adapter_class,
        )

    # ==================== 底层扫描器调用方法 ====================

    def _scan_cisco(self, skill_path: Path) -> dict:
        """
        调用 Cisco AI Skill Scanner

        源模块: scan_cisco/scan_cisco/
        入口类: scan_cisco.core.scanner.SkillScanner

        返回原始扫描输出，不进行字段映射。
        """
        model = self.config.scan_cisco.model
        base_url = self.config.scan_cisco.base_url
        api_key = self.config.scan_cisco.api_key
        timeout = self.config.get_scanner_timeout("scan_cisco")
        return scan_cisco(skill_path, model=model, base_url=base_url, api_key=api_key, timeout=timeout)

    def _scan_hss(self, skill_path: Path) -> dict:
        """
        调用 HSS (Hybrid Security Scanner)

        使用 ScanHssAdapter 适配器，返回原始扫描输出。
        """
        model = self.config.scan_hss.model
        base_url = self.config.scan_hss.base_url
        adapter_kwargs: dict[str, Any] = {}
        if model:
            adapter_kwargs["model"] = model
        if base_url:
            adapter_kwargs["base_url"] = base_url
        try:
            return self._scan_with_adapter(
                skill_path,
                scanner_name="scan_hss",
                module_name="scan_hss",
                class_name="ScanHssAdapter",
                adapter_kwargs=adapter_kwargs or None,
            )
        except Exception as e:
            return {
                "error": str(e),
                "error_type": type(e).__name__,
                "scanner": "scan_hss",
            }

    def _scan_skill_vetter(self, skill_path: Path) -> dict:
        """
        调用 Skill Vetter (Claude Code)

        使用 ScanSkillVetterAdapter 适配器。
        """
        adapter_kwargs: dict[str, Any] = {}
        if self.config.scan_skill_vetter.model:
            adapter_kwargs["model"] = self.config.scan_skill_vetter.model
        self._apply_ccsw_provider(self.config.scan_skill_vetter, adapter_kwargs)
        return self._scan_with_adapter(
            skill_path,
            scanner_name="scan_skill_vetter",
            module_name="scan_skill_vetter",
            class_name="ScanSkillVetterAdapter",
            adapter_kwargs=adapter_kwargs or None,
        )

    def _apply_ccsw_provider(self, scanner_cfg, adapter_kwargs: dict[str, Any]) -> None:
        """若 scanner 配了 ccsw_provider，解析其 ANTHROPIC_* env 注入 adapter_kwargs。

        与 KG 增强（可选、失败即跳过）不同：provider 是实验自变量，解析失败时
        让 CcswProviderError 冒泡中断，避免静默回退到官方 Claude 污染实验数据。
        """
        if not scanner_cfg.ccsw_provider:
            return
        # 沙盒容器里没有 ccsw 二进制 / ~/.ccsw：宿主已在外层 resolve 好并经
        # SANDBOX_CCSW_ENV（JSON）注入进来，直接用，避免容器内调 ccsw 失败。
        injected = os.environ.get("SANDBOX_CCSW_ENV")
        if injected:
            import json as _json
            adapter_kwargs["provider_env"] = _json.loads(injected)
            return
        adapter_kwargs["provider_env"] = resolve_ccsw_provider_env(
            scanner_cfg.ccsw_provider
        )

    def _scan_skill_auditor(self, skill_path: Path) -> dict:
        """
        调用 ClawGuard Auditor (CG-A)

        使用 ScanSkillAuditorAdapter 适配器。
        """
        adapter_kwargs: dict[str, Any] = {}
        if self.config.scan_skill_auditor.model:
            adapter_kwargs["model"] = self.config.scan_skill_auditor.model
        self._apply_ccsw_provider(self.config.scan_skill_auditor, adapter_kwargs)
        return self._scan_with_adapter(
            skill_path,
            scanner_name="scan_skill_auditor",
            module_name="scan_skill_auditor",
            class_name="ScanSkillAuditorAdapter",
            adapter_kwargs=adapter_kwargs or None,
        )

    def _scan_skillfortify(self, skill_path: Path) -> dict:
        """调用嵌入的 SkillFortify 扫描器.

        扫描器路径: unified_scanner/skillfortify/
        支持: Claude Code skills (.claude/skills/*.md) 和 Standalone SKILL.md (dir/SKILL.md)

        返回适配后的扫描结果。
        """
        return self._scan_with_adapter(
            skill_path,
            scanner_name="scan_skillfortify",
            module_name="scan_skillfortify",
            class_name="ScanSkillfortifyAdapter",
        )

    def _scan_skill_slowmist(self, skill_path: Path) -> dict:
        """调用 SlowMist Agent Security 扫描器.

        扫描器路径: scan_skill_slowmist/
        通过 Claude CLI 调用 slowmist skill 进行安全审查。

        返回适配后的扫描结果。
        """
        adapter_kwargs: dict[str, Any] = {}
        if self.config.scan_skill_slowmist.model:
            adapter_kwargs["model"] = self.config.scan_skill_slowmist.model
        self._apply_ccsw_provider(self.config.scan_skill_slowmist, adapter_kwargs)
        return self._scan_with_adapter(
            skill_path,
            scanner_name="scan_skill_slowmist",
            module_name="scan_skill_slowmist",
            class_name="ScanSkillSlowmistAdapter",
            adapter_kwargs=adapter_kwargs or None,
        )

    def _scan_execscan(self, skill_path: Path) -> dict:
        """调用 scan_execscan 扫描器。"""
        adapter_kwargs: dict[str, Any] = {}
        if self.config.scan_execscan.model:
            adapter_kwargs["model"] = self.config.scan_execscan.model
        if self.config.scan_execscan.model_a:
            adapter_kwargs["model_a"] = self.config.scan_execscan.model_a
        if self.config.scan_execscan.model_b:
            adapter_kwargs["model_b"] = self.config.scan_execscan.model_b
        if self.config.scan_execscan.api_key:
            adapter_kwargs["api_key"] = self.config.scan_execscan.api_key
        if self.config.scan_execscan.base_url:
            adapter_kwargs["base_url"] = self.config.scan_execscan.base_url
        return self._scan_with_adapter(
            skill_path,
            scanner_name="scan_execscan",
            module_name="scan_execscan",
            class_name="ScanExecscanAdapter",
            adapter_kwargs=adapter_kwargs or None,
        )

    # ==================== 公共方法 ====================

    def scan_all(self, skill_paths: list[str | Path]) -> dict[str, Any]:
        """批量扫描多个技能目录并返回标准化批量结果。"""
        return scan_all_targets(
            skill_paths,
            scan_one=self._scan_single_skill,
            max_skill_workers=self.config.max_skill_workers,
        )

    def scan_fast_fail(self, skill_path: str | Path) -> dict:
        """
        快速失败模式扫描 - 串行执行scanner，发现高危问题立即停止

        适用于大量skills筛选场景，一旦发现critical/high问题就跳过剩余scanner。
        这是特定功能模式，不走 batch 路径。

        Args:
            skill_path: 技能目录路径

        Returns:
            扫描结果字典，格式与scan()相同
        """
        skill_path = Path(skill_path)

        if not skill_path.exists():
            return build_error_result(skill_path, "Skill path does not exist", "file_not_found")

        runner = ScanRunner(
            enabled_scanners=self.enabled_scanners,
            is_available=self._is_scanner_available,
            normalize_name=self._normalize_scanner_name,
            get_scan_method=lambda name: getattr(self, f"_{name}"),
            get_timeout=lambda s: self.config.get_scanner_timeout(s),
            max_workers=self.config.max_workers,
            global_timeout=max((self.config.get_scanner_timeout(s) for s in self.enabled_scanners), default=0),
            max_retries=self.config.max_retries,
            skill_name=skill_path.name,
            progress_callback=self._report_progress,
        )
        results = runner.run_fast_fail(skill_path)
        duration_ms = results.get("_duration_ms", 0)
        results, top_level_judgement = self._apply_llm_judgement(results)
        summary = calculate_summary(results, duration_ms)
        payload = build_unified_scan_result(skill_path, results, summary)
        if isinstance(top_level_judgement, dict):
            payload["llm_judgement"] = top_level_judgement
        return payload

    def scan_directory(
        self, directory: str | Path, recursive: bool = False, pattern: str = "SKILL.md"
    ) -> dict[str, Any]:
        """扫描目录中的所有技能并返回标准化批量结果。"""
        return scan_directory_targets(
            directory,
            recursive=recursive,
            pattern=pattern,
            scan_one=self._scan_single_skill,
            max_skill_workers=self.config.max_skill_workers,
        )

    def list_available_scanners(self) -> dict[str, str]:
        """列出所有可用的扫描器"""
        return {
            name: display_name
            for name, display_name in self.SCANNER_DISPLAY_NAMES.items()
            if self._is_scanner_available(name)
        }

    def get_availability_report(self) -> dict[str, dict[str, Any]]:
        """获取所有扫描器的可用性报告

        Returns:
            {
                "scan_cisco": {"available": True, "display_name": "...", "reason": None},
                "scan_hss": {"available": False, "display_name": "...", "reason": "..."},
                ...
            }
        """
        return get_availability_report(self._availability)

    def _sanitize_filename(self, name: str) -> str:
        """清理文件名中的特殊字符"""
        return name.replace("/", "-").replace("\\", "-")

    def save_result(
        self,
        result: dict,
        output_path: str | Path,
    ) -> None:
        """
        保存扫描结果到 JSON 文件（线程安全）

        Args:
            result: scan() 方法返回的结果字典
            output_path: 输出文件路径
        """
        save_json_atomic(result, output_path)

    def save_result_atomic(
        self,
        result: dict,
        output_path: str | Path,
    ) -> None:
        """
        原子性保存扫描结果（委托给 save_result）

        使用写入-重命名模式确保原子性，避免多线程写入冲突。

        Args:
            result: scan() 方法返回的结果字典
            output_path: 输出文件路径
        """
        self.save_result(result, output_path)

    # ==================== 实验日志方法 ====================

    def _init_experiment_session(self) -> None:
        """初始化实验会话，创建时间戳目录"""
        self._experiment_store.ensure_session()

    def _create_iteration_dir(self, skill_path: Path) -> Path:
        """创建新的迭代目录并复制skill

        Args:
            skill_path: 原始skill路径

        Returns:
            迭代目录路径
        """
        return self._experiment_store.create_iteration_dir(skill_path)

    def _save_scan_result(self, result: dict, iter_dir: Path, analysis: dict | None = None) -> None:
        """保存扫描结果到迭代目录

        Args:
            result: 扫描结果字典
            iter_dir: 迭代目录路径
            analysis: 生成器的分析反馈（可选）
        """
        self._experiment_store.save_scan_result(result, iter_dir, analysis)

    def save_scan_result_external(
        self,
        result: dict,
        iter_dir: Path,
        skill_path: Path | None = None,
        analysis: dict | None = None
    ) -> None:
        """保存扫描结果到外部指定的目录（统一日志存储入口）

        这是统一的日志存储入口点，用于替代 orchestrator 中的 _save_attempt。
        保存完整的扫描结果和生成器的分析反馈。

        Args:
            result: 扫描结果字典
            iter_dir: 迭代目录路径
            skill_path: 可选的技能路径，用于复制 skill 副本
            analysis: 生成器的分析反馈（可选）
        """
        self._experiment_store.save_scan_result_external(result, iter_dir, skill_path, analysis)

    def finalize_experiment_session(self) -> Path:
        """结束实验会话，生成最终摘要

        Returns:
            实验目录路径
        """
        return self._experiment_store.finalize_session()

# ==================== 便捷函数 ====================

def create_scanner(
    enabled_scanners: list[str] | None = None,
    save_individual_results: bool = False,
    results_dir: str | Path | None = None,
    enable_experiment_logging: bool = False,
    experiment_output_dir: str | Path | None = None,
) -> UnifiedSkillScanner:
    """创建统一扫描器实例的便捷函数"""
    return UnifiedSkillScanner(
        enabled_scanners=enabled_scanners,
        save_individual_results=save_individual_results,
        results_dir=results_dir,
        enable_experiment_logging=enable_experiment_logging,
        experiment_output_dir=experiment_output_dir,
    )


def quick_scan(
    skill_path: str | Path,
    save_individual_results: bool = False,
    results_dir: str | Path | None = None,
    enable_experiment_logging: bool = False,
    experiment_output_dir: str | Path | None = None,
) -> dict:
    """快速扫描单个技能（使用默认设置）"""
    scanner = UnifiedSkillScanner(
        save_individual_results=save_individual_results,
        results_dir=results_dir,
        enable_experiment_logging=enable_experiment_logging,
        experiment_output_dir=experiment_output_dir,
    )
    return scanner.scan(skill_path)
