"""
ScanSkillAuditorAdapter - 调用 ClawGuard Auditor 进行企业级安全审查

通过 Claude CLI 调用 scan_skill_auditor skill 执行 ClawGuard (CG-A) 的三阶段安全审查。
"""

import re
from pathlib import Path

try:
    from ..models import Severity, ThreatCategory
    from .skill_scanner_base import SkillBasedScannerAdapter
except ImportError:
    from models import Severity, ThreatCategory
    from adapters.skill_scanner_base import SkillBasedScannerAdapter


class ScanSkillAuditorAdapter(SkillBasedScannerAdapter):
    """
    ClawGuard Auditor (CG-A) 适配器

    scan_skill_auditor skill 路径: scan_skill_auditor/SKILL.md (通过 paths.py 动态解析)

    ClawGuard Auditor 提供企业级安全内核，包含：
    - Phase 1: 预飞行静态审查（SAST Red Flag Hunt、语义意图分析）
    - Phase 2: 运行时监督（能力令牌系统、主动威胁拦截）
    - Phase 3: 主动 DLP（数据掩码、外泄启发式）
    """

    scanner_name = "scan_skill_auditor"
    scanner_display_name = "ClawGuard Auditor (CG-A)"

    # Risk Tier 到 Severity 的映射
    RISK_TIER_MAP = {
        "TIER 0": Severity.INFO,
        "TIER 1": Severity.LOW,
        "TIER 2": Severity.HIGH,
        "TIER 3": Severity.CRITICAL,
        "TIER 4": Severity.CRITICAL,
        "TIER_0": Severity.INFO,
        "TIER_1": Severity.LOW,
        "TIER_2": Severity.HIGH,
        "TIER_3": Severity.CRITICAL,
        "TIER_4": Severity.CRITICAL,
    }

    # SAST finding 行的 emoji → severity
    SAST_EMOJI_SEVERITY = {
        "⚠️": None,  # 需要从文本提取（HIGH/CRITICAL）
        "🔴": Severity.CRITICAL,
        "📝": Severity.MEDIUM,
        "🟢": Severity.INFO,
    }

    def __init__(
        self,
        timeout: int | None = None,
        max_retries: int | None = None,
        model: str | None = None,
        provider_env: dict[str, str] | None = None,
    ):
        """
        初始化扫描器

        ClawGuard Auditor 需要更长的超时时间，因为：
        1. 使用 12000 tokens 的较大上下文
        2. 三阶段分析（Pre-Flight, Runtime, DLP）
        3. 企业级深度审查
        """
        super().__init__(
            timeout=timeout,
            max_retries=max_retries if max_retries is not None else 3,
            model=model,
            provider_env=provider_env,
        )

    def get_skill_name(self) -> str:
        """返回 skill 名称"""
        return "scan_skill_auditor"

    def get_skill_source_path(self) -> Path:
        """返回 skill 源文件路径"""
        try:
            from skillcamo.framework.paths import get_scanner_path
        except ImportError:
            from paths import get_scanner_path
        return get_scanner_path("scan_skill_auditor")

    def get_max_tokens(self) -> int:
        """ClawGuard 报告可能较长，需要更多 tokens"""
        return 12000

    def build_scan_prompt(self, skill_path: Path, skill_content: str) -> str:
        """构建扫描 prompt

        协议内联自扫描器 SKILL.md，不写入目录名/路径；不指定输出格式，让协议
        自身的输出格式定义生效。
        """
        return self._build_isolated_prompt(skill_content, action_verb="审计")

    def parse_findings(self, content: str, skill_path: Path) -> list[dict]:
        """Claude-based scanners do not parse agent output locally.

        The raw Claude output is preserved in ``raw_output_text`` and adjudicated
        later by the shared ``llm_judgement`` path.
        """
        return []

    def _parse_json_data(self, data: dict) -> list[dict]:
        """从 JSON 数据中提取 findings

        支持两种 JSON schema：
        1. Adapter 扁平 schema（findings[], risk_tier, guardian_verdict）
        2. SKILL.md 深层 schema（analysis.sast.findings[], verdict, risk_tier）
        """
        findings = []

        # 路径 A：SKILL.md 深层 schema（analysis.sast.findings）
        sast_findings = self._extract_nested(data, "analysis", "sast", "findings")
        if sast_findings:
            for f in sast_findings:
                severity_str = f.get("severity", "MEDIUM")
                try:
                    severity = Severity(severity_str)
                except ValueError:
                    severity = Severity.MEDIUM

                findings.append(self._create_finding(
                    title=f.get("title", "Security concern"),
                    description=f.get("evidence", ""),
                    severity=severity,
                    category=f.get("category", "other"),
                    file_path=f.get("location"),
                    metadata={
                        "phase": "PHASE_1",
                        "risk_tier": self._extract_nested(data, "risk_tier"),
                        "guardian_verdict": self._extract_nested(data, "verdict"),
                        "risk_score": self._extract_nested(data, "risk_score"),
                    },
                ))

        # 路径 B：Adapter 扁平 schema（findings[]）
        if not sast_findings:
            for finding in data.get("findings", []):
                category_str = finding.get("category", "other")
                try:
                    category = ThreatCategory(category_str)
                except ValueError:
                    category = category_str

                severity_str = finding.get("severity", "MEDIUM")
                try:
                    severity = Severity(severity_str)
                except ValueError:
                    severity = Severity.MEDIUM

                findings.append(self._create_finding(
                    title=finding.get("title", "Security concern"),
                    description=finding.get("description", ""),
                    severity=severity,
                    category=category,
                    file_path=finding.get("file_path"),
                    line_number=finding.get("line_number"),
                    snippet=finding.get("snippet"),
                    metadata={
                        "phase": finding.get("phase"),
                        "capabilities_required": data.get("capabilities_required", []),
                        "risk_tier": data.get("risk_tier"),
                        "guardian_verdict": data.get("guardian_verdict"),
                        "stated_purpose": data.get("stated_purpose"),
                        "actual_behavior": data.get("actual_behavior"),
                        "intent_match": data.get("intent_match"),
                    },
                ))

        # 如果有 risk_tier / risk_level 但没有 findings，添加一个摘要 finding
        if not findings:
            risk_tier = (
                data.get("risk_tier")
                or self._extract_nested(data, "risk_tier")
            )
            # Also accept risk_level from normalized short responses
            risk_level = data.get("risk_level")
            risk_label = risk_tier or risk_level
            if risk_label:
                verdict = (
                    data.get("guardian_verdict")
                    or data.get("verdict")
                    or self._extract_nested(data, "verdict")
                    or "UNKNOWN"
                )
                # Try RISK_TIER_MAP first, then a plain severity lookup
                severity = self.RISK_TIER_MAP.get(risk_label)
                if severity is None:
                    try:
                        severity = Severity(risk_label)
                    except ValueError:
                        severity = Severity.MEDIUM

                findings.append(self._create_finding(
                    title=f"ClawGuard Audit Complete - {risk_label}",
                    description=f"Guardian Verdict: {verdict}",
                    severity=severity,
                    category=ThreatCategory.OTHER,
                    metadata={
                        "risk_tier": risk_tier,
                        "risk_level": risk_level,
                        "guardian_verdict": verdict,
                    },
                ))

        return findings

    def _parse_terminal_report(self, content: str) -> list[dict]:
        """解析 ClawGuard 终端输出（ASCII-art 格式）

        SKILL.md 定义的终端格式关键模式：
        - SAST ANALYSIS 段: ⚠️ HIGH: Dynamic code execution (src/index.js:42)
        - 底部 box: VERDICT: APPROVED / RISK TIER: 🟢 TIER_1 / RISK SCORE: 15/100
        """
        findings = []
        lines = content.split('\n')

        risk_tier = None
        verdict = None
        risk_score = None
        in_sast = False

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            line_stripped = line.lstrip('║│ ').strip()

            # 检测 SAST ANALYSIS 段
            if 'SAST ANALYSIS' in line.upper() or 'SAST' in line.upper():
                in_sast = True
                i += 1
                continue

            # 离开 SAST 段（遇到其他 section 标题）
            if in_sast and (
                'SEMANTIC' in line.upper()
                or 'SUPPLY CHAIN' in line.upper()
                or 'ML ANOMALY' in line.upper()
                or 'SANDBOX' in line.upper()
                or line.startswith('╔')
            ):
                in_sast = False

            # 解析 SAST findings
            if in_sast:
                # 匹配: ⚠️ HIGH: description (file:line) 或 📝 MEDIUM: description
                sast_match = re.match(
                    r'^\s*(?:⚠️|📝|🔴|🟢)\s*(CRITICAL|HIGH|MEDIUM|LOW|INFO)\s*:\s*(.+)',
                    line_stripped,
                    re.IGNORECASE,
                )
                if sast_match:
                    sev_str = sast_match.group(1).upper()
                    desc_and_loc = sast_match.group(2).strip()

                    try:
                        severity = Severity(sev_str)
                    except ValueError:
                        severity = Severity.MEDIUM

                    # 提取 location: description (file:line)
                    location = None
                    loc_match = re.search(r'\(([^)]+\.\w+(?::\d+)?)\)', desc_and_loc)
                    if loc_match:
                        location = loc_match.group(1)
                        desc_and_loc = desc_and_loc[:loc_match.start()].strip()

                    # 读取后续行（Evidence/Recommendation）
                    evidence = None
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j].strip()
                        next_stripped = next_line.lstrip('║│ ').strip()
                        if not next_stripped:
                            break
                        ev_match = re.match(r'^\s*Evidence\s*:\s*(.+)', next_stripped, re.IGNORECASE)
                        if ev_match:
                            evidence = ev_match.group(1).strip()
                            j += 1
                            continue
                        # 不再是子行（新的 finding 或 section）
                        if re.match(r'^\s*(?:⚠️|📝|🔴|🟢)', next_stripped):
                            break
                        if any(s in next_stripped.upper() for s in ['SEMANTIC', 'SUPPLY', 'ML ANOMALY', 'SANDBOX']):
                            break
                        break

                    findings.append(self._create_finding(
                        title=desc_and_loc,
                        description=evidence or desc_and_loc,
                        severity=severity,
                        category=ThreatCategory.OTHER,
                        file_path=location,
                        metadata={
                            "phase": "PHASE_1",
                            "source": "terminal_report",
                        },
                    ))
                    i = j
                    continue

            # 解析底部 box 中的 VERDICT
            if 'VERDICT' in line_stripped.upper():
                verdict_match = re.search(
                    r'VERDICT\s*:\s*(APPROVED|REJECTED|APPROVED_WITH_SANDBOX|CONDITIONAL)',
                    line_stripped,
                    re.IGNORECASE,
                )
                if verdict_match:
                    verdict = verdict_match.group(1).upper()

            # 解析底部 box 中的 RISK TIER
            if 'RISK TIER' in line_stripped.upper():
                tier_match = re.search(r'(TIER\s*[_\s]?\s*\d)', line_stripped, re.IGNORECASE)
                if tier_match:
                    risk_tier = tier_match.group(1).upper().replace(' ', '')

            # 解析底部 box 中的 RISK SCORE
            if 'RISK SCORE' in line_stripped.upper():
                score_match = re.search(r'(\d+)\s*/\s*100', line_stripped)
                if score_match:
                    risk_score = int(score_match.group(1))

            i += 1

        # 添加摘要 finding
        if risk_tier or verdict:
            severity = self.RISK_TIER_MAP.get(risk_tier, Severity.MEDIUM) if risk_tier else Severity.INFO
            findings.append(self._create_finding(
                title=f"ClawGuard Audit Complete - {risk_tier or 'UNKNOWN'}",
                description=f"Guardian Verdict: {verdict or 'UNKNOWN'}"
                            + (f", Risk Score: {risk_score}/100" if risk_score is not None else ""),
                severity=severity,
                category=ThreatCategory.OTHER,
                metadata={
                    "risk_tier": risk_tier,
                    "guardian_verdict": verdict,
                    "risk_score": risk_score,
                    "source": "terminal_report",
                },
            ))

        return findings

    def _extract_nested(self, data: dict, *keys) -> object:
        """从嵌套 dict 中安全提取值"""
        current = data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
        return current

    def _parse_freeform_report(self, content: str) -> list[dict]:
        """Parse free-form auditor output with Summary/Findings/Severity sections."""
        findings = []
        current_title = None
        buffer: list[str] = []
        risk_line = None

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if re.match(r"^\d+\.\s+", line):
                if current_title:
                    findings.append(self._build_freeform_finding(current_title, buffer))
                current_title = re.sub(r"^\d+\.\s+", "", line)
                buffer = []
                continue
            if "Overall:" in line or "Overall：" in line or "high-risk" in line.lower():
                risk_line = line
            if current_title:
                buffer.append(line)

        if current_title:
            findings.append(self._build_freeform_finding(current_title, buffer))

        if risk_line:
            findings.append(self._create_finding(
                title="ClawGuard Audit Complete - FREEFORM",
                description=risk_line,
                severity=self._infer_report_severity(risk_line),
                category=ThreatCategory.OTHER,
                metadata={"source": "freeform_report"},
            ))

        return findings

    def _build_freeform_finding(self, title: str, details: list[str]) -> dict:
        detail_text = " ".join(details)
        file_path, line_number = self._extract_first_location(detail_text or title)
        return self._create_finding(
            title=title,
            description=f"{title}. {detail_text}".strip(),
            severity=self._infer_report_severity(f"{title} {detail_text}"),
            category=ThreatCategory.OTHER,
            file_path=file_path,
            line_number=line_number,
            metadata={"source": "freeform_report"},
        )
