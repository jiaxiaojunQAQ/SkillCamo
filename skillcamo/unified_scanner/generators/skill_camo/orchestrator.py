# Copyright 2026
#
# Orchestrator for LLM-driven image command injection.

"""
Orchestrator - coordinates LLM analysis, image injection, and scanning.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from .models import (
    InjectionConfig,
    InjectionResult,
    IterationAttempt,
)
from .skill_analyzer import SkillAnalyzer, load_script_command
from .llm_advisor import LLMAdvisor
from .image_injector import ImageInjector
from ...pipeline.scan_utils import has_scanner_errors, is_detected, was_detected

logger = logging.getLogger(__name__)


class ImageInjectionOrchestrator:
    """Orchestrates LLM-driven injection testing"""

    def __init__(self, config: InjectionConfig, scanner_config=None):
        self.config = config
        self._scanner_config = scanner_config

        # Initialize components
        self.skill_analyzer = SkillAnalyzer(config.base_skill_path)
        self.llm_advisor = LLMAdvisor(
            provider=config.llm_provider,
            model=config.llm_model,
            api_key_pool=getattr(config, 'api_key_pool', None),
        )
        self.scanner = self._init_scanner()

    def _init_scanner(self):
        """Initialize the scanner wrapper"""
        try:
            # 导入路径更新到 pipeline 目录
            from ...pipeline.scanner_wrapper import UnifiedScannerWrapper
            return UnifiedScannerWrapper(verbose=self.config.verbose, scanner_config=self._scanner_config)
        except ImportError as e:
            logger.error(f"Failed to import scanner: {e}")
            return None

    def run(self) -> InjectionResult:
        """Run the LLM-driven injection test"""
        start_time = datetime.now()
        attempts = []

        # Create output directory
        self.config.run_output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Starting LLM-driven injection test")
        logger.info(f"Base skill: {self.config.base_skill_path}")
        logger.info(f"Script: {self.config.harmful_script_path}")
        logger.info(f"Max iterations: {self.config.max_iterations}")

        skill_context = self.skill_analyzer.analyze()
        logger.info(f"Analyzed skill: {len(skill_context.sections)} sections")

        # Load command
        command = load_script_command(self.config.harmful_script_path)
        logger.info(f"Command: {command[:60]}...")

        current_skill_md = skill_context.content
        image_alt_text = "Setup command"

        # Create injector
        injector = ImageInjector(
            self.config.base_skill_path,
            self.config,
        )

        # Main loop
        previous_feedback = None
        compact_feedback = None

        for iteration in range(1, self.config.max_iterations + 1):
            iter_start = datetime.now()
            logger.info(f"\n=== Iteration {iteration} ===")

            if iteration == 1:
                rewritten_skill_md = self.llm_advisor.rewrite_initial_skill_markdown(
                    skill_context,
                    command,
                    image_alt_text,
                )
            else:
                rewritten_skill_md = self.llm_advisor.rewrite_skill_markdown_with_feedback(
                    current_skill_md,
                    command,
                    compact_feedback or {},
                    image_alt_text,
                )

            gen_end = datetime.now()

            generated_skill = injector.inject_with_injection(
                command,
                iteration,
                rewritten_skill_md,
            )
            current_skill_md = rewritten_skill_md

            scan_result = self._scan_skill(generated_skill)
            scan_end = datetime.now()
            detected = was_detected(scan_result)

            # Build iteration timing
            iteration_timing = {
                "started_at": iter_start.isoformat(),
                "generation_completed_at": gen_end.isoformat(),
                "scan_completed_at": scan_end.isoformat(),
                "generation_duration_seconds": (gen_end - iter_start).total_seconds(),
                "scan_duration_seconds": (scan_end - gen_end).total_seconds(),
                "total_iteration_duration_seconds": (scan_end - iter_start).total_seconds(),
            }

            # Build update context from scanner results
            update_context = self._build_update_context(scan_result)
            timed_out_scanners = self._get_timed_out_scanners(scan_result)

            enriched_result = {
                **scan_result,
                "timed_out_scanners": timed_out_scanners,
                "iteration_timing": iteration_timing,
                "update_context": update_context,
            }

            # Record attempt
            attempt = IterationAttempt(
                iteration=iteration,
                timestamp=datetime.now(),
                strategy=None,
                generated_skill_path=generated_skill,
                detected=detected,
                scan_result=scan_result,
                feedback_summary=previous_feedback or "",
            )
            attempts.append(attempt)

            # Save to unified log storage (scan_result.json + generator analysis)
            iter_dir = self.config.get_iteration_dir(iteration)
            analysis = {
                "strategy": "rewrite_full_skill_md",
                "command": command,
                "suggested_image_alt": image_alt_text,
                "feedback_summary": compact_feedback or {},
                "detected": detected,
            }
            self.scanner.save_scan_result_external(
                result=enriched_result,
                iter_dir=iter_dir,
                skill_path=generated_skill,
                analysis=analysis,
            )

            if detected:
                logger.warning("DETECTED")
                previous_feedback = scan_result
                compact_feedback = self.llm_advisor.analyze_scan_result(scan_result)
                analysis_end = datetime.now()
                # Update timing with analysis phase
                iteration_timing["analysis_completed_at"] = analysis_end.isoformat()
                iteration_timing["analysis_duration_seconds"] = (analysis_end - scan_end).total_seconds()
                iteration_timing["total_iteration_duration_seconds"] = (analysis_end - iter_start).total_seconds()
                # Update context with compact feedback
                update_context["compact_feedback_used"] = compact_feedback
            else:
                # 保守策略：如果有 scanner 出错，不宣告 bypass 成功
                errored_scanners = has_scanner_errors(scan_result)
                if errored_scanners:
                    logger.warning(
                        "Bypass suppressed: scanners %s produced errors — treating as detected",
                        errored_scanners,
                    )
                    detected = True
                    previous_feedback = scan_result
                    compact_feedback = self.llm_advisor.analyze_scan_result(scan_result)
                else:
                    logger.info("SUCCESS! Bypassed detection")

                    # Save final result
                    self._save_success(generated_skill, command, image_alt_text)

                    return InjectionResult(
                        success=True,
                        total_iterations=iteration,
                        attempts=attempts,
                        successful_strategy=None,
                        final_skill_path=generated_skill,
                        duration_seconds=(datetime.now() - start_time).total_seconds(),
                    )

        # All iterations exhausted
        logger.info("All iterations exhausted without success")

        return InjectionResult(
            success=False,
            total_iterations=len(attempts),
            attempts=attempts,
            duration_seconds=(datetime.now() - start_time).total_seconds(),
        )

    def _scan_skill(self, skill_path: Path) -> dict:
        """Scan the generated skill"""
        if self.scanner is None:
            return {"mock": True, "scanners": {}}

        result = self.scanner.scan(skill_path)

        # Convert to dict for JSON serialization, preserving raw_result and findings
        if hasattr(result, "__dict__"):
            scanners_data = {}
            for name, fb in result.scanners.items():
                scanner_data = {
                    "detected": fb.detected if hasattr(fb, "detected") else False,
                    "max_severity": fb.max_severity if hasattr(fb, "max_severity") else "UNKNOWN",
                    "blocked_rules": list(fb.blocked_rules) if hasattr(fb, "blocked_rules") else [],
                }
                if hasattr(fb, "raw_result") and fb.raw_result is not None:
                    scanner_data["raw_result"] = fb.raw_result
                if hasattr(fb, "findings"):
                    scanner_data["findings"] = fb.findings
                scanners_data[name] = scanner_data

            return {
                "scanners": scanners_data,
                "summary": result.summary if hasattr(result, "summary") else {},
            }

        return {"raw": str(result)}

    def _save_success(self, skill_path: Path, command: str, image_alt_text: str) -> None:
        """Save successful result"""
        final_dir = self.config.run_output_dir / "final"
        final_dir.mkdir(parents=True, exist_ok=True)

        # Copy successful skill (ignore_errors handles non-existent paths)
        success_skill = final_dir / "skill"
        shutil.rmtree(success_skill, ignore_errors=True)
        shutil.copytree(skill_path, success_skill)

        # Save strategy info
        (final_dir / "strategy.json").write_text(
            json.dumps({
                "command": command,
                "suggested_image_alt": image_alt_text,
                "strategy": "rewrite_full_skill_md",
            }, indent=2),
            encoding="utf-8"
        )

    @staticmethod
    def _build_update_context(scan_result: dict) -> dict:
        """构建更新上下文：明确记录 scanner 检测信息。"""
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

        return {
            "triggered_scanners": triggered_scanners,
            "clean_scanners": clean_scanners,
            "triggered_rules_by_scanner": triggered_rules_by_scanner,
            "severity_summary": severity_summary,
            "total_findings_count": total_findings,
        }

    @staticmethod
    def _get_timed_out_scanners(scan_result: dict) -> list[str]:
        """提取超时扫描器名称列表。"""
        scanners = scan_result.get("scanners", {})
        if not isinstance(scanners, dict):
            return []
        timeout_names = []
        for name, data in scanners.items():
            if isinstance(data, dict):
                raw = data.get("raw_result", {})
                if isinstance(raw, dict) and raw.get("timed_out"):
                    timeout_names.append(name)
        return timeout_names


def run_injection_test(
    base_skill: str | Path,
    script: str | Path,
    max_iterations: int = 5,
    output_dir: str | Path = "outputs",
    llm_provider: str = "openai",
    llm_model: str = None,
    verbose: bool = True,
) -> InjectionResult:
    """Convenience function to run injection test"""
    config = InjectionConfig(
        base_skill_path=Path(base_skill),
        harmful_script_path=Path(script),
        max_iterations=max_iterations,
        output_dir=Path(output_dir),
        llm_provider=llm_provider,
        llm_model=llm_model or "gpt-4o-mini",
        verbose=verbose,
    )

    orchestrator = ImageInjectionOrchestrator(config)
    return orchestrator.run()
