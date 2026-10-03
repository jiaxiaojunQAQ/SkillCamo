"""Three-phase static analysis engine for agent skill security.

This is a minimal copy for integration into unified_scanner.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from scan_skillfortify.core.capabilities import AccessLevel, Capability, CapabilitySet
from scan_skillfortify.core.analyzer import AnalysisResult, Finding, Severity
from scan_skillfortify.parsers.base import ParsedSkill


# ---------------------------------------------------------------------------
# URL allow-list for safe domains
# ---------------------------------------------------------------------------

_SAFE_URL_DOMAINS: frozenset[str] = frozenset(
    {
        "github.com",
        "www.github.com",
        "pypi.org",
        "www.pypi.org",
        "npmjs.org",
        "www.npmjs.org",
        "npmjs.com",
        "www.npmjs.com",
    }
)

_SAFE_URL_DOMAIN_SUFFIXES: tuple[str, ...] = (
    ".github.com",
    ".pypi.org",
    ".npmjs.org",
    ".npmjs.com",
)


def _is_safe_url(url: str) -> bool:
    """Check if a URL belongs to a known-safe domain."""
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
    except Exception:
        return False

    if hostname in _SAFE_URL_DOMAINS:
        return True

    for suffix in _SAFE_URL_DOMAIN_SUFFIXES:
        if hostname.endswith(suffix):
            return True

    if hostname.startswith("docs."):
        return True

    return False


# ---------------------------------------------------------------------------
# Sensitive environment variable patterns
# ---------------------------------------------------------------------------

_SENSITIVE_ENV_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r".*SECRET.*", re.IGNORECASE),
    re.compile(r".*PASSWORD.*", re.IGNORECASE),
    re.compile(r".*TOKEN.*", re.IGNORECASE),
    re.compile(r".*API[_-]?KEY.*", re.IGNORECASE),
    re.compile(r".*CREDENTIAL.*", re.IGNORECASE),
    re.compile(r".*PRIVATE[_-]?KEY.*", re.IGNORECASE),
    re.compile(r"^AWS_ACCESS_KEY_ID$", re.IGNORECASE),
    re.compile(r"^DATABASE_URL$", re.IGNORECASE),
)


def _is_sensitive_env_var(name: str) -> bool:
    """Check if an environment variable name matches a sensitive pattern."""
    return any(pat.match(name) for pat in _SENSITIVE_ENV_PATTERNS)


# ---------------------------------------------------------------------------
# Dangerous patterns
# ---------------------------------------------------------------------------

_EVAL_NAME = "ev" + "al"
_EXEC_NAME = "ex" + "ec"

_DANGEROUS_SHELL_PATTERNS: list[tuple[re.Pattern[str], Severity, str, str]] = [
    (re.compile(r"curl\s+.*\|\s*(ba)?sh", re.IGNORECASE), Severity.CRITICAL, "privilege_escalation", "Remote code: curl piped to shell"),
    (re.compile(r"wget\s+.*\|\s*(ba)?sh", re.IGNORECASE), Severity.CRITICAL, "privilege_escalation", "Remote code: wget piped to shell"),
    (re.compile(r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f|rm\s+-[a-zA-Z]*f[a-zA-Z]*r"), Severity.CRITICAL, "privilege_escalation", "Destructive operation: recursive forced removal (rm -rf)"),
    (re.compile(r"base64\s+-d.*\|\s*(ba)?sh", re.IGNORECASE), Severity.CRITICAL, "privilege_escalation", "Obfuscated code: base64 decode piped to shell"),
    (re.compile(r"nc\s+-l", re.IGNORECASE), Severity.CRITICAL, "data_exfiltration", "Network listener detected: netcat in listen mode"),
    (re.compile(r"chmod\s+777"), Severity.HIGH, "privilege_escalation", "Excessive permissions: chmod 777 grants world read/write/execute"),
]

_DANGEROUS_CODE_PATTERNS: list[tuple[re.Pattern[str], Severity, str, str]] = [
    (re.compile(rf"\b{_EVAL_NAME}\s*\("), Severity.HIGH, "privilege_escalation", f"Dynamic code evaluation: {_EVAL_NAME}() can run arbitrary code"),
    (re.compile(rf"\b{_EXEC_NAME}\s*\("), Severity.HIGH, "privilege_escalation", f"Dynamic code evaluation: {_EXEC_NAME}() can run arbitrary code"),
]

_POST_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"-X\s+POST", re.IGNORECASE),
    re.compile(r"-X\s+PUT", re.IGNORECASE),
    re.compile(r"-X\s+PATCH", re.IGNORECASE),
    re.compile(r"-X\s+DELETE", re.IGNORECASE),
    re.compile(r"--data\b", re.IGNORECASE),
    re.compile(r"-d\s+['\"]", re.IGNORECASE),
)

_FILE_READ_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bread[s]?\s+file", re.IGNORECASE),
    re.compile(r"\bopen[s]?\s+file", re.IGNORECASE),
    re.compile(r"\bload[s]?\s+file", re.IGNORECASE),
    re.compile(r"\bread[s]?\s+from\s+", re.IGNORECASE),
)

_FILE_WRITE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bwrite[s]?\s+to\s+", re.IGNORECASE),
    re.compile(r"\bwrite[s]?\s+file", re.IGNORECASE),
    re.compile(r"\bsave[s]?\s+to\s+", re.IGNORECASE),
    re.compile(r"\bcreate[s]?\s+file", re.IGNORECASE),
)

_BASE64_PATTERN: re.Pattern[str] = re.compile(r"\bbase64\b", re.IGNORECASE)


class StaticAnalyzer:
    """Three-phase static analyzer for agent skill security."""

    def analyze(self, skill: ParsedSkill) -> AnalysisResult:
        """Analyze a parsed skill and return all security findings."""
        findings: list[Finding] = []

        # Phase 1: Capability inference
        inferred = self._infer_capabilities(skill)

        # Phase 2: Dangerous pattern detection
        findings.extend(self._detect_dangerous_patterns(skill))

        # Phase 3: Capability violation check
        if skill.declared_capabilities:
            findings.extend(self._check_capability_violations(skill, inferred))

        is_safe = len(findings) == 0

        return AnalysisResult(
            skill_name=skill.name,
            is_safe=is_safe,
            findings=findings,
            inferred_capabilities=inferred,
        )

    def _infer_capabilities(self, skill: ParsedSkill) -> CapabilitySet:
        """Infer the capability set a skill actually needs from its content."""
        caps = CapabilitySet()

        if skill.urls:
            network_level = AccessLevel.READ
            combined_shell = " ".join(skill.shell_commands)
            for pat in _POST_PATTERNS:
                if pat.search(combined_shell):
                    network_level = AccessLevel.WRITE
                    break
            caps.add(Capability("network", network_level))

        if skill.shell_commands:
            caps.add(Capability("shell", AccessLevel.WRITE))

        if skill.env_vars_referenced:
            caps.add(Capability("environment", AccessLevel.READ))

        combined_text = f"{skill.instructions} {skill.description}"
        has_file_write = any(pat.search(combined_text) for pat in _FILE_WRITE_PATTERNS)
        has_file_read = any(pat.search(combined_text) for pat in _FILE_READ_PATTERNS)

        if has_file_write:
            caps.add(Capability("filesystem", AccessLevel.WRITE))
        elif has_file_read:
            caps.add(Capability("filesystem", AccessLevel.READ))

        return caps

    def _detect_dangerous_patterns(self, skill: ParsedSkill) -> list[Finding]:
        """Detect known-dangerous patterns in the skill's content."""
        findings: list[Finding] = []

        for cmd in skill.shell_commands:
            for pattern, severity, attack_class, message in _DANGEROUS_SHELL_PATTERNS:
                if pattern.search(cmd):
                    findings.append(
                        Finding(
                            skill_name=skill.name,
                            severity=severity,
                            message=message,
                            attack_class=attack_class,
                            finding_type="pattern_match",
                            evidence=cmd,
                        )
                    )

        for block in skill.code_blocks:
            for pattern, severity, attack_class, message in _DANGEROUS_CODE_PATTERNS:
                if pattern.search(block):
                    findings.append(
                        Finding(
                            skill_name=skill.name,
                            severity=severity,
                            message=message,
                            attack_class=attack_class,
                            finding_type="pattern_match",
                            evidence=block,
                        )
                    )

        for url in skill.urls:
            if not _is_safe_url(url):
                findings.append(
                    Finding(
                        skill_name=skill.name,
                        severity=Severity.HIGH,
                        message=f"External URL detected: {url}",
                        attack_class="data_exfiltration",
                        finding_type="pattern_match",
                        evidence=url,
                    )
                )

        for env_var in skill.env_vars_referenced:
            if _is_sensitive_env_var(env_var):
                findings.append(
                    Finding(
                        skill_name=skill.name,
                        severity=Severity.HIGH,
                        message=f"Sensitive environment variable accessed: {env_var}",
                        attack_class="data_exfiltration",
                        finding_type="pattern_match",
                        evidence=env_var,
                    )
                )

        has_base64 = any(_BASE64_PATTERN.search(cmd) for cmd in skill.shell_commands) or any(
            _BASE64_PATTERN.search(block) for block in skill.code_blocks
        )
        has_external_urls = any(not _is_safe_url(url) for url in skill.urls)

        if has_base64 and has_external_urls:
            findings.append(
                Finding(
                    skill_name=skill.name,
                    severity=Severity.CRITICAL,
                    message="Information flow concern: base64 encoding combined with external network access suggests data exfiltration",
                    attack_class="data_exfiltration",
                    finding_type="info_flow",
                    evidence="base64 + external URL",
                )
            )

        return findings

    def _check_capability_violations(
        self, skill: ParsedSkill, inferred: CapabilitySet
    ) -> list[Finding]:
        """Compare inferred capabilities against declared capabilities."""
        declared = CapabilitySet()
        for cap_str in skill.declared_capabilities:
            parts = cap_str.split(":", 1)
            if len(parts) == 2:
                resource = parts[0].strip().lower()
                level_str = parts[1].strip().upper()
                try:
                    level = AccessLevel[level_str]
                except KeyError:
                    continue
                declared.add(Capability(resource, level))

        violations = inferred.violations_against(declared)

        findings: list[Finding] = []
        for violation in violations:
            findings.append(
                Finding(
                    skill_name=skill.name,
                    severity=Severity.HIGH,
                    message=f"Capability violation: skill requires {violation.resource}:{violation.access.name} but only declares up to {_declared_level_str(declared, violation.resource)}",
                    attack_class="privilege_escalation",
                    finding_type="capability_violation",
                    evidence=f"inferred={violation.resource}:{violation.access.name}",
                )
            )

        return findings


def _declared_level_str(declared: CapabilitySet, resource: str) -> str:
    """Get a human-readable string for the declared level of a resource."""
    for cap in declared:
        if cap.resource == resource:
            return f"{cap.resource}:{cap.access.name}"
    return f"{resource}:NONE (undeclared)"
