"""
ScanSkillVetterAdapter - 调用 skill-vetter 进行安全审查

通过 Claude CLI 调用 scan_skill_vetter skill 执行安全审查。
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from ..models import Severity, ThreatCategory
    from .skill_scanner_base import SkillBasedScannerAdapter
except ImportError:
    from models import Severity, ThreatCategory
    from adapters.skill_scanner_base import SkillBasedScannerAdapter


class ScanSkillVetterAdapter(SkillBasedScannerAdapter):
    """
    Skill Vetter 适配器

    scan_skill_vetter skill 路径: scan_skill_vetter/SKILL.md (通过 paths.py 动态解析)
    """

    scanner_name = "scan_skill_vetter"
    scanner_display_name = "Skill Vetter"

    def __init__(
        self,
        timeout: int | None = None,
        max_retries: int | None = None,
        model: str | None = None,
        provider_env: dict[str, str] | None = None,
    ):
        super().__init__(
            timeout=timeout, max_retries=max_retries, model=model, provider_env=provider_env
        )

    def get_skill_name(self) -> str:
        """返回 skill 名称"""
        return "scan_skill_vetter"

    def get_skill_source_path(self) -> Path:
        """返回 skill 源文件路径"""
        try:
            from skillcamo.framework.paths import get_scanner_path
        except ImportError:
            from paths import get_scanner_path
        return get_scanner_path("scan_skill_vetter")

    def build_scan_prompt(self, skill_path: Path, skill_content: str) -> str:
        """构建扫描 prompt

        不指定输出格式，让 SKILL.md 自身的输出格式定义生效。
        """
        return self._build_isolated_prompt(skill_content)

    def parse_findings(self, content: str, skill_path: Path) -> list[dict]:
        """Parse Claude output into structured findings.

        Uses the base-class ``_strip_json_fences`` to strip markdown fences
        before attempting JSON extraction.  Falls back to the Vetter-specific
        Markdown report parser and free-form parser when the output is not JSON.
        """
        parsed, stripped = self._strip_json_fences(content)
        if parsed:
            return self._parse_json_findings(parsed)

        # Non-JSON output — try structured Markdown template, then free-form
        findings = self._parse_markdown_report(stripped)
        if findings:
            return findings
        return self._parse_freeform_report(stripped)

    def _parse_json_findings(self, data: dict) -> list[dict]:
        """从 JSON 数据中提取 findings"""
        findings = []

        for flag in data.get("red_flags", []):
            severity_str = flag.get("severity", "MEDIUM")
            try:
                severity = Severity(severity_str)
            except ValueError:
                severity = Severity.MEDIUM

            findings.append(self._create_finding(
                title=flag.get("title", "Security concern"),
                description=flag.get("description", ""),
                severity=severity,
                category=ThreatCategory.RED_FLAG,
                file_path=flag.get("file_path"),
                line_number=flag.get("line_number"),
                snippet=flag.get("snippet"),
                metadata={
                    "permissions_needed": data.get("permissions_needed", {}),
                    "risk_level": data.get("risk_level"),
                    "verdict": data.get("verdict"),
                },
            ))

        # 添加总体评估
        if data.get("risk_level") or data.get("verdict"):
            findings.append(self._create_summary_finding(data))

        return findings

    def _parse_markdown_report(self, content: str) -> list[dict]:
        """解析 Markdown 格式的报告

        支持 scan_skill_vetter 的标准报告格式：
        - RED FLAGS: [None / 列表]
        - PERMISSIONS NEEDED:
        - RISK LEVEL: [LOW / MEDIUM / HIGH / EXTREME]
        - VERDICT: [SAFE_TO_INSTALL / INSTALL_WITH_CAUTION / DO_NOT_INSTALL]
        """
        findings = []
        lines = content.split('\n')

        # 解析状态
        red_flags = []
        permissions_needed = {"files": [], "network": [], "commands": []}
        risk_level = None
        verdict = None
        notes = []

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # 解析 RED FLAGS
            if line.startswith('RED FLAGS:') or line.startswith('**RED FLAGS:**'):
                flag_value = line.split(':', 1)[1].strip()
                if flag_value and flag_value.lower() != 'none':
                    red_flags.append(flag_value)
                # 继续读取后续的 bullet 列表
                i += 1
                while i < len(lines):
                    next_line = lines[i].strip()
                    if next_line.startswith('•') or next_line.startswith('-') or next_line.startswith('*'):
                        flag_text = next_line.lstrip('•-*').strip()
                        if (
                            flag_text
                            and not flag_text.lower().startswith("none of the")
                            and not flag_text.lower().startswith("caution items")
                            and "not found in the reviewed files" not in flag_text.lower()
                        ):
                            red_flags.append(flag_text)
                        i += 1
                    elif next_line.startswith('PERMISSIONS') or next_line.startswith('RISK LEVEL') or not next_line:
                        break
                    else:
                        break
                continue

            # 解析 PERMISSIONS NEEDED
            if line.startswith('PERMISSIONS NEEDED:') or line.startswith('**PERMISSIONS NEEDED:**'):
                i += 1
                while i < len(lines):
                    perm_line = lines[i].strip()
                    if perm_line.startswith('•') or perm_line.startswith('-'):
                        perm_text = perm_line.lstrip('•-*').strip()
                        if ':' in perm_text:
                            key, value = perm_text.split(':', 1)
                            key = key.strip().lower()
                            value = value.strip()
                            if key in ['files', 'network', 'commands']:
                                if value and value.lower() != 'none':
                                    permissions_needed[key].append(value)
                        i += 1
                    elif perm_line.startswith('RISK LEVEL') or not perm_line or perm_line.startswith('─'):
                        break
                    else:
                        i += 1
                continue

            # 解析 RISK LEVEL
            if line.startswith('RISK LEVEL:') or line.startswith('**RISK LEVEL:**'):
                risk_text = line.split(':', 1)[1].strip()
                # 移除 emoji
                for emoji in ['🟢', '🟡', '🔴', '⛔']:
                    risk_text = risk_text.replace(emoji, '')
                risk_level = risk_text.strip().upper()
                i += 1
                continue

            # 解析 VERDICT
            if line.startswith('VERDICT:') or line.startswith('**VERDICT:**'):
                verdict_text = line.split(':', 1)[1].strip()
                # 移除 emoji 和括号
                for emoji in ['✅', '⚠️', '❌']:
                    verdict_text = verdict_text.replace(emoji, '')
                verdict = verdict_text.strip().upper().replace(' ', '_')
                i += 1
                continue

            # 解析 NOTES
            if line.startswith('NOTES:') or line.startswith('**NOTES:**'):
                note_text = line.split(':', 1)[1].strip()
                if note_text:
                    notes.append(note_text)
                i += 1
                continue

            i += 1

        # 创建 red flag findings
        for flag in red_flags:
            severity = self._infer_severity_from_text(flag)
            findings.append(self._create_finding(
                title="Red Flag Detected",
                description=flag,
                severity=severity,
                category=ThreatCategory.RED_FLAG,
            ))

        # 创建总结 finding（包含风险评估）
        if risk_level or verdict:
            findings.append(self._create_summary_finding({
                "risk_level": risk_level or "UNKNOWN",
                "verdict": verdict or "UNKNOWN",
                "permissions_needed": permissions_needed,
                "red_flags": red_flags,
                "notes": " ".join(notes) if notes else None,
            }))

        return findings

    def _parse_freeform_report(self, content: str) -> list[dict]:
        """Parse free-form quick-review output."""
        findings = []
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        risk_level = None
        verdict = None

        for line in lines:
            upper = line.upper()
            if "风险等级" in line or "RISK LEVEL" in upper or "严重性" in line:
                if "HIGH" in upper or "高" in line:
                    risk_level = "HIGH"
                elif "MEDIUM" in upper or "中" in line:
                    risk_level = "MEDIUM"
                elif "LOW" in upper or "低" in line:
                    risk_level = "LOW"
            if "不建议安装" in line or "DO_NOT_INSTALL" in upper:
                verdict = "DO_NOT_INSTALL"
            elif "INSTALL WITH CAUTION" in upper or "谨慎" in line:
                verdict = "INSTALL_WITH_CAUTION"

            interesting = (
                "关键证据" in line
                or "可疑命令" in line
                or "敏感信息泄露" in line
                or "数据外泄" in line
                or "git config" in line.lower()
                or "curl" in line.lower()
            )
            if not interesting:
                continue

            file_path, line_number = self._extract_first_location(line)
            findings.append(self._create_finding(
                title="Red Flag Detected",
                description=line,
                severity=self._infer_report_severity(line),
                category=ThreatCategory.RED_FLAG,
                file_path=file_path,
                line_number=line_number,
            ))

        if (risk_level or verdict) and not (
            len(findings) == 1 and findings[0]["title"].startswith("Skill Vetter Assessment:")
        ):
            findings.append(self._create_summary_finding({
                "risk_level": risk_level or "UNKNOWN",
                "verdict": verdict or "UNKNOWN",
                "permissions_needed": {},
            }))

        return findings

    def _infer_severity_from_text(self, text: str) -> Severity:
        """从文本推断严重程度

        优先级：emoji 标记 → red flag 默认 HIGH。
        Emoji 映射：⛔→CRITICAL, 🔴→HIGH, 🟡→MEDIUM, 🟢→LOW。
        无 emoji 时，red flag 本身即为 🔴 级别 → HIGH。
        """
        emoji_severity = self._parse_emoji_severity(text)
        if emoji_severity != Severity.MEDIUM:
            return emoji_severity
        return Severity.HIGH

    def _create_summary_finding(self, data: dict) -> dict:
        """创建摘要 finding"""
        risk_level = data.get("risk_level", "MEDIUM")
        verdict = data.get("verdict", "UNKNOWN")

        severity_map = {
            "LOW": Severity.INFO,
            "MEDIUM": Severity.MEDIUM,
            "HIGH": Severity.HIGH,
            "EXTREME": Severity.CRITICAL,
            "REJECT": Severity.CRITICAL,
        }
        severity = severity_map.get(risk_level, Severity.MEDIUM)

        return self._create_finding(
            title=f"Skill Vetter Assessment: {risk_level} Risk",
            description=f"Verdict: {verdict}",
            severity=severity,
            category=ThreatCategory.POLICY_VIOLATION,
            metadata={
                "risk_level": risk_level,
                "verdict": verdict,
                "permissions_needed": data.get("permissions_needed", {}),
            },
        )
