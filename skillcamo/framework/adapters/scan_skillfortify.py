"""Adapter for SkillFortify scanner.

Integrates with the standalone scan_skillfortify package.
"""

import logging
import sys
import time
from pathlib import Path

try:
    from ..models import Severity
    from .base import BaseAdapter
except ImportError:
    from models import Severity
    from adapters.base import BaseAdapter

logger = logging.getLogger(__name__)

# 动态获取 scan_skillfortify 模块路径
try:
    from skillcamo.framework.paths import get_scanner_path
    scan_skillfortify_path = get_scanner_path("scan_skillfortify")
except ImportError:
    from paths import get_scanner_path
    scan_skillfortify_path = get_scanner_path("scan_skillfortify")

# 添加到 sys.path
if str(scan_skillfortify_path) not in sys.path:
    sys.path.insert(0, str(scan_skillfortify_path))

try:
    from scan_skillfortify.parsers.registry import default_registry
    from scan_skillfortify.core.analyzer.engine import StaticAnalyzer
    SKILLFORTIFY_AVAILABLE = True
    logger.info("scan_skillfortify module loaded successfully")
except ImportError as e:
    SKILLFORTIFY_AVAILABLE = False
    IMPORT_ERROR = str(e)
    logger.error(f"scan_skillfortify module not available: {e}")


class ScanSkillfortifyAdapter(BaseAdapter):
    """Adapter for embedded SkillFortify scanner."""

    scanner_name = "scan_skillfortify"
    scanner_display_name = "SkillFortify Scanner"

    def __init__(self):
        """初始化适配器"""
        super().__init__()

    def _check_availability(self) -> bool:
        return SKILLFORTIFY_AVAILABLE

    def scan(self, skill_path: str | Path, **kwargs) -> dict:
        """Scan a skill directory using embedded SkillFortify.

        Args:
            skill_path: Path to skill directory (should contain SKILL.md)
            **kwargs: Additional arguments (for interface consistency, currently unused)

        Returns:
            Dict with findings in unified_scanner format
        """
        start_time = time.time()
        logger.debug(f"scan_skillfortify: Starting scan of {skill_path}")

        if not SKILLFORTIFY_AVAILABLE:
            logger.error(f"scan_skillfortify: Module not available: {IMPORT_ERROR}")
            return {
                "findings": [],
                "metadata": {
                    "scanner": "scan_skillfortify",
                    "error": f"SkillFortify 模块不可用: {IMPORT_ERROR}",
                    "error_type": "ModuleNotAvailable",
                    "is_safe": None,  # None means unable to determine (technical error)
                }
            }

        try:
            # 1. Discover and parse skill
            skill_path = Path(skill_path)
            registry = default_registry()
            skills = registry.discover(skill_path)

            if not skills:
                logger.warning(f"scan_skillfortify: No skill found in {skill_path}")
                return {
                    "findings": [],
                    "metadata": {
                        "scanner": "scan_skillfortify",
                        "status": "no_skill_found",
                        "skill_path": str(skill_path),
                        "is_safe": None,  # None means unable to determine
                    }
                }

            # 2. Analyze each skill
            analyzer = StaticAnalyzer()
            all_findings = []
            raw_output_parts = []

            for skill in skills:
                result = analyzer.analyze(skill)
                for finding in result.findings:
                    all_findings.append({
                        "severity": finding.severity.name,
                        "category": finding.attack_class or "unknown",
                        "title": finding.message,
                        "description": finding.evidence or "",
                        "file_path": str(getattr(finding, 'file_path', None) or skill.source_path or "SKILL.md"),
                        "line_number": getattr(finding, 'line_number', None),
                        "finding_type": finding.finding_type,
                    })
                    raw_output_parts.append(
                        f"[{finding.severity.name}] {finding.message}\n"
                        f"  Type: {finding.finding_type}\n"
                        f"  Class: {finding.attack_class or 'unknown'}\n"
                        f"  File: {getattr(finding, 'file_path', 'N/A')}:{getattr(finding, 'line_number', 'N/A')}\n"
                        f"  Evidence: {finding.evidence or 'none'}"
                    )

            logger.info(f"scan_skillfortify: Scan completed, found {len(all_findings)} findings")

            # Calculate is_safe: no CRITICAL or HIGH severity findings
            is_safe = not any(
                f.get("severity") in (Severity.CRITICAL.name, Severity.HIGH.name)
                for f in all_findings
            )

            duration_ms = int((time.time() - start_time) * 1000)

            return {
                "findings": all_findings,
                "metadata": {
                    "scanner": "scan_skillfortify",
                    "total_skills": len(skills),
                    "skill_names": [s.name for s in skills],
                    "skill_path": str(skill_path),
                    "duration_ms": duration_ms,
                    "is_safe": is_safe,
                },
                "raw_output_text": "\n\n".join(raw_output_parts) if raw_output_parts else "No findings",
            }

        except Exception as e:
            logger.error(f"scan_skillfortify: Scan failed with {type(e).__name__}: {e}")
            return {
                "findings": [],
                "metadata": {
                    "scanner": "scan_skillfortify",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "is_safe": None,  # None means unable to determine (technical error)
                },
                "raw_output_text": f"Error: {type(e).__name__}: {e}",
            }
