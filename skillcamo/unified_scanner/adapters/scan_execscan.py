"""
ScanExecscanAdapter - 适配 execution-grounded multimodal scanner.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import time
import uuid
from pathlib import Path

try:
    from ..models import Severity, SourceScanner, ThreatCategory, UnifiedFinding
    from ..paths import get_scanner_path
    from .base import BaseAdapter
    from ..llm_audit import LLMAuditConfig, create_auditor_from_config
except ImportError:
    from models import Severity, SourceScanner, ThreatCategory, UnifiedFinding
    from paths import get_scanner_path
    from adapters.base import BaseAdapter
    from llm_audit import LLMAuditConfig, create_auditor_from_config


class ScanExecscanAdapter(BaseAdapter):
    """Adapter for `scan_execscan`."""

    scanner_name = "scan_execscan"
    scanner_display_name = "scan_execscan"

    def __init__(
        self,
        *,
        model: str | None = None,
        model_a: str | None = None,
        model_b: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        audit_config: LLMAuditConfig | dict | None = None,
    ):
        super().__init__()
        self.model = model
        self.model_a = model_a or model
        self.model_b = model_b or model
        self.api_key = api_key
        self.base_url = base_url
        self._audit_config = audit_config
        self._auditor = create_auditor_from_config(audit_config, source="ScanExecscanAdapter")
        self._availability_error: str | None = None
        self._review_skill = self._load_review_skill()

    def _load_review_skill(self):
        try:
            return importlib.import_module("skillcamo.defenses.execscan").review_skill
        except ImportError:
            scanners_root = get_scanner_path("scan_execscan").parent
            root = scanners_root.parent
            for path in (root, scanners_root):
                path_str = str(path)
                if path_str not in sys.path:
                    sys.path.insert(0, path_str)
            return importlib.import_module("skillcamo.defenses.execscan").review_skill

    def _check_availability(self) -> bool:
        scanner_path = get_scanner_path("scan_execscan")
        if not scanner_path.exists():
            self._availability_error = f"扫描器目录不存在: {scanner_path}"
            return False
        if not os.environ.get("OPENAI_API_KEY") and not self.api_key:
            self._availability_error = "OPENAI_API_KEY 环境变量未设置且未通过配置传入 api_key"
            return False
        try:
            self._review_skill = self._load_review_skill()
        except Exception as exc:
            self._availability_error = f"{type(exc).__name__}: {exc}"
            return False
        self._availability_error = None
        return True

    def scan(self, skill_path: str | Path, **kwargs) -> dict:
        start_time = time.time()
        skill_path = Path(skill_path)

        if not self.is_available():
            return {
                "findings": [],
                "metadata": {
                    "scanner": self.scanner_name,
                    "error": self._availability_error or "Scanner not available",
                    "error_type": "ScannerUnavailable",
                },
            }

        try:
            previous_api_key = os.environ.get("OPENAI_API_KEY")
            previous_base_url = os.environ.get("OPENAI_BASE_URL")
            if self.api_key:
                os.environ["OPENAI_API_KEY"] = self.api_key
            if self.base_url:
                os.environ["OPENAI_BASE_URL"] = self.base_url

            # 记录请求审计（扫描器级别）
            if self._auditor and self._auditor.enabled:
                self._auditor.log_request(
                    provider="openai",
                    model=self.model_a or "gpt-5-mini",
                    prompt=f"Scan skill with execscan (model_a={self.model_a}, model_b={self.model_b})",
                    system_prompt="",
                    source="ScanExecscanAdapter",
                    metadata={
                        "skill_path": str(skill_path),
                        "scanner": "scan_execscan",
                        "model_a": self.model_a,
                        "model_b": self.model_b,
                    },
                )

            result = self._review_skill(
                skill_path,
                model_a=self.model_a or "gpt-5-mini",
                model_b=self.model_b or "gpt-5-mini",
            )
            duration_ms = int((time.time() - start_time) * 1000)
            findings = [self._normalize_finding(item) for item in result.get("findings", [])]

            # ExecScan 的 verdict/final_score 是主决策，但图像类 SkillCamo 攻击的风险落在
            # risk_judgment / execution_simulation、findings[] 为空 → 框架按 findings 算
            # detected 会漏检（实测：verdict=Malicious/final_score=0.95 却 0 finding → bypass）。
            # 当 verdict=Malicious（或 final_score≥0.80）且无 HIGH/CRITICAL finding 时，从
            # risk_judgment 合成一个 CRITICAL finding，使 detected 忠实反映 ExecScan 的 verdict。
            verdict = str(result.get("verdict") or "").strip().lower()
            final_score = result.get("final_score")
            has_hc = any(f.severity in (Severity.HIGH, Severity.CRITICAL) for f in findings)
            score_high = isinstance(final_score, (int, float)) and final_score >= 0.80
            if not has_hc and (verdict == "malicious" or score_high):
                rj = result.get("risk_judgment") or {}
                if not isinstance(rj, dict):
                    rj = {}
                sim = result.get("execution_simulation") or {}
                sim = sim if isinstance(sim, dict) else {}
                evidence = (rj.get("delta_explanation") or rj.get("reasoning")
                            or sim.get("execution_chain_summary") or "")
                ptv = rj.get("primary_threat_vector")
                title = (f"ExecScan verdict: malicious ({ptv} threat)"
                         if ptv else "ExecScan verdict: malicious skill")
                findings.append(UnifiedFinding(
                    id=f"scan-execscan-verdict-{uuid.uuid4().hex[:8]}",
                    source_scanner=SourceScanner.SCAN_EXECSCAN,
                    severity=Severity.CRITICAL,
                    category=ThreatCategory.OTHER,
                    title=title,
                    description=evidence or "ExecScan flagged this skill as malicious.",
                    file_path=None,
                    line_number=None,
                    snippet=evidence or None,
                    remediation=None,
                    metadata={
                        "verdict": result.get("verdict"),
                        "final_score": final_score,
                        "risk_judgment": rj,
                        "synthesized_from_verdict": True,
                    },
                ))

            # 记录响应审计（扫描器级别）
            if self._auditor and self._auditor.enabled:
                self._auditor.log_response(
                    raw_response=json.dumps(result, ensure_ascii=False),
                    parsed_response={"findings_count": len(findings), "verdict": result.get("verdict")},
                    duration_ms=duration_ms,
                )
                self._auditor.save()
                self._auditor.append_to_index()

            return {
                "findings": [f.to_dict() for f in findings],
                "metadata": {
                    "scanner": self.scanner_name,
                    "duration_ms": duration_ms,
                    "model": self.model,
                    "model_a": self.model_a or "gpt-5-mini",
                    "model_b": self.model_b or "gpt-5-mini",
                    "base_url": self.base_url,
                    "verdict": result.get("verdict"),
                    "final_score": result.get("final_score"),
                    "final_assessment": result.get("final_assessment"),
                },
                "raw": result,
                "raw_output_text": json.dumps(result, ensure_ascii=False, indent=2),
            }
        except Exception as exc:
            # 记录错误审计
            if self._auditor and self._auditor.enabled:
                self._auditor.log_response(
                    raw_response="",
                    error=f"{type(exc).__name__}: {exc}",
                    duration_ms=int((time.time() - start_time) * 1000),
                )
                self._auditor.save()

            return {
                "findings": [],
                "metadata": {
                    "scanner": self.scanner_name,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
                "raw_output_text": f"Error: {type(exc).__name__}: {exc}",
            }
        finally:
            if self.api_key:
                if previous_api_key is None:
                    os.environ.pop("OPENAI_API_KEY", None)
                else:
                    os.environ["OPENAI_API_KEY"] = previous_api_key
            if self.base_url:
                if previous_base_url is None:
                    os.environ.pop("OPENAI_BASE_URL", None)
                else:
                    os.environ["OPENAI_BASE_URL"] = previous_base_url

    def _normalize_finding(self, finding: dict) -> UnifiedFinding:
        line_number = self._parse_line_number(finding.get("lines"))
        category = self._normalize_category(finding.get("category"))
        evidence = str(finding.get("evidence", "")).strip()
        why = str(finding.get("why_it_matters", "")).strip()
        description = evidence
        if why:
            description = f"{evidence} {why}".strip()

        return UnifiedFinding(
            id=finding.get("id", f"scan-execscan-{uuid.uuid4().hex[:8]}"),
            source_scanner=SourceScanner.SCAN_EXECSCAN,
            severity=self._normalize_severity(finding.get("severity")),
            category=category,
            title=finding.get("title") or finding.get("category") or "scan_execscan finding",
            description=description or "scan_execscan reported a security finding",
            file_path=finding.get("file"),
            line_number=line_number,
            snippet=evidence or None,
            remediation=finding.get("recommended_fix"),
            metadata={
                "lines": finding.get("lines"),
                "exploit_scenario": finding.get("exploit_scenario"),
                "raw_finding": finding,
            },
        )

    def _normalize_severity(self, severity: str | None) -> Severity:
        mapping = {
            "critical": Severity.CRITICAL,
            "high": Severity.HIGH,
            "medium": Severity.MEDIUM,
            "low": Severity.LOW,
            "info": Severity.INFO,
        }
        if not severity:
            return Severity.INFO
        return mapping.get(str(severity).strip().lower(), Severity.INFO)

    def _normalize_category(self, category: str | None) -> ThreatCategory:
        if not category:
            return ThreatCategory.OTHER
        try:
            return ThreatCategory(str(category).strip().lower())
        except ValueError:
            return ThreatCategory.OTHER

    def _parse_line_number(self, lines: str | None) -> int | None:
        if not lines:
            return None
        head = str(lines).split("-", 1)[0].strip()
        return int(head) if head.isdigit() else None
