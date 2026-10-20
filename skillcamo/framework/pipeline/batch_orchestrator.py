# Copyright 2026
#
# Batch orchestrator for adversarial framework.

"""
Batch orchestrator for running multiple adversarial tests.
"""

import json
import logging
import re
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from rich.console import Console
from rich.table import Table

from .config import AdversarialConfig
from .batch_config import BatchConfig, SkillSpec, resolve_project_root
from .batch_result import BatchResult, BatchSkillResult, evaluate_final_iteration
from .orchestrator import PipelineOrchestrator


def _resolve_project_root() -> Path:
    """解析项目根目录（委托 batch_config.resolve_project_root，保持两层基准一致）。"""
    return resolve_project_root()

logger = logging.getLogger(__name__)
console = Console()

if TYPE_CHECKING:
    from ..config import UnifiedScannerConfig


def _short_error_message(error: Exception | str, max_len: int = 300) -> str:
    text = str(error).replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len] + "...[truncated]"


class BatchOrchestrator:
    """批量执行协调器。

    并行执行多个技能的对抗测试，支持进度跟踪和错误处理。
    """

    def __init__(
        self,
        batch_config: BatchConfig,
        adv_config: AdversarialConfig,
        max_workers: int | None = None,
        base_dir: Path | None = None,
        scanner_config: "UnifiedScannerConfig | None" = None,
    ):
        """初始化批量协调器。

        Args:
            batch_config: 批量配置
            adv_config: Adversarial 配置
            max_workers: 最大工作线程数，None 表示使用配置中的值
            base_dir: 基础目录，用于解析相对路径
            scanner_config: 已加载的 UnifiedScannerConfig（含 timeout 等配置）
        """
        self.batch_config = batch_config
        self.adv_config = adv_config
        self.scanner_config = scanner_config
        self.max_workers = max_workers or batch_config.get_max_workers()
        self.base_dir = base_dir or _resolve_project_root()

        if not batch_config.batch.get("output_dir"):
            raise ValueError("defaults.adversarial.output_dir is required")
        if not batch_config.batch.get("generator"):
            raise ValueError("profile.action / generator is required")
        if batch_config.batch.get("max_iterations") is None:
            raise ValueError("defaults.adversarial.max_iterations is required")

        # 按任务类型划分输出目录：{output_dir}/{generator_name}
        output_dir = batch_config.batch["output_dir"]
        if not Path(output_dir).is_absolute():
            output_dir = self.base_dir / output_dir
        generator_name = batch_config.batch.get("generator", "unknown")
        batch_output_dir = Path(output_dir) / generator_name

        self.result = BatchResult(
            batch_id="batch",
            total_skills=len(batch_config.get_resolved_skills()),
            output_dir=batch_output_dir,
        )

        # 保存全局配置快照
        self.result.global_settings = {
            "generator": batch_config.batch["generator"],
            "max_iterations": batch_config.batch["max_iterations"],
            "max_workers": self.max_workers,
        }

        # 线程锁
        self._lock = threading.Lock()
        self.state_path = self.result.output_dir / "state.json"
        self._state: dict[str, Any] = {"skills": {}}

        # 注入 Anthropic key pool 给 Claude CLI 扫描器
        self._setup_scanner_key_pool()

    def _setup_scanner_key_pool(self) -> None:
        """为 Claude CLI 扫描器设置 API key 轮换池。"""
        try:
            from ..adapters.skill_scanner_base import SkillBasedScannerAdapter
            anthropic_pool = self.adv_config.get_llm_api_key_pool("anthropic")
            if anthropic_pool and anthropic_pool.key_count > 0:
                SkillBasedScannerAdapter.set_api_key_pool(anthropic_pool)
        except Exception as e:
            logger.debug(f"Skipping Anthropic key pool setup: {e}")

    def run(self, verbose: bool = False) -> BatchResult:
        """执行批量测试。

        Args:
            verbose: 是否输出详细日志

        Returns:
            批量结果
        """
        # 验证配置
        errors = self.batch_config.validate(allowed_generators=set(self.adv_config.generators))
        if errors:
            logger.error("Configuration errors:")
            for error in errors:
                logger.error(f"  - {error}")
            raise ValueError(f"Invalid configuration: {errors}")

        # 创建输出目录
        self.result.output_dir.mkdir(parents=True, exist_ok=True)
        self._state = self._load_state()

        # 获取要执行的技能列表（先做二次校验，让 _display_batch_plan 用真实的 pending 数）
        skills = self.batch_config.get_resolved_skills()
        pending_skills = self._prepare_execution_plan(skills)

        if verbose:
            self._display_batch_plan(skills, pending_skills)

        if pending_skills:
            self._run_parallel(pending_skills, verbose)

        # 完成批量运行
        self.result.finalize()

        # 生成报告
        self._generate_reports()

        return self.result

    def _run_parallel(
        self,
        skills: list[SkillSpec],
        verbose: bool,
    ) -> None:
        """并行执行技能测试。"""
        total_skills = len(skills)
        all_count = len(self.batch_config.get_resolved_skills())
        if all_count > total_skills:
            skipped = all_count - total_skills
            click.echo(f"跳过 {skipped} 个已完成 skill（从 state.json 恢复）")
        click.echo(f"开始扫描 {total_skills} 个 skill...")

        def execute_with_progress(
            index: int, spec: SkillSpec,
        ) -> tuple[SkillSpec, BatchSkillResult]:
            with self._lock:
                click.echo(f"  [{index}/{total_skills}] {spec.name}")
            result = self._execute_skill(spec, verbose=verbose)
            with self._lock:
                if result.success:
                    click.echo(f"  [{index}/{total_skills}] ✓ {spec.name}")
                else:
                    click.echo(
                        f"  [{index}/{total_skills}] ✗ {spec.name}: "
                        f"{_short_error_message(result.error or 'Unknown error')}"
                    )
            return spec, result

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(execute_with_progress, i + 1, spec): spec
                for i, spec in enumerate(skills)
            }

            try:
                for future in as_completed(futures):
                    spec, skill_result = future.result()

                    with self._lock:
                        self.result.add_result(skill_result)

            except KeyboardInterrupt:
                click.echo("\nBatch execution interrupted")
                executor.shutdown(wait=False, cancel_futures=True)
                raise

    def _run_single_skill(self, spec: SkillSpec, verbose: bool = False) -> BatchSkillResult:
        """运行单个技能测试。

        Args:
            spec: 技能规格
            verbose: 是否输出详细日志

        Returns:
            技能测试结果

        Note:
            每个 skill 的输出目录由 generator 的 run_output_dir 决定
            （包含 _resolve_script() 解析后的真实脚本名）。
        """
        start_time = datetime.now()

        try:
            # 获取该技能的配置
            skill_config = self.batch_config.get_skill_config(spec, self.base_dir)
            generator_name = skill_config["generator"]

            # 验证路径
            if not spec.path.exists():
                return BatchSkillResult(
                    spec=spec,
                    success=False,
                    generator=generator_name,
                    error=f"Skill path does not exist: {spec.path}",
                    start_time=start_time,
                    end_time=datetime.now(),
                )

            if not (spec.path / "SKILL.md").exists():
                return BatchSkillResult(
                    spec=spec,
                    success=False,
                    generator=generator_name,
                    error=f"SKILL.md not found in: {spec.path}",
                    start_time=start_time,
                    end_time=datetime.now(),
                )

            # 验证脚本
            script_path = skill_config.get("script")
            if generator_name != "direct_scan" and script_path and not script_path.exists():
                return BatchSkillResult(
                    spec=spec,
                    success=False,
                    generator=generator_name,
                    error=f"Script does not exist: {script_path}",
                    start_time=start_time,
                    end_time=datetime.now(),
                )

            # 创建协调器并运行（orchestrator 会自动创建输出目录）
            orchestrator = PipelineOrchestrator.from_config(
                self.adv_config,
                generator_name=skill_config["generator"],
                base_skill_path=spec.path,
                script_path=script_path,
                output_dir=self.result.output_dir,
                enabled_scanners=skill_config.get("enabled_scanners"),
                max_iterations=skill_config["max_iterations"],
                scanner_config=self.scanner_config,
                generator_config=skill_config.get("generator_config"),
            )
            orchestrator.show_progress = verbose

            # 抑制详细输出（在批量模式下）
            orchestrator.verbose = False

            # 运行（日志已在 orchestrator 中统一保存）
            pipeline_result = orchestrator.run()

            # 使用 generator 实际的输出目录（包含 _resolve_script() 解析后的真实脚本名）
            actual_output_dir = orchestrator.generator.config.run_output_dir

            # 不再单独保存摘要，因为 scan_result.json 已包含完整信息
            # 只返回结果用于 batch 报告汇总
            return BatchSkillResult(
                spec=spec,
                success=True,
                generator=generator_name,
                result=pipeline_result,
                output_dir=actual_output_dir,
                scan_detected=not pipeline_result.success,
                start_time=start_time,
                end_time=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Error running skill {spec.name}: {_short_error_message(e)}")
            return BatchSkillResult(
                spec=spec,
                success=False,
                generator=self.batch_config.get_skill_config(spec, self.base_dir).get("generator", "unknown"),
                error=_short_error_message(e, max_len=800),
                output_dir=self._get_skill_output_dir(spec),
                start_time=start_time,
                end_time=datetime.now(),
            )

    def _prepare_execution_plan(self, skills: list[SkillSpec]) -> list[SkillSpec]:
        pending: list[SkillSpec] = []

        for spec in skills:
            state_entry = self._get_skill_state(spec)
            if state_entry.get("status") == "success":
                skill_exists = spec.path is not None and spec.path.exists()
                output_dir = Path(state_entry["output_dir"]) if state_entry.get("output_dir") else self._get_skill_output_dir(spec)
                has_scan_result = bool(list(output_dir.glob("iter_*/scan_result.json"))) if output_dir.exists() else False

                if skill_exists and has_scan_result:
                    last_scan_result = self._load_last_scan_result(output_dir)
                    if last_scan_result is None:
                        logger.warning(
                            "Skill %s last iteration could not be loaded, rerunning",
                            spec.name,
                        )
                        pending.append(spec)
                        continue

                    evaluation = evaluate_final_iteration(last_scan_result)

                    if evaluation["has_errors"]:
                        logger.info(
                            "Skill %s last scan has errors (final_outcome=%s), re-queuing for retry",
                            spec.name,
                            evaluation["final_outcome"],
                        )
                        self._clear_skill_state(spec)
                        pending.append(spec)
                        continue

                    restored = BatchSkillResult(
                        spec=spec,
                        success=True,
                        generator=state_entry.get("generator", self.batch_config.get_skill_config(spec, self.base_dir).get("generator", "unknown")),
                        output_dir=output_dir,
                        scan_detected=evaluation["detected"],
                        start_time=datetime.fromisoformat(state_entry["start_time"]) if state_entry.get("start_time") else datetime.now(),
                        end_time=datetime.fromisoformat(state_entry["end_time"]) if state_entry.get("end_time") else datetime.now(),
                        _cached_final_outcome=evaluation["final_outcome"],
                        _cached_scanner_summary=evaluation["scanner_summary"],
                        _cached_total_iterations=state_entry.get("total_iterations"),
                    )
                    self.result.add_result(restored)
                    continue
                else:
                    logger.warning(
                        f"Skill {spec.name} 标记为 success 但验证失败 "
                        f"(skill_exists={skill_exists}, has_scan_result={has_scan_result})，重新执行"
                    )
                    pending.append(spec)
                    continue
            pending.append(spec)

        return pending

    def _clear_skill_state(self, spec: SkillSpec) -> None:
        """清除指定 skill 的 state 条目，确保重新执行时不会残留旧数据。"""
        key = self._get_skill_key(spec)
        self._state.setdefault("skills", {}).pop(key, None)

    @staticmethod
    def _load_last_scan_result(output_dir: Path) -> dict[str, Any] | None:
        """Load the last iteration scan_result.json for a skill output directory."""
        iter_dirs = sorted(output_dir.glob("iter_*"))
        if not iter_dirs:
            return None
        last_scan = iter_dirs[-1] / "scan_result.json"
        if not last_scan.exists():
            return None

        try:
            with open(last_scan, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read {last_scan}: {e}")
            return None

    def _execute_skill(self, spec: SkillSpec, verbose: bool = False) -> BatchSkillResult:
        self._update_skill_state(
            spec,
            status="running",
            error=None,
            start_time=datetime.now(),
        )
        result = self._run_single_skill(spec, verbose=verbose)
        self._update_skill_state(
            spec,
            status="success" if result.success else "error",
            error=result.error,
            output_dir=result.output_dir,
            detected=result.scan_detected,
            end_time=result.end_time or datetime.now(),
            final_outcome=result.final_outcome,
            scanner_summary=result.scanner_summary,
            total_iterations=result.total_iterations,
        )
        return result

    def _get_skill_key(self, spec: SkillSpec) -> str:
        if spec.path is None:
            raise ValueError("Skill spec path is required")
        return str(spec.path.resolve())

    def _get_skill_state(self, spec: SkillSpec) -> dict[str, Any]:
        return self._state.setdefault("skills", {}).get(self._get_skill_key(spec), {})

    def _load_state(self, *, create_if_missing: bool = True) -> dict[str, Any]:
        if not self.state_path.exists():
            state = self._new_state()
            if create_if_missing:
                self._write_state(state)
            return state

        try:
            with open(self.state_path, encoding="utf-8") as f:
                state = json.load(f)
        except json.JSONDecodeError:
            logger.warning("state.json 解析失败，尝试修复 trailing comma")
            with open(self.state_path, encoding="utf-8") as f:
                content = f.read()
            for _ in range(10):
                fixed = re.sub(r",(\s*[}\]])", r"\1", content)
                if fixed == content:
                    break
                content = fixed
            try:
                state = json.loads(content)
            except json.JSONDecodeError:
                logger.error("state.json 修复失败，创建新 state")
                state = self._new_state()

        state.setdefault("skills", {})
        return state

    def _new_state(self) -> dict[str, Any]:
        return {
            "batch_id": self.result.batch_id,
            "output_dir": str(self.result.output_dir),
            "updated_at": datetime.now().isoformat(),
            "skills": {},
        }

    def _write_state(self, state: dict[str, Any]) -> None:
        state["updated_at"] = datetime.now().isoformat()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=self.state_path.parent, suffix=".tmp",
        )
        try:
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            Path(tmp_path).replace(self.state_path)
        except BaseException:
            Path(tmp_path).unlink(missing_ok=True)
            raise

    def _update_skill_state(
        self,
        spec: SkillSpec,
        *,
        status: str,
        error: str | None = None,
        output_dir: Path | None = None,
        detected: bool | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        final_outcome: str | None = None,
        scanner_summary: dict | None = None,
        total_iterations: int | None = None,
    ) -> None:
        with self._lock:
            skill_config = self.batch_config.get_skill_config(spec, self.base_dir)
            key = self._get_skill_key(spec)
            entry = self._state.setdefault("skills", {}).get(key, {})
            entry.update(
                {
                    "name": spec.name,
                    "path": str(spec.path.resolve()) if spec.path else None,
                    "script": str(skill_config["script"]) if skill_config.get("script") else None,
                    "generator": skill_config.get("generator"),
                    "max_iterations": skill_config.get("max_iterations"),
                    "status": status,
                    "error": error,
                    "detected": detected,
                    "output_dir": str(output_dir or self._get_skill_output_dir(spec, skill_config)),
                }
            )
            if start_time is not None:
                entry["start_time"] = start_time.isoformat()
            if end_time is not None:
                entry["end_time"] = end_time.isoformat()
            if final_outcome is not None:
                entry["final_outcome"] = final_outcome
            if scanner_summary is not None:
                entry["scanner_summary"] = scanner_summary
            if total_iterations is not None:
                entry["total_iterations"] = total_iterations
            self._state["skills"][key] = entry
            self._write_state(self._state)

    def _get_skill_output_dir(
        self,
        spec: SkillSpec,
        skill_config: dict[str, Any] | None = None,
    ) -> Path:
        """Fallback 输出目录推算（仅在 generator 未创建时使用）。

        正常路径应使用 orchestrator.generator.config.run_output_dir。
        此方法仅在异常路径（generator 创建失败）作为 fallback。
        """
        if skill_config is None:
            skill_config = self.batch_config.get_skill_config(spec, self.base_dir)

        skill_name = spec.path.name if spec.path else (spec.name or "unknown_skill")
        return self.result.output_dir / skill_name

    def _generate_reports(self) -> None:
        """生成批量报告。"""
        reports = self.batch_config.reports

        if reports.format in ("json", "both"):
            json_path = self.result.output_dir / "summary.json"
            self.result.save_json_report(json_path)

        if reports.format in ("markdown", "both"):
            md_path = self.result.output_dir / "summary.md"
            self.result.save_markdown_report(md_path)

        # 生成总结报告（Markdown + Rich Console）
        try:
            from ..summary_report import SummaryReportGenerator
            summary_gen = SummaryReportGenerator(title="Adversarial Batch Summary")
            summary_gen.render(
                self.result,
                output_path=self.result.output_dir / "summary_report.md",
                show_console=True,
            )
        except Exception as e:
            logger.warning(f"Summary report generation failed: {e}")

    def _display_batch_plan(
        self,
        all_skills: list[SkillSpec],
        pending_skills: list[SkillSpec],
    ) -> None:
        """显示批量执行计划。

        completed/pending 计数与 `_run_parallel` 中"跳过 N 个已完成 skill" 日志保持口径一致：
        completed = 通过 `_prepare_execution_plan` 二次校验、可直接恢复的 skill 数；
        pending  = 真正会被 `_run_parallel` 执行的 skill 数。
        """
        console.print("\n[bold cyan]Batch Execution Plan[/bold cyan]\n")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Setting", style="cyan")
        table.add_column("Value")

        completed = len(all_skills) - len(pending_skills)
        pending = len(pending_skills)
        if completed > 0:
            table.add_row("Total Skills", f"{len(all_skills)} ({completed} completed, {pending} pending)")
        else:
            table.add_row("Total Skills", str(len(all_skills)))
        table.add_row("Max Workers", str(self.max_workers))
        table.add_row("Output Directory", str(self.result.output_dir))
        table.add_row("Generator", str(self.batch_config.batch.get("generator")))
        table.add_row("Max Iterations", str(self.batch_config.batch.get("max_iterations")))

        # 显示启用的扫描器
        enabled_scanners = self.batch_config.batch.get("enabled_scanners")
        if enabled_scanners:
            table.add_row("Enabled Scanners", ", ".join(enabled_scanners) + " [dim](profile override)[/dim]")
        elif self.adv_config.available_scanners:
            table.add_row("Enabled Scanners", ", ".join(self.adv_config.available_scanners) + f" [dim]({len(self.adv_config.available_scanners)} from config)[/dim]")
        else:
            table.add_row("Enabled Scanners", "[dim]All (8 scanners)[/dim]")

        console.print(table)
        console.print()

    def dry_run(self) -> None:
        """显示执行计划但不实际运行。

        以只读方式加载 state.json（state.json 不存在时不写空文件），
        然后跑一次 `_prepare_execution_plan` 让表格数字与正常 run 一致。
        `_prepare_execution_plan` 的副作用仅作用于内存 state 和 self.result，
        dry_run 不进入 `_run_parallel` 也不触发 `_write_state`，磁盘不变。
        """
        self._state = self._load_state(create_if_missing=False)
        skills = self.batch_config.get_resolved_skills()
        pending_skills = self._prepare_execution_plan(skills)
        self._display_batch_plan(skills, pending_skills)

        console.print("[yellow]Dry run mode - no actual execution[/yellow]")
