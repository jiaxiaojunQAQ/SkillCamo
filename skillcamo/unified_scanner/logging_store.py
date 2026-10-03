"""结果保存与实验日志存储。"""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CLAUDE_BASED_SCANNERS = frozenset({
    "scan_skill_vetter",
    "scan_skill_auditor",
    "scan_skill_slowmist",
})


def save_json_atomic(result: dict[str, Any], output_path: str | Path) -> None:
    """原子性保存 JSON 文件。"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = output_path.with_suffix(f".tmp.{uuid.uuid4().hex[:8]}")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        temp_path.replace(output_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


def _save_text_atomic(text: str, output_path: Path) -> None:
    """原子性保存文本文件。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = output_path.with_suffix(f".tmp.{uuid.uuid4().hex[:8]}")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(text)
        temp_path.replace(output_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


class ExperimentLogStore:
    """实验日志会话和扫描结果保存。"""

    def __init__(self, *, enabled: bool, output_dir: str | Path):
        self.enabled = enabled
        self.output_dir = Path(output_dir)
        self.session_id: str | None = None
        self.iteration: int = 0
        self.run_dir: Path | None = None
        self.start_time: datetime | None = None

    def ensure_session(self) -> None:
        """确保实验会话已初始化。"""
        if not self.enabled or self.session_id is not None:
            return

        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.iteration = 0
        self.start_time = datetime.now()
        self.run_dir = self.output_dir / "runs" / self.session_id / "iterations"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Experiment session initialized: %s", self.run_dir)

    def create_iteration_dir(self, skill_path: Path) -> Path:
        """创建迭代目录并复制 skill。"""
        if self.run_dir is None:
            raise RuntimeError("Experiment session has not been initialized")

        self.iteration += 1
        iter_dir = self.run_dir / f"iter_{self.iteration:03d}"
        iter_dir.mkdir(parents=True, exist_ok=True)

        self._copy_skill(skill_path, iter_dir / "skill")
        logger.info("Iteration %03d created at %s", self.iteration, iter_dir)
        return iter_dir

    def save_scan_result(
        self,
        result: dict[str, Any],
        iter_dir: Path,
        analysis: dict[str, Any] | None = None,
    ) -> None:
        """保存扫描结果到迭代目录。

        result 字典可能包含以下富化字段（由 orchestrator 注入）：
        - iteration_timing: 每迭代的计时信息（各阶段时间戳和耗时）
        - update_context: 更新决策的完整上下文（scanner 检测信息到 rewrite 策略的映射）
        - timed_out_scanners: 超时扫描器名称列表
        """
        self.save_llm_judgement_audit(result, iter_dir)
        compact_result = self._compact_llm_judgement(result)
        payload = {**compact_result, "generator_analysis": analysis} if analysis else compact_result
        output_file = iter_dir / "scan_result.json"
        save_json_atomic(payload, output_file)
        logger.debug("Scan result saved to %s", output_file)

        # 保存各 scanner 的原始输出到文本文件
        self.save_scanner_raw_outputs(result, iter_dir)
        self.save_scanner_cli_audits(result, iter_dir)

    def save_llm_judgement_audit(self, result: dict[str, Any], iter_dir: Path) -> None:
        """Persist full LLM judgement audit material when present."""
        judgement = result.get("llm_judgement")
        if not isinstance(judgement, dict):
            return
        audit = judgement.get("audit")
        if not isinstance(audit, dict):
            return

        audit_dir = iter_dir / "llm_judgement"
        scanner_outputs = audit.get("scanner_outputs", {})
        sanitized_scanner_outputs = self._sanitize_judge_scanner_outputs(scanner_outputs)
        save_json_atomic(sanitized_scanner_outputs, audit_dir / "scanner_outputs.json")
        _save_text_atomic(str(audit.get("prompt", "")), audit_dir / "prompt.txt")
        _save_text_atomic(str(audit.get("raw_response", "")), audit_dir / "response.txt")
        parsed = audit.get("parsed_judgement", {})
        save_json_atomic(parsed if isinstance(parsed, dict) else {"raw": parsed}, audit_dir / "judgement.json")

    def _sanitize_judge_scanner_outputs(self, scanner_outputs: Any) -> dict[str, Any]:
        if not isinstance(scanner_outputs, dict):
            return {}

        sanitized: dict[str, Any] = {}
        for scanner_name, payload in scanner_outputs.items():
            if not isinstance(payload, dict):
                sanitized[str(scanner_name)] = payload
                continue
            metadata = payload.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            sanitized[str(scanner_name)] = {
                "findings": payload.get("findings", []),
                "metadata": metadata,
                "raw_output_text": str(payload.get("raw_output_text", "")),
            }
        return sanitized

    def _compact_llm_judgement(self, result: dict[str, Any]) -> dict[str, Any]:
        """Remove bulky Claude output and audit material from scan_result.json payload."""
        compact_result = dict(result)

        judgement = compact_result.get("llm_judgement")
        if isinstance(judgement, dict) and "audit" in judgement:
            compact_result["llm_judgement"] = {
                key: value for key, value in judgement.items() if key != "audit"
            }

        scanner_results = compact_result.get("scanner_results")
        if isinstance(scanner_results, dict):
            compact_result["scanner_results"] = {
                name: self._compact_scanner_payload(payload)
                for name, payload in scanner_results.items()
            }

        scanners = compact_result.get("scanners")
        if isinstance(scanners, dict):
            compact_result["scanners"] = {
                name: self._compact_pipeline_scanner_payload(payload)
                for name, payload in scanners.items()
            }

        return compact_result

    def _compact_scanner_payload(self, payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload

        compact_payload = {
            key: value
            for key, value in payload.items()
            if key not in {"raw_output_text", "claude_cli_audit"}
        }
        judgement = compact_payload.get("llm_judgement")
        if isinstance(judgement, dict) and "audit" in judgement:
            compact_payload["llm_judgement"] = {
                key: value for key, value in judgement.items() if key != "audit"
            }
        return compact_payload

    def _compact_pipeline_scanner_payload(self, payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload

        compact_payload = dict(payload)
        raw_result = compact_payload.get("raw_result")
        if isinstance(raw_result, dict):
            compact_payload["raw_result"] = self._compact_scanner_payload(raw_result)
        judgement = compact_payload.get("llm_judgement")
        if isinstance(judgement, dict) and "audit" in judgement:
            compact_payload["llm_judgement"] = {
                key: value for key, value in judgement.items() if key != "audit"
            }
        return compact_payload

    def save_scan_result_external(
        self,
        result: dict[str, Any],
        iter_dir: Path,
        skill_path: Path | None = None,
        analysis: dict[str, Any] | None = None,
    ) -> None:
        """保存扫描结果到外部指定目录。"""
        iter_dir.mkdir(parents=True, exist_ok=True)
        if skill_path:
            self._copy_skill(Path(skill_path), iter_dir / "skill")
        self.save_scan_result(result, iter_dir, analysis)

    def save_scanner_raw_outputs(self, result: dict[str, Any], iter_dir: Path) -> None:
        """将各 scanner 的 raw_output_text 保存为独立的文本文件。

        文件保存在 iter_dir/scanner_outputs/{scanner_name}.txt。
        兼容两种结果格式：
        - 统一格式: result["scanner_results"][scanner_name]
        - Pipeline 格式: result["scanners"][scanner_name]["raw_result"]
        """
        scanner_results = result.get("scanner_results", {})

        # Pipeline orchestrator 格式: scanners.{name}.raw_result
        if not scanner_results:
            scanners = result.get("scanners", {})
            scanner_results = {
                name: data.get("raw_result", {})
                for name, data in scanners.items()
                if isinstance(data, dict)
            }

        if not scanner_results:
            return

        outputs_dir = iter_dir / "scanner_outputs"
        has_output = False

        for scanner_name, scanner_data in scanner_results.items():
            if not isinstance(scanner_data, dict):
                continue
            if scanner_name in CLAUDE_BASED_SCANNERS:
                continue
            raw_text = scanner_data.get("raw_output_text")
            if raw_text:
                outputs_dir.mkdir(parents=True, exist_ok=True)
                output_file = outputs_dir / f"{scanner_name}.txt"
                _save_text_atomic(raw_text, output_file)
                has_output = True

        if not has_output and outputs_dir.exists():
            # 清理空目录
            try:
                outputs_dir.rmdir()
            except OSError:
                pass

    def save_scanner_cli_audits(self, result: dict[str, Any], iter_dir: Path) -> None:
        """Persist Claude CLI stdout/stderr/returncode audit snapshots when present."""
        scanner_results = result.get("scanner_results", {})

        if not scanner_results:
            scanners = result.get("scanners", {})
            scanner_results = {
                name: data.get("raw_result", {})
                for name, data in scanners.items()
                if isinstance(data, dict)
            }

        if not scanner_results:
            return

        audit_dir = iter_dir / "claude_cli_audit"
        wrote_any = False

        for scanner_name, scanner_data in scanner_results.items():
            if not isinstance(scanner_data, dict):
                continue
            cli_audit = scanner_data.get("claude_cli_audit")
            if not isinstance(cli_audit, dict):
                continue
            audit_dir.mkdir(parents=True, exist_ok=True)
            save_json_atomic(cli_audit, audit_dir / f"{scanner_name}.json")
            wrote_any = True

        if not wrote_any and audit_dir.exists():
            try:
                audit_dir.rmdir()
            except OSError:
                pass

    def finalize_session(self) -> Path:
        """结束实验会话并写入摘要。"""
        if not self.enabled or not self.session_id or self.run_dir is None:
            logger.warning("No active experiment session to finalize")
            return Path()

        end_time = datetime.now()
        summary = {
            "session_id": self.session_id,
            "total_iterations": self.iteration,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": end_time.isoformat(),
            "duration_seconds": (
                (end_time - self.start_time).total_seconds()
                if self.start_time
                else 0
            ),
        }

        session_dir = self.run_dir.parent
        save_json_atomic(summary, session_dir / "summary.json")
        logger.info("Experiment session finalized. Summary saved to %s", session_dir / "summary.json")

        self.session_id = None
        self.iteration = 0
        self.start_time = None
        return session_dir

    def _copy_skill(self, source_path: Path, target_path: Path) -> None:
        if source_path.resolve() == target_path.resolve():
            return
        if target_path.exists():
            shutil.rmtree(target_path)
        shutil.copytree(source_path, target_path)
