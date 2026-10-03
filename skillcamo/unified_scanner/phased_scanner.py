"""
分阶段技能扫描器

实现3阶段扫描策略：
- 阶段1: 快速本地扫描 (scan_cisco, scan_skillfortify)
- 阶段2: Claude CLI扫描 (scan_skill_vetter, scan_skill_auditor, scan_skill_slowmist)
- 阶段3: 外部API扫描 (scan_hss, scan_execscan, scan_fusion)

发现有害立即停止后续阶段。
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable

# 导入现有模块
try:
    from unified_scanner.scanner import UnifiedSkillScanner
    from unified_scanner.runner import ScanRunner
    from unified_scanner.result_builder import calculate_summary, build_error_result, build_unified_scan_result
except ImportError:
    from scanner import UnifiedSkillScanner  # type: ignore[import-not-found]
    from runner import ScanRunner  # type: ignore[import-not-found,no-redef]
    from result_builder import calculate_summary, build_error_result, build_unified_scan_result  # type: ignore[import-not-found,no-redef]

logger = logging.getLogger(__name__)


class PhasedSkillScanner:
    """
    分阶段技能扫描器

    按照速度和资源消耗将scanner分为3个阶段，发现高危问题立即停止。
    """

    # 阶段定义
    PHASES = {
        1: {
            "name": "快速本地扫描",
            "scanners": ["scan_cisco", "scan_skillfortify"],
            "description": "静态分析+YARA规则，无网络依赖",
        },
        2: {
            "name": "Claude CLI扫描",
            "scanners": ["scan_skill_vetter", "scan_skill_auditor", "scan_skill_slowmist"],
            "description": "基于Claude CLI的skill扫描（受全局Semaphore限制并发）",
        },
        3: {
            "name": "外部API扫描",
            "scanners": ["scan_hss", "scan_execscan", "scan_fusion"],
            "description": "需要外部API调用的扫描器",
        },
    }

    _META_RESULT_KEYS = frozenset({"early_stop", "phase_failures"})

    def _phase_scanners(self, phase_config: dict[str, Any]) -> list[str]:
        """返回阶段中的 scanner 列表。"""
        return list(phase_config.get("scanners", []))

    def _raw_scanner_results(self, results: dict[str, Any]) -> dict[str, Any]:
        """返回仅包含 scanner 结果和内部 duration 元数据的字典。"""
        return {
            key: value
            for key, value in results.items()
            if key not in self._META_RESULT_KEYS
        }

    def __init__(
        self,
        config: Any = None,
        enable_phase_3: bool = True,
        exclude_scanners: list[str] | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ):
        """
        初始化分阶段扫描器

        Args:
            config: UnifiedScannerConfig 配置对象
            enable_phase_3: 是否启用阶段3（外部API扫描）
            exclude_scanners: 要排除的扫描器列表（如 ["scan_hss"]）
            progress_callback: 进度回调函数
        """
        self.config = config
        self.enable_phase_3 = enable_phase_3
        self._exclude_scanners = set(exclude_scanners or [])
        self._progress_callback = progress_callback

        # 创建基础扫描器（用于单个scanner调用）
        self._base_scanner = UnifiedSkillScanner(config=config, parallel=False)

        # 预绑定 scanner 方法引用，避免运行时 lambda/getattr 开销
        self._scan_method_cache: dict[str, Callable[[Path], dict]] = {}

    def _get_scan_method(self, scanner_name: str) -> Callable[[Path], dict]:
        """获取 scanner 扫描方法（带缓存）。"""
        if scanner_name not in self._scan_method_cache:
            self._scan_method_cache[scanner_name] = getattr(
                self._base_scanner, f"_{scanner_name}"
            )
        return self._scan_method_cache[scanner_name]

    def _get_scanner_timeout(self, scanner_name: str) -> int:
        """获取 scanner 超时配置，安全处理 None config。"""
        if self.config is not None:
            return self.config.get_scanner_timeout(scanner_name)
        # 默认超时 120 秒
        return 120

    def _extract_error_info(self, result: dict) -> tuple[bool, str]:
        """
        从扫描结果中提取错误信息。

        Args:
            result: 扫描器返回的结果字典

        Returns:
            (has_error, error_type) 元组
        """
        # 防御性检查：确保 result 是字典
        if not isinstance(result, dict):
            logger.warning(
                f"Non-dict result passed to _extract_error_info: {type(result).__name__}"
            )
            return (True, f"InvalidResultType:{type(result).__name__}")

        has_error = result.get("error") or result.get("metadata", {}).get("error")
        error_type = (
            result.get("error_type") or
            result.get("metadata", {}).get("error_type") or
            "Unknown"
        )
        return bool(has_error), error_type

    def list_available_phases(self) -> list[int]:
        """获取可用的阶段列表"""
        available = []
        all_scanners = self._base_scanner.list_available_scanners()

        for phase_num, phase_config in self.PHASES.items():
            if phase_num == 3 and not self.enable_phase_3:
                continue

            # 检查该阶段是否有可用的scanner
            phase_scanners = [
                s for s in self._phase_scanners(phase_config)
                if s in all_scanners
            ]

            if phase_scanners:
                available.append(phase_num)

        return available

    def scan_phased(self, skill_path: str | Path) -> dict:
        """
        分阶段扫描skill

        Args:
            skill_path: 技能目录路径

        Returns:
            扫描结果字典，包含：
            - 各scanner的原始结果
            - summary: 扫描摘要
            - early_stop: 如果提前停止，包含停止原因
        """
        skill_path = Path(skill_path)

        if not skill_path.exists():
            return build_error_result(skill_path, "Skill path does not exist", "file_not_found")

        results: dict[str, Any] = {}
        all_phases = self.list_available_phases()
        summary = calculate_summary(results, self._duration_ms(results))

        logger.debug(f"开始分阶段扫描: {skill_path.name}")
        logger.debug(f"可用阶段: {all_phases}")

        for phase_num in all_phases:
            phase_config = self.PHASES[phase_num]

            logger.info(f"  阶段{phase_num}: {phase_config['name']}")
            if self._progress_callback:
                self._progress_callback(phase_num, len(all_phases), f"阶段{phase_num}: {phase_config['name']}")

            phase_result = self._run_phase(skill_path, phase_config, results)
            results.update(phase_result)

            # 计算当前摘要
            raw_results = self._raw_scanner_results(results)
            summary = calculate_summary(raw_results, self._duration_ms(raw_results))

            # 检查是否有有害发现
            if summary.critical > 0 or summary.high > 0:
                # 有害！停止后续阶段
                stop_reason = f"发现威胁: critical={summary.critical}, high={summary.high}"
                logger.info(f"  ✓ {stop_reason}，停止后续阶段")
                results["early_stop"] = {
                    "phase": phase_num,
                    "phase_name": phase_config["name"],
                    "reason": stop_reason,
                    "critical": summary.critical,
                    "high": summary.high,
                }
                break

            # 检查是否有scanner失败
            if summary.scanners_failed:
                # 构建详细的错误信息
                error_details = []
                for scanner_name in summary.scanners_failed:
                    if scanner_name in results:
                        result = results[scanner_name]
                        # 防御性检查：确保 result 是字典
                        if not isinstance(result, dict):
                            error_details.append(f"{scanner_name}: InvalidResultType({type(result).__name__})")
                            continue
                        error_type = result.get("error_type", "Unknown")
                        error_msg = result.get("error", "")
                        if error_msg:
                            error_details.append(f"{scanner_name}: {error_type} ({error_msg[:50]})")
                        else:
                            error_details.append(f"{scanner_name}: {error_type}")
                    else:
                        error_details.append(f"{scanner_name}: 未找到结果")

                logger.warning(f"  ✗ 阶段{phase_num}有scanner失败:")
                for detail in error_details:
                    logger.warning(f"    - {detail}")

                # 不停止，继续下一阶段（其他scanner可能成功），但记录失败信息
                results["phase_failures"] = results.get("phase_failures", [])
                results["phase_failures"].append({
                    "phase": phase_num,
                    "scanners_failed": summary.scanners_failed.copy(),
                    "error_details": error_details,
                })

        raw_results = self._raw_scanner_results(results)
        raw_results, top_level_judgement = self._base_scanner._apply_llm_judgement(raw_results)
        summary = calculate_summary(raw_results, self._duration_ms(raw_results))
        final_result = build_unified_scan_result(skill_path, raw_results, summary)
        if isinstance(top_level_judgement, dict):
            final_result["llm_judgement"] = top_level_judgement
        if "early_stop" in results:
            final_result["early_stop"] = results["early_stop"]
        if "phase_failures" in results:
            final_result["phase_failures"] = results["phase_failures"]
        return final_result

    def _run_phase(
        self,
        skill_path: Path,
        phase_config: dict,
        existing_results: dict,
    ) -> dict:
        """
        运行单个阶段的所有 scanner。

        Args:
            skill_path: 技能路径
            phase_config: 阶段配置
            existing_results: 已有结果（用于跳过已运行的scanner）

        Returns:
            本阶段scanner的结果字典
        """
        phase_scanners = self._phase_scanners(phase_config)

        # 过滤出可用且未运行的scanner，并排除指定scanner
        available_scanners = self._base_scanner.list_available_scanners()
        scanners_to_run = [
            s for s in phase_scanners
            if s in available_scanners
            and s not in existing_results
            and s not in self._exclude_scanners
        ]

        if not scanners_to_run:
            excluded_in_phase = [s for s in phase_scanners if s in self._exclude_scanners]
            if excluded_in_phase:
                logger.debug(f"    阶段scanner已排除: {excluded_in_phase}")
            else:
                logger.debug("    阶段无可运行的scanner")
            return {}

        logger.debug(f"    运行scanner: {scanners_to_run}")

        start_time = time.time()
        phase_progress_callback = None
        if self._progress_callback:
            def _on_scanner_progress(current: int, total: int, message: str) -> None:
                self._progress_callback(current, total, message)
            phase_progress_callback = _on_scanner_progress

        runner = ScanRunner(
            enabled_scanners=scanners_to_run,
            is_available=lambda s: s in available_scanners,
            normalize_name=self._base_scanner._normalize_scanner_name,
            get_scan_method=self._get_scan_method,
            get_timeout=lambda s: self._get_scanner_timeout(s),
            max_workers=getattr(self.config, 'max_workers', 5) if self.config else 5,
            global_timeout=max((self._get_scanner_timeout(s) for s in scanners_to_run), default=0),
            max_retries=getattr(self.config, 'max_retries', 3) if self.config else 3,
            skill_name=skill_path.name,
            progress_callback=phase_progress_callback,
        )
        results = runner.run_parallel(skill_path)

        duration_ms = int((time.time() - start_time) * 1000)
        results["_phase_duration_ms"] = duration_ms

        return results

    def _duration_ms(self, scanner_results: dict) -> int:
        """汇总 phase duration 元数据。"""
        return sum(
            value for key, value in scanner_results.items()
            if key.endswith("_duration_ms") and isinstance(value, int)
        )

    def _create_error_summary(self, skill_path: str, error_type: str) -> dict:
        """创建错误摘要"""
        return {
            "total_findings": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0,
            "is_safe": False,
            "scan_duration_ms": 0,
            "scanners_used": [],
            "scanners_failed": [],
            "scanner_summaries": [],
            "error": error_type,
        }


def create_phased_scanner(
    config: Any = None,
    enable_phase_3: bool = True,
    exclude_scanners: list[str] | None = None,
) -> PhasedSkillScanner:
    """创建分阶段扫描器实例的便捷函数"""
    return PhasedSkillScanner(
        config=config,
        enable_phase_3=enable_phase_3,
        exclude_scanners=exclude_scanners,
    )


def quick_phased_scan(
    skill_path: str | Path,
    enable_phase_3: bool = True,
    exclude_scanners: list[str] | None = None,
) -> dict:
    """快速分阶段扫描（使用默认设置，默认不启用阶段3）"""
    scanner = PhasedSkillScanner(
        enable_phase_3=enable_phase_3,
        exclude_scanners=exclude_scanners,
    )
    return scanner.scan_phased(skill_path)
