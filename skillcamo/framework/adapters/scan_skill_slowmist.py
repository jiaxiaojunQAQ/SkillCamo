"""
ScanSlowmistAdapter - SlowMist Agent Security 适配器

通过 Claude CLI 调用 slowmist skill 进行安全审查。
SlowMist 提供基于知识库的安全模式检测。
"""

import re
from pathlib import Path

try:
    from ..models import Severity, ThreatCategory
    from .skill_scanner_base import SkillBasedScannerAdapter
except ImportError:
    from models import Severity, ThreatCategory
    from adapters.skill_scanner_base import SkillBasedScannerAdapter


class ScanSkillSlowmistAdapter(SkillBasedScannerAdapter):
    """
    SlowMist Agent Security 适配器

    scan_skill_slowmist skill 路径: scan_skill_slowmist/SKILL.md (通过 paths.py 动态解析)

    SlowMist 提供基于知识库的安全模式检测，包括：
    - 代码级危险模式（11类）
    - 社会工程学模式（8类）
    - 供应链攻击模式（7类）
    """

    scanner_name = "scan_skill_slowmist"
    scanner_display_name = "SlowMist Agent Security"

    # SlowMist 类别映射
    CATEGORY_MAP = {
        "data_exfiltration": ThreatCategory.DATA_EXFILTRATION,
        "command_injection": ThreatCategory.COMMAND_INJECTION,
        "social_engineering": ThreatCategory.SOCIAL_ENGINEERING,
        "supply_chain": ThreatCategory.SUPPLY_CHAIN_ATTACK,
        "privilege_escalation": ThreatCategory.PRIVILEGE_ESCALATION,
        "persistence": ThreatCategory.MALWARE,
        "obfuscation": ThreatCategory.OBFUSCATION,
        "credential_access": ThreatCategory.HARDCODED_SECRETS,
        "file_access": ThreatCategory.UNAUTHORIZED_TOOL_USE,
        "network": ThreatCategory.SUSPICIOUS_NETWORK,
    }

    # Risk level emoji → Severity
    RISK_SEVERITY_MAP = {
        "LOW": Severity.INFO,
        "MEDIUM": Severity.MEDIUM,
        "HIGH": Severity.HIGH,
        "REJECT": Severity.CRITICAL,
    }

    # Emoji → severity for inline red flag markers
    EMOJI_SEVERITY = {
        "⛔": Severity.CRITICAL,
        "🔴": Severity.HIGH,
        "🟡": Severity.MEDIUM,
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

        SlowMist 需要更长的超时时间，因为：
        1. 使用 12000 tokens 的较大上下文
        2. 需要检索知识库中的安全模式
        3. 多维度分析（代码、社会工程、供应链）
        """
        super().__init__(
            timeout=timeout,
            max_retries=max_retries if max_retries is not None else 3,
            model=model,
            provider_env=provider_env,
        )

    def get_skill_name(self) -> str:
        """返回 skill 名称"""
        return "scan_skill_slowmist"

    def get_skill_source_path(self) -> Path:
        """返回 skill 源文件路径"""
        try:
            from skillcamo.framework.paths import get_scanner_path
        except ImportError:
            from paths import get_scanner_path
        return get_scanner_path("scan_skill_slowmist")

    def get_max_tokens(self) -> int:
        """SlowMist 报告可能较长"""
        return 12000

    def build_scan_prompt(self, skill_path: Path, skill_content: str) -> str:
        """构建扫描 prompt

        协议内联自扫描器 SKILL.md，不写入目录名/路径；不指定输出格式，让协议
        和模板自身的输出格式定义生效。
        """
        return self._build_isolated_prompt(skill_content)

    def parse_findings(self, content: str, skill_path: Path) -> list[dict]:
        """Claude-based scanners do not parse agent output locally.

        The raw Claude output is preserved in ``raw_output_text`` and adjudicated
        later by the shared ``llm_judgement`` path.
        """
        return []

    def _parse_json_findings(self, data: dict) -> list[dict]:
        """从 JSON 数据中提取 findings"""
        findings = []

        for flag in data.get("red_flags", []):
            severity_str = flag.get("severity", "MEDIUM")
            try:
                severity = Severity(severity_str)
            except ValueError:
                severity = Severity.MEDIUM

            category_str = flag.get("category", "other")
            category = self.CATEGORY_MAP.get(category_str, ThreatCategory.OTHER)

            findings.append(self._create_finding(
                title=flag.get("title", "Security concern"),
                description=flag.get("description", ""),
                severity=severity,
                category=category,
                metadata={
                    "pattern_type": category_str,
                    "risk_level": data.get("risk_level"),
                    "verdict": data.get("verdict"),
                },
            ))

        # 添加总体评估
        if data.get("risk_level") or data.get("verdict"):
            findings.extend(self._build_summary_findings(
                data.get("risk_level", "UNKNOWN"),
                data.get("verdict", "UNKNOWN"),
                data.get("permissions", {}),
            ))

        return findings

    def _parse_slowmist_template(self, content: str) -> list[dict]:
        """解析 SlowMist 标准报告模板（ASCII-art box 格式）

        模板格式定义在 templates/report-skill.md，关键 section：
        - RED FLAGS: bullet 列表，带 (Severity: 🔴/🟡) 内联标记
        - RISK: emoji 风险等级（🟢 LOW / 🟡 MEDIUM / 🔴 HIGH / ⛔ REJECT）
        - VERDICT: 判定（✅ SAFE / ⚠️ CAUTION / ❌ REJECT）
        """
        findings = []
        lines = content.split('\n')

        # 提取各 section 的内容
        red_flags = []
        risk_level = None
        verdict = None

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            line_stripped = line.lstrip('║│ ').strip()

            # 解析 RED FLAGS 段
            if 'RED FLAGS' in line.upper() and not line.startswith('•') and not line.startswith('-'):
                i += 1
                while i < len(lines):
                    flag_line = lines[i].strip()
                    flag_line_stripped = flag_line.lstrip('║│ ').strip()
                    # 到达下一个 section（box 分隔线或已知 section 标题）
                    if flag_line_stripped.startswith('╠') or flag_line_stripped.startswith('╚'):
                        break
                    if any(s in flag_line_stripped.upper() for s in ['PERMISSIONS REQUIRED', 'RISK:', 'VERDICT:', 'NOTES', 'ARCHITECTURE']):
                        break
                    # 收集 bullet 项
                    for prefix in ['•', '-', '*']:
                        if flag_line_stripped.startswith(prefix):
                            flag_text = flag_line_stripped.lstrip('•-*').strip()
                            if flag_text and flag_text.lower() != 'none':
                                severity = self._extract_inline_severity(flag_text)
                                # 清理描述文本
                                desc = self._clean_flag_description(flag_text)
                                red_flags.append({"description": desc, "severity": severity})
                            break
                    i += 1
                continue

            # 解析 RISK 行
            if re.match(r'RISK\s*:', line_stripped, re.IGNORECASE):
                risk_text = line_stripped.split(':', 1)[1].strip() if ':' in line_stripped else ''
                risk_level = self._extract_risk_level(risk_text)
                i += 1
                continue

            # 解析 VERDICT 行
            if re.match(r'VERDICT\s*:', line_stripped, re.IGNORECASE):
                verdict_text = line_stripped.split(':', 1)[1].strip() if ':' in line_stripped else ''
                verdict = self._extract_verdict(verdict_text)
                i += 1
                continue

            i += 1

        # 创建 red flag findings
        for flag in red_flags:
            findings.append(self._create_finding(
                title="Red Flag Detected",
                description=flag["description"],
                severity=flag["severity"],
                category=ThreatCategory.RED_FLAG,
                metadata={"flag_type": "red_flag"},
            ))

        # 创建摘要 finding（包含风险等级和判定）
        if risk_level or verdict:
            findings.extend(self._build_summary_findings(
                risk_level or "UNKNOWN",
                verdict or "UNKNOWN",
                {},
            ))

        return findings

    def _extract_inline_severity(self, text: str) -> Severity:
        """从 red flag 文本中提取内联 severity（emoji 或关键词）"""
        # 先检查 emoji 标记：(Severity: 🔴/🟡) 或直接内嵌 emoji
        for emoji, sev in self.EMOJI_SEVERITY.items():
            if emoji in text:
                return sev
        # 检查文本关键词
        text_upper = text.upper()
        if 'CRITICAL' in text_upper or 'EXTREME' in text_upper:
            return Severity.CRITICAL
        if 'HIGH' in text_upper or 'DANGER' in text_upper:
            return Severity.HIGH
        if 'MEDIUM' in text_upper or 'CAUTION' in text_upper or 'WARNING' in text_upper:
            return Severity.MEDIUM
        if 'LOW' in text_upper:
            return Severity.INFO
        return Severity.MEDIUM

    def _clean_flag_description(self, text: str) -> str:
        """清理 red flag 描述文本，移除 severity 标记和 emoji"""
        desc = text
        # 移除 (Severity: 🔴/🟡) 标记
        desc = re.sub(r'\(?\s*Severity\s*[:：]\s*[🔴🟡🟢⛔HIGHMEDIUMLOWCRITICAL]+\.?\s*\)?', '', desc, flags=re.IGNORECASE)
        # 移除 emoji
        for emoji in ["🔴", "🟡", "🟢", "⛔", "⚠️", "❌", "✅"]:
            desc = desc.replace(emoji, "")
        return desc.strip()

    def _extract_risk_level(self, text: str) -> str | None:
        """从 RISK 行提取风险等级"""
        text_upper = text.upper()
        for level in ["REJECT", "HIGH", "MEDIUM", "LOW"]:
            if level in text_upper:
                return level
        return None

    def _extract_verdict(self, text: str) -> str | None:
        """从 VERDICT 行提取判定"""
        text_upper = text.upper()
        if "REJECT" in text_upper or "❌" in text:
            return "REJECT"
        if "CAUTION" in text_upper or "⚠" in text:
            return "CAUTION"
        if "SAFE" in text_upper or "✅" in text:
            return "SAFE"
        return None

    def _build_summary_findings(
        self, risk_level: str, verdict: str, permissions: dict,
    ) -> list[dict]:
        """构建摘要 findings（包含风险等级和判定）"""
        severity = self.RISK_SEVERITY_MAP.get(risk_level, Severity.INFO)
        return [self._create_finding(
            title=f"SlowMist Assessment: {risk_level} Risk",
            description=f"Verdict: {verdict}",
            severity=severity,
            category=ThreatCategory.POLICY_VIOLATION,
            metadata={
                "risk_level": risk_level,
                "verdict": verdict,
                "permissions": permissions,
            },
        )]

    def _parse_freeform_report(self, content: str) -> list[dict]:
        """Parse Chinese free-form quick-review output."""
        findings = []
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        risk_level = None

        for line in lines:
            if line.startswith("- 高") or "HIGH" in line.upper():
                risk_level = "HIGH"
            elif line.startswith("- 中") or "MEDIUM" in line.upper():
                risk_level = risk_level or "MEDIUM"

            if not (
                "可疑" in line
                or "风险" in line
                or "curl" in line.lower()
                or "外泄" in line
                or "网络出站" in line
            ):
                continue

            if line.startswith("- 可疑") or line.startswith("- 要求") or line.startswith("- 内容") or line.startswith("- 风险") or line.startswith("- 高") or line.startswith("- 中"):
                file_path, line_number = self._extract_first_location(line)
                findings.append(self._create_finding(
                    title="Red Flag Detected",
                    description=line.lstrip("- ").strip(),
                    severity=self._infer_report_severity(line),
                    category=ThreatCategory.RED_FLAG,
                    file_path=file_path,
                    line_number=line_number,
                    metadata={"source": "freeform_report"},
                ))

        if risk_level:
            findings.extend(self._build_summary_findings(risk_level, "CAUTION", {}))

        return findings
