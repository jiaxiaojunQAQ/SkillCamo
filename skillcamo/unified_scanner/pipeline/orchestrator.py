# Copyright 2026
#
# Pipeline orchestrator for adversarial testing.

"""
Pipeline orchestrator for running adversarial testing with different generators.
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .result import PipelineResult, PipelineAttempt
from .config import AdversarialConfig
from .scanner_wrapper import UnifiedScannerWrapper
from .scan_utils import get_scanner_error_details, has_scanner_errors, is_detected, was_detected
from ..generators.base import BaseGenerator
from ..generators.exceptions import RetryableGenerationError

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..config import UnifiedScannerConfig


class PipelineOrchestrator:
    """
    通用 Pipeline 协调器

    支持通过配置文件加载不同的生成器和扫描器。
    """

    def __init__(
        self,
        generator: BaseGenerator,
        scanner: UnifiedScannerWrapper | None = None,
        max_iterations: int = 5,
        verbose: bool = True,
        show_progress: bool = True,
    ):
        """
        初始化协调器

        Args:
            generator: 生成器实例
            scanner: 扫描器实例
            max_iterations: 最大迭代次数
            verbose: 是否输出详细日志
            show_progress: 是否显示进度输出
        """
        self.generator = generator
        self.scanner = scanner
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.show_progress = show_progress

        # Inner-loop optimizers (unified code_induction) own their own candidate
        # scan loop within the per-skill budget K — inject the scan callback so
        # they can evaluate candidates. Outer-loop / non-transfer generators are
        # driven entirely by run()'s per-iteration loop and ignore this.
        if hasattr(generator, "uses_inner_loop") and generator.uses_inner_loop():
            generator.set_scan_callback(self._scan_skill)

    @classmethod
    def from_config(
        cls,
        config: AdversarialConfig,
        generator_name: str,
        base_skill_path: Path | None = None,
        script_path: Path | None = None,
        output_dir: Path | None = None,
        enabled_scanners: list[str] | None = None,
        max_iterations: int = 5,
        scanner_config: "UnifiedScannerConfig | None" = None,
        generator_config: dict | None = None,
    ) -> "PipelineOrchestrator":
        """
        从配置文件创建协调器

        Args:
            config: 配置对象
            generator_name: 生成器名称
            base_skill_path: 基础技能路径
            script_path: 脚本路径（某些生成器需要）
            enabled_scanners: 启用的扫描器列表，None 表示全部
            scanner_config: 已加载的 UnifiedScannerConfig（含 timeout 等配置）
            generator_config: profile 级 generator config 覆盖，deep-merge 到
                config.generator.yaml 的 canonical 块之上（override 优先）。
                用于让一个 generator 从多个 profile 跑出 baseline 矩阵。

        Returns:
            协调器实例
        """
        # 获取生成器配置
        gen_config = config.get_generator_config(generator_name)

        # profile 级覆盖：deep-merge 到 canonical 块之上（override 在后，优先）
        if generator_config:
            from ..config import deep_merge
            gen_config = deep_merge(gen_config, generator_config)

        # 添加路径参数
        if base_skill_path:
            gen_config["base_skill_path"] = str(base_skill_path)
        if script_path:
            gen_config["harmful_script_path"] = str(script_path)
        if output_dir:
            gen_config["output_dir"] = str(output_dir)

        # 注入 LLM 凭证（从 AdversarialConfig 的 generator.openai/anthropic 段读取）
        provider = gen_config.get("llm_provider", "openai")

        # 优先使用 key pool（支持多 key 轮换）
        key_pool = config.get_llm_api_key_pool(provider)
        if key_pool:
            gen_config["api_key_pool"] = key_pool
            gen_config["api_key"] = key_pool.get_next_key()  # GeneratorConfig 兼容
        else:
            api_key = config.get_llm_api_key(provider)
            if api_key:
                gen_config["api_key"] = api_key

        base_url = config.get_llm_base_url(provider)
        if base_url:
            gen_config["base_url"] = base_url

        # 加载生成器
        from ..generators import load_generator_from_config
        generator = load_generator_from_config(generator_name, gen_config)

        # 验证配置
        errors = generator.validate_config()
        if errors:
            raise ValueError(f"Invalid generator config: {errors}")

        # 加载扫描器
        scanner = None
        # 如果没有指定扫描器列表，使用所有可用的扫描器
        scanners_to_use = enabled_scanners if enabled_scanners is not None else config.available_scanners

        if scanners_to_use:
            scanner = UnifiedScannerWrapper(
                verbose=True,
                parallel=True,
                enabled_scanners=scanners_to_use,
                scanner_config=scanner_config,
            )

        return cls(
            generator=generator,
            scanner=scanner,
            max_iterations=max_iterations,
        )

    def run(self) -> PipelineResult:
        """
        执行完整的迭代流程

        Returns:
            Pipeline 结果
        """
        start_time = datetime.now()
        attempts = []

        skill_name = Path(str(self.generator.config.base_skill_path)).name
        if self.show_progress:
            print(f"==> Starting adversarial testing: {skill_name} (max {self.max_iterations} iterations)")

        logger.info(f"Starting adversarial pipeline with {self.generator.__class__.__name__}")
        logger.info(f"Max iterations: {self.max_iterations}")

        # 创建输出目录
        output_dir = self.generator.config.run_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        previous_feedback = None

        iteration = 0
        consecutive_gen_failures = 0
        max_consecutive_gen_failures = 10  # 防止无限重试

        while iteration < self.max_iterations:
            iteration += 1
            iter_start = datetime.now()

            if self.show_progress:
                print(f"\n  -> Iteration {iteration}/{self.max_iterations}")

            logger.info(f"\n=== Iteration {iteration}/{self.max_iterations} ===")

            # Step 1: 生成（失败不占迭代次数，直接重试）
            if self.show_progress:
                print("    Generating adversarial sample...")
            try:
                skill_path = self.generator.generate(iteration, previous_feedback)
                gen_end = datetime.now()
                logger.info(f"Generated skill: {skill_path}")
                consecutive_gen_failures = 0  # 成功后重置
            except RetryableGenerationError as e:
                # 瞬时故障（空 LLM 响应等）：不计入连续失败，仍不占迭代槽位
                logger.warning("Generation failed (retryable, not counting): %s", e)
                if self.show_progress:
                    print(f"    [!] Generation failed (will retry): {e}")
                iteration -= 1
                continue
            except Exception as e:
                consecutive_gen_failures += 1
                logger.warning("Generation failed (consecutive %d): %s", consecutive_gen_failures, e)
                if self.show_progress:
                    print(f"    [!] Generation failed: {e}")

                if consecutive_gen_failures >= max_consecutive_gen_failures:
                    logger.error("Generation failed %d times consecutively, giving up", consecutive_gen_failures)
                    break

                # 不占迭代次数，回退计数器并重试
                iteration -= 1
                continue

            # Step 2: 扫描
            if self.show_progress:
                print("    Scanning generated skill...")
            scan_result = self._scan_skill(skill_path)
            scan_end = datetime.now()

            # 扫描重试循环：仅重试出错的扫描器，不占迭代槽位
            max_scan_retries = 2
            errored_scanners = has_scanner_errors(scan_result)
            no_scanners = scan_result.get("no_scanners_ran", False)

            if not no_scanners and errored_scanners:
                for scan_retry in range(1, max_scan_retries + 1):
                    error_details = get_scanner_error_details(scan_result)
                    if self.show_progress:
                        for name, info in error_details.items():
                            print(f"    [?] {name}: {info['error_type']} — {info['error'][:200]}")
                        print(f"    [↻] Retrying {len(errored_scanners)} scanner(s) ({scan_retry}/{max_scan_retries})...")
                    logger.warning(
                        "Scan retry %d/%d for scanners: %s",
                        scan_retry,
                        max_scan_retries,
                        {n: d["error_type"] for n, d in error_details.items()},
                    )

                    time.sleep(2 ** scan_retry)  # 指数退避: 2s, 4s

                    # 仅重试出错的扫描器
                    retry_result = self._scan_skill(skill_path, scanner_names=errored_scanners)

                    # 合并：用重试结果替换原始出错条目
                    for name in errored_scanners:
                        if name in retry_result.get("scanners", {}):
                            scan_result["scanners"][name] = retry_result["scanners"][name]

                    # 更新 no_scanners_ran 标志
                    any_valid = any(
                        isinstance(d, dict) and d.get("max_severity") != "ERROR"
                        for d in scan_result["scanners"].values()
                    )
                    scan_result["no_scanners_ran"] = not any_valid

                    # 检查重试后是否还有错误
                    errored_scanners = has_scanner_errors(scan_result)
                    if not errored_scanners:
                        if self.show_progress:
                            print("    [✓] Retry succeeded — all scanners returned valid results")
                        break

                scan_end = datetime.now()  # 更新扫描结束时间

            detected = was_detected(scan_result)

            # 检测空扫描：所有 scanner 都失败时退出当前 profile
            no_scanners = scan_result.get("no_scanners_ran", False)
            if no_scanners:
                logger.error(
                    "No scanners produced valid results for %s — aborting profile",
                    skill_path,
                )
                if self.show_progress:
                    print("    [ERROR] All scanners failed — aborting this profile")

                # 保存错误结果到迭代目录
                iteration_timing = self._build_iteration_timing(iter_start, gen_end, scan_end)
                error_analysis = {
                    "detected": False,
                    "strategy": "scanner_error",
                    "reason": "All scanners failed — no valid scan results",
                    "next_action": "abort",
                }
                enriched_result = {
                    **scan_result,
                    "iteration_timing": iteration_timing,
                    "update_context": {
                        "triggered_scanners": [],
                        "clean_scanners": [],
                        "total_findings_count": 0,
                        "rewrite_strategy": "scanner_error",
                        "rewrite_reason": "All scanners failed — no valid scan results",
                    },
                    "generator_analysis": error_analysis,
                }
                iter_dir = self.generator.config.get_iteration_dir(iteration)
                if self.scanner is not None:
                    self.scanner.save_scan_result_external(
                        result=enriched_result,
                        iter_dir=iter_dir,
                        skill_path=skill_path,
                        analysis=error_analysis,
                    )
                else:
                    logger.warning("No scanner instance available, skipping error result save")
                break

            logger.info(f"Scan result: detected={detected}")
            if self.verbose:
                logger.info(self._summarize_scan_result(scan_result))

            if self.show_progress:
                if detected:
                    print("    [!] Threat detected")
                    print(f"    {self._summarize_scan_result(scan_result)}")
                else:
                    # 保守策略：如果有 scanner 出错，不宣告 bypass 成功
                    errored_scanners = has_scanner_errors(scan_result)
                    if errored_scanners:
                        error_details = get_scanner_error_details(scan_result)
                        scanner_summary = "; ".join(
                            f"{n}: {d['error_type']}" for n, d in error_details.items()
                        )
                        print(f"    [?] Inconclusive — scanners errored: {scanner_summary}")
                        for name, info in error_details.items():
                            print(f"        {name}: {info['error'][:200]}")
                        logger.warning(
                            "Bypass suppressed: scanners %s produced errors at iteration %d",
                            errored_scanners,
                            iteration,
                        )
                        # 视为检测到（保守策略），继续迭代
                        detected = True
                    else:
                        print("    [✓] Bypassed detection!")

            # Step 3: 成功则立即返回，跳过反馈分析
            if not detected:
                logger.info(f"SUCCESS! Bypassed detection at iteration {iteration}")
                analysis = {
                    "detected": False,
                    "strategy": "bypass_success",
                    "reason": "Bypassed detection - feedback analysis skipped",
                    "next_action": "success",
                }

                iteration_timing = self._build_iteration_timing(iter_start, gen_end, scan_end)
                scan_result_to_save, timed_out_scanners = self._filter_timeout_scanners(scan_result)
                update_context = self._build_update_context(scan_result, analysis, timed_out_scanners)

                enriched_result = {
                    **scan_result_to_save,
                    "timed_out_scanners": timed_out_scanners,
                    "iteration_timing": iteration_timing,
                    "update_context": update_context,
                }

                attempt = PipelineAttempt(
                    iteration=iteration,
                    timestamp=datetime.now(),
                    skill_path=skill_path,
                    detected=False,
                    scan_result=scan_result,
                    analysis=analysis,
                    notes=analysis.get("reason", ""),
                    iteration_timing=iteration_timing,
                    update_context=update_context,
                )
                attempts.append(attempt)

                iter_dir = self.generator.config.get_iteration_dir(iteration)
                self.scanner.save_scan_result_external(
                    result=enriched_result,
                    iter_dir=iter_dir,
                    skill_path=skill_path,
                    analysis=analysis,
                )

                if self.show_progress:
                    print("\n==> Adversarial testing complete - SUCCESS!\n")

                return PipelineResult(
                    success=True,
                    total_iterations=iteration,
                    attempts=attempts,
                    final_skill_path=skill_path,
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                    start_time=start_time,
                    end_time=datetime.now(),
                    evals_used=self._inner_evals_used(),
                )

            # Step 4: 分析反馈（仅被检测到时需要，用于下一轮调整策略）
            if self.max_iterations > 1:
                if self.show_progress:
                    print("    Analyzing feedback...")
                feedback = {
                    "scan_result": scan_result,
                    "detected": detected,
                }
                analysis = self.generator.analyze_feedback(feedback)
                analysis_end = datetime.now()
            else:
                feedback = None
                analysis = {
                    "detected": detected,
                    "strategy": "single_iteration",
                    "reason": "Single iteration - feedback analysis skipped",
                    "next_action": "stop",
                }
                analysis_end = datetime.now()

            # 构建迭代计时和更新上下文
            iteration_timing = self._build_iteration_timing(iter_start, gen_end, scan_end, analysis_end)
            scan_result_to_save, timed_out_scanners = self._filter_timeout_scanners(scan_result)
            update_context = self._build_update_context(scan_result, analysis, timed_out_scanners)

            enriched_result = {
                **scan_result_to_save,
                "timed_out_scanners": timed_out_scanners,
                "iteration_timing": iteration_timing,
                "update_context": update_context,
            }

            # Step 5: 记录到内存（用于最终统计）
            attempt = PipelineAttempt(
                iteration=iteration,
                timestamp=datetime.now(),
                skill_path=skill_path,
                detected=detected,
                scan_result=scan_result,
                analysis=analysis,
                notes=analysis.get("reason", ""),
                iteration_timing=iteration_timing,
                update_context=update_context,
            )
            attempts.append(attempt)

            # Step 5.5: 保存到统一日志存储（scan_result.json 包含扫描结果+分析反馈+更新上下文）
            iter_dir = self.generator.config.get_iteration_dir(iteration)
            self.scanner.save_scan_result_external(
                result=enriched_result,
                iter_dir=iter_dir,
                skill_path=skill_path,
                analysis=analysis,
            )

            # 生成器请求提前停止（连续多轮严重度不下降，继续重写不再有收益）
            if analysis.get("next_action") == "early_stop":
                logger.info(
                    "Generator signalled early_stop at iteration %d: %s",
                    iteration, analysis.get("reason", ""),
                )
                if self.show_progress:
                    print(
                        f"    [early-stop] {analysis.get('reason', 'severity plateau')}"
                    )
                break

            # 准备下一轮
            previous_feedback = feedback

        # 所有迭代完成
        logger.info("All iterations exhausted without success")

        if self.show_progress:
            print("\n==> Adversarial testing complete - All iterations exhausted\n")

        return PipelineResult(
            success=False,
            total_iterations=len(attempts),
            attempts=attempts,
            duration_seconds=(datetime.now() - start_time).total_seconds(),
            start_time=start_time,
            end_time=datetime.now(),
            evals_used=self._inner_evals_used(),
        )

    def _inner_evals_used(self) -> int | None:
        """Candidate scanner evals the inner-loop optimizer spent (None if the
        generator is not an inner-loop one)."""
        gen = self.generator
        if hasattr(gen, "uses_inner_loop") and gen.uses_inner_loop():
            return int(getattr(gen, "_inner_evals_used", 0) or 0)
        return None

    def _summarize_scan_result(self, scan_result: dict[str, Any]) -> str:
        """Return a compact human-readable scan summary."""
        if not isinstance(scan_result, dict):
            return "Scan summary: unavailable"

        scanners = scan_result.get("scanners", {})
        if not isinstance(scanners, dict) or not scanners:
            return "Scan summary: no scanner details"

        hit_scanners = []
        total_rules = 0
        for scanner_name, scanner_data in scanners.items():
            if not isinstance(scanner_data, dict):
                continue
            if scanner_data.get("detected"):
                blocked_rules = scanner_data.get("blocked_rules") or []
                total_rules += len(blocked_rules)
                severity = scanner_data.get("max_severity", "UNKNOWN")
                hit_scanners.append(f"{scanner_name}({severity})")

        if not hit_scanners:
            return "Scan summary: no blocking findings"

        scanners_text = ", ".join(hit_scanners[:6])
        if len(hit_scanners) > 6:
            scanners_text += f", +{len(hit_scanners) - 6} more"
        return f"Scan summary: {len(hit_scanners)} scanner(s) flagged, {total_rules} blocked rule(s): {scanners_text}"

    @staticmethod
    def _filter_timeout_scanners(scan_result: dict) -> tuple[dict, list[str]]:
        """过滤超时扫描器结果，返回过滤后结果和超时扫描器名称列表。

        保留原始 scan_result 不变，返回过滤后的副本供保存使用，
        同时返回超时扫描器名称列表以便记录到日志中。
        """
        scanners = scan_result.get("scanners", {})
        if not isinstance(scanners, dict):
            return scan_result, []

        timeout_names = []
        filtered_scanners = {}
        for name, data in scanners.items():
            if isinstance(data, dict):
                raw = data.get("raw_result", {})
                if isinstance(raw, dict) and raw.get("timed_out"):
                    timeout_names.append(name)
                    continue
            filtered_scanners[name] = data

        if timeout_names:
            logger.warning(
                "超时扫描器 (已从输出中排除): %s",
                ", ".join(timeout_names),
            )

        return {**scan_result, "scanners": filtered_scanners}, timeout_names

    @staticmethod
    def _build_update_context(
        scan_result: dict,
        analysis: dict | None,
        timed_out_scanners: list[str],
    ) -> dict[str, Any]:
        """构建更新上下文：明确记录 scanner 检测信息到 rewrite 策略的映射。

        将散落在各 scanner 子字段中的检测信息汇总为结构化上下文，
        使 scan_result.json 自包含，无需交叉引用即可追溯更新依据。
        """
        scanners = scan_result.get("scanners", {})

        triggered_scanners = []
        clean_scanners = []
        triggered_rules_by_scanner: dict[str, list[str]] = {}
        severity_summary: dict[str, str] = {}
        total_findings = 0

        for name, data in scanners.items():
            if not isinstance(data, dict):
                continue
            det = data.get("detected", False)
            sev = data.get("max_severity", "SAFE")
            rules = data.get("blocked_rules") or []
            findings = data.get("findings", [])
            findings_count = len(findings) if isinstance(findings, list) else 0
            total_findings += findings_count

            if is_detected(det, sev):
                triggered_scanners.append(name)
                if rules:
                    triggered_rules_by_scanner[name] = list(rules)
                severity_summary[name] = sev
            else:
                clean_scanners.append(name)

        context: dict[str, Any] = {
            "triggered_scanners": triggered_scanners,
            "clean_scanners": clean_scanners,
            "triggered_rules_by_scanner": triggered_rules_by_scanner,
            "severity_summary": severity_summary,
            "total_findings_count": total_findings,
            "timed_out_scanners": timed_out_scanners,
        }

        if analysis:
            context["rewrite_strategy"] = analysis.get("strategy", "unknown")
            context["rewrite_reason"] = analysis.get("reason", "")
            if analysis.get("compact_feedback"):
                context["compact_feedback_used"] = analysis["compact_feedback"]
            if analysis.get("reduced_scan_result"):
                context["reduced_scan_result_used"] = analysis["reduced_scan_result"]

        return context

    @staticmethod
    def _build_iteration_timing(
        iter_start: datetime,
        gen_end: datetime,
        scan_end: datetime,
        analysis_end: datetime | None = None,
    ) -> dict[str, Any]:
        """构建每迭代的计时信息。"""
        timing: dict[str, Any] = {
            "started_at": iter_start.isoformat(),
            "generation_completed_at": gen_end.isoformat(),
            "scan_completed_at": scan_end.isoformat(),
            "generation_duration_seconds": (gen_end - iter_start).total_seconds(),
            "scan_duration_seconds": (scan_end - gen_end).total_seconds(),
        }
        if analysis_end is not None:
            timing["analysis_completed_at"] = analysis_end.isoformat()
            timing["analysis_duration_seconds"] = (analysis_end - scan_end).total_seconds()
            timing["total_iteration_duration_seconds"] = (analysis_end - iter_start).total_seconds()
        else:
            timing["total_iteration_duration_seconds"] = (scan_end - iter_start).total_seconds()
        return timing

    def _scan_skill(self, skill_path: Path, scanner_names: list[str] | None = None) -> dict:
        """
        扫描技能

        Args:
            skill_path: 技能路径
            scanner_names: 仅运行指定的扫描器子集（用于重试出错扫描器）。
                           为 None 时运行所有启用的扫描器。

        Returns:
            扫描结果字典（包含完整扫描器输出）
        """
        if self.scanner is None:
            return {"scanners": {}, "summary": {"all_clean": False, "mock": True}, "no_scanners_ran": True}

        if scanner_names is not None:
            result = self.scanner.scan_selective(skill_path, scanner_names)
        else:
            result = self.scanner.scan(skill_path)

        # 转换为字典，保留完整的扫描器结果
        if hasattr(result, "__dict__"):
            # 保留每个扫描器的完整结果，包括 raw_result
            scanners_data = {}
            has_valid_scan = False
            for name, fb in result.scanners.items():
                scanner_data = {
                    "detected": fb.detected if hasattr(fb, "detected") else False,
                    "max_severity": fb.max_severity if hasattr(fb, "max_severity") else "UNKNOWN",
                    "blocked_rules": list(fb.blocked_rules) if hasattr(fb, "blocked_rules") else [],
                }
                # 保留完整的 raw_result（包含 metadata, error, findings 等）
                if hasattr(fb, "raw_result") and fb.raw_result is not None:
                    scanner_data["raw_result"] = fb.raw_result
                    # 检查是否有错误（raw_result 中的 error 字段）
                    if isinstance(fb.raw_result, dict) and not fb.raw_result.get("error"):
                        has_valid_scan = True
                # 保留 findings（如果有的话）
                if hasattr(fb, "findings"):
                    scanner_data["findings"] = fb.findings

                scanners_data[name] = scanner_data

            parsed_result = {
                "scanners": scanners_data,
                "summary": result.summary if hasattr(result, "summary") else {},
                "no_scanners_ran": not has_valid_scan,
            }
            if getattr(result, "llm_judgement", None) is not None:
                parsed_result["llm_judgement"] = result.llm_judgement
            return parsed_result

        return {"scanners": {}, "summary": {"error": "Invalid result format"}, "raw": str(result), "no_scanners_ran": True}


# 便捷函数
def run_pipeline(
    base_skill_path: Path,
    script_path: Path,
    config_path: Path | None = None,
    generator_name: str = "SkillCamo",
    max_iterations: int = 5,
) -> PipelineResult:
    """
    运行 pipeline 的便捷函数

    Args:
        base_skill_path: 基础技能路径
        script_path: 恶意脚本路径
        config_path: 配置文件路径
        generator_name: 生成器名称
        max_iterations: 最大迭代次数

    Returns:
        Pipeline 结果
    """
    config = AdversarialConfig.load(config_path)

    # 为 Claude CLI 扫描器设置 API key 轮换池
    try:
        from ..adapters.skill_scanner_base import SkillBasedScannerAdapter
        anthropic_pool = config.get_llm_api_key_pool("anthropic")
        if anthropic_pool and anthropic_pool.key_count > 0:
            SkillBasedScannerAdapter.set_api_key_pool(anthropic_pool)
    except Exception:
        pass

    orchestrator = PipelineOrchestrator.from_config(
        config,
        generator_name=generator_name,
        base_skill_path=base_skill_path,
        script_path=script_path,
        max_iterations=max_iterations,
    )
    return orchestrator.run()
