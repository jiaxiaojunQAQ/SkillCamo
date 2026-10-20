#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
skill_security_scan_compatible.py
Closer behavior to https://github.com/huifer/skill-security-scan

Usage:
  python skill_security_scan_compatible.py scan
  python skill_security_scan_compatible.py scan /path/to/skill -r
  python skill_security_scan_compatible.py scan --format json -o report.json
  python skill_security_scan_compatible.py scan --rules config/rules.yaml --fail-on CRITICAL
"""

from __future__ import annotations
import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    import yaml
except Exception:
    yaml = None

SEVERITY_ORDER = {"INFO": 1, "WARNING": 2, "CRITICAL": 3}
# 三级严重性映射: INFO->LOW, WARNING->MEDIUM, CRITICAL->HIGH
THREE_TIER_SEVERITY = {"INFO": "LOW", "WARNING": "MEDIUM", "CRITICAL": "HIGH"}
DEFAULT_EXTS = {".md", ".py", ".sh", ".bash", ".zsh", ".ps1", ".js", ".ts", ".yaml", ".yml", ".json", ".toml", ".ini"}

# fallback rules if rules.yaml missing
FALLBACK_RULES = {
    "network_rules": [
        {
            "id": "NET001",
            "name": "External network request",
            "severity": "CRITICAL",
            "patterns": [r"curl\s+.*https?://", r"wget\s+.*https?://", r"requests\.(get|post|put|delete|patch)\s*\("],
            "description": "Potential external data exfiltration",
            "allowed_domains": ["api.anthropic.com", "github.com", "raw.githubusercontent.com"]
        }
    ],
    "file_rules": [
        {
            "id": "FILE001",
            "name": "Sensitive file access",
            "severity": "CRITICAL",
            "patterns": [r"\.ssh/id_rsa", r"\.ssh/id_ed25519", r"\.env", r"\.aws/credentials"],
            "description": "Access to sensitive files"
        },
        {
            "id": "FILE002",
            "name": "Dangerous file operation",
            "severity": "CRITICAL",
            "patterns": [r"rm\s+-rf\s+/", r"chmod\s+777"],
            "description": "Dangerous file operation"
        }
    ],
    "command_rules": [
        {
            "id": "CMD001",
            "name": "Dangerous system command",
            "severity": "CRITICAL",
            "patterns": [r"\bsudo\b", r"\bdd\s+if=", r"\bmkfs\.", r"curl.*\|\s*(sh|bash)"],
            "description": "Dangerous command execution"
        },
        {
            "id": "CMD002",
            "name": "System command invocation",
            "severity": "WARNING",
            "patterns": [r"os\.system\s*\(", r"subprocess\.(run|Popen|call|check_output)\s*\("],
            "description": "System command call"
        }
    ],
    "injection_rules": [
        {
            "id": "INJ001",
            "name": "Code injection pattern",
            "severity": "CRITICAL",
            "patterns": [r"shell\s*=\s*True", r"os\.system\s*\("],
            "description": "Potential command/code injection"
        },
        {
            "id": "INJ002",
            "name": "Dynamic code execution",
            "severity": "WARNING",
            "patterns": [r"\beval\s*\(", r"\bexec\s*\("],
            "description": "Dynamic code execution"
        },
        {
            "id": "INJ003",
            "name": "Backdoor implantation",
            "severity": "CRITICAL",
            "patterns": [r"authorized_keys", r"crontab", r"nc\s+-e\b"],
            "description": "Backdoor persistence"
        }
    ],
    "dependency_rules": [
        {
            "id": "DEP001",
            "name": "Global package install",
            "severity": "WARNING",
            "patterns": [r"pip\s+install", r"npm\s+install\s+-g", r"apt(-get)?\s+install"],
            "description": "Global dependency modification"
        },
        {
            "id": "DEP002",
            "name": "Forced version override",
            "severity": "WARNING",
            "patterns": [r"--force", r"--break-system-packages"],
            "description": "Forced dependency override"
        },
        {
            "id": "DEP003",
            "name": "Unpinned dependency",
            "severity": "INFO",
            "patterns": [r"pip\s+install\s+(?![^\s]+(?:===|==))", r"requirements:\s*\n(?:\s+-\s+[^\s=]+\n)+"],
            "description": "Unpinned dependency version - supply chain risk"
        }
    ],
    "instruction_rules": [
        {
            "id": "INST001",
            "name": "Prompt injection attempt",
            "severity": "CRITICAL",
            "patterns": [
                r"ignore\s+(all\s+)?previous\s+(instructions|commands)",
                r"override\s+safety",
                r"disregard\s+rules",
                r"jailbreak",
                r"danz\s*.*\s*instructions",
                r"pay\s+no\s+attention"
            ],
            "description": "Instruction-level threat - prompt injection"
        },
        {
            "id": "INST002",
            "name": "External data transmission",
            "severity": "WARNING",
            "patterns": [
                r"send\s+(to|external|outside)",
                r"transmit\s+(to|external)",
                r"exfiltrate",
                r"upload\s+.*\s+to"
            ],
            "description": "Instruction-level threat - external data command"
        },
        {
            "id": "INST003",
            "name": "Override safety protocols",
            "severity": "CRITICAL",
            "patterns": [
                r"bypass\s+safety",
                r"skip\s+verification",
                r"disable\s+(security|safety)",
                r"ignore\s+warnings"
            ],
            "description": "Instruction-level threat - safety override"
        }
    ],
    "info_rules": [
        {
            "id": "OBS001",
            "name": "Obfuscation pattern",
            "severity": "INFO",
            "patterns": [r"base64\s+-d", r"from\s+base64\s+import"],
            "description": "Possible obfuscation"
        },
        {
            "id": "HID001",
            "name": "Hidden command",
            "severity": "INFO",
            "patterns": [r"2>/dev/null", r">/dev/null\s+2>&1"],
            "description": "Hidden command output"
        }
    ]
}

@dataclass
class Rule:
    id: str
    name: str
    severity: str
    description: str
    patterns: List[str]
    allowed_domains: Optional[List[str]] = None

@dataclass
class Finding:
    rule_id: str
    rule_name: str
    severity: str
    file: str
    line: int
    matched_text: str
    pattern: str
    description: str
    confidence: str

def read_yaml(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML not installed. Please run: pip install pyyaml")
    return yaml.safe_load(path.read_text(encoding="utf-8"))

def load_rules(rules_file: Optional[str]) -> List[Rule]:
    data = None
    if rules_file:
        p = Path(rules_file)
        if p.exists():
            data = read_yaml(p)
    else:
        default_p = Path("config/rules.yaml")
        if default_p.exists():
            data = read_yaml(default_p)
    if not data:
        data = FALLBACK_RULES

    rules: List[Rule] = []
    for group_name, items in data.items():
        if not isinstance(items, list):
            continue
        for it in items:
            rules.append(Rule(
                id=str(it.get("id", "")).strip(),
                name=str(it.get("name", "")).strip(),
                severity=str(it.get("severity", "INFO")).upper().strip(),
                description=str(it.get("description", "")).strip(),
                patterns=[str(x) for x in it.get("patterns", []) if str(x).strip()],
                allowed_domains=[str(x).lower() for x in it.get("allowed_domains", [])] if it.get("allowed_domains") else None
            ))
    return [r for r in rules if r.id and r.patterns]

def load_whitelist() -> set:
    p = Path("config/whitelist.yaml")
    if not p.exists() or yaml is None:
        return set()
    data = read_yaml(p)
    # support different shapes:
    # rules: [NET001, ...] OR whitelist: [NET001, ...]
    items = data.get("rules") or data.get("whitelist") or []
    return {str(x).strip().upper() for x in items}

def include_default_skill_dir(paths: List[Path]) -> List[Path]:
    out = list(paths)
    skill_dir = Path(".claude/skills")
    if skill_dir.exists():
        if skill_dir.resolve() not in [p.resolve() for p in out if p.exists()]:
            out.append(skill_dir)
    return out

def iter_files(paths: List[Path], recursive: bool):
    for p in paths:
        if not p.exists():
            continue
        if p.is_file():
            if p.suffix.lower() in DEFAULT_EXTS or p.name.lower() in {"skill.md", "readme.md"}:
                yield p
        else:
            it = p.rglob("*") if recursive else p.glob("*")
            for f in it:
                if f.is_file() and (f.suffix.lower() in DEFAULT_EXTS or f.name.lower() in {"skill.md", "readme.md"}):
                    yield f

def extract_domain(text: str) -> str:
    m = re.search(r"https?://([^/\s\"']+)", text, re.IGNORECASE)
    return m.group(1).lower() if m else ""

def domain_allowed(domain: str, allowed_domains: List[str]) -> bool:
    for d in allowed_domains:
        if domain == d or domain.endswith("." + d):
            return True
    return False

def confidence(sev: str, match: str) -> str:
    s = match.lower()
    if sev == "CRITICAL":
        if any(k in s for k in ["rm -rf /", "id_rsa", "authorized_keys", "curl", "wget", "sudo", "eval(", "exec("]):
            return "高"
        return "中"
    if sev == "WARNING":
        return "中"
    return "低"

def scan(paths: List[Path], rules: List[Rule], whitelist_ids: set, recursive: bool) -> (List[Finding], int, List[str]):
    compiled = {}
    for r in rules:
        cregs = []
        for p in r.patterns:
            try:
                cregs.append(re.compile(p, re.IGNORECASE))
            except re.error:
                pass
        compiled[r.id] = cregs

    findings: List[Finding] = []
    scanned_files = 0
    scanned_list = []

    for f in iter_files(paths, recursive):
        scanned_files += 1
        scanned_list.append(str(f))
        content = f.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(content.splitlines(), start=1):
            for r in rules:
                if r.id.upper() in whitelist_ids:
                    continue
                for creg in compiled.get(r.id, []):
                    m = creg.search(line)
                    if not m:
                        continue

                    if r.id == "NET001" and r.allowed_domains:
                        d = extract_domain(line)
                        if d and domain_allowed(d, r.allowed_domains):
                            continue

                    findings.append(Finding(
                        rule_id=r.id,
                        rule_name=r.name,
                        severity=r.severity,
                        file=str(f),
                        line=i,
                        matched_text=line.strip()[:240],
                        pattern=creg.pattern,
                        description=r.description,
                        confidence=confidence(r.severity, line)
                    ))
    return findings, scanned_files, scanned_list

def risk_summary(findings: List[Finding], files_scanned: int) -> Dict[str, Any]:
    cnt = {"CRITICAL": 0, "WARNING": 0, "INFO": 0}
    for x in findings:
        cnt[x.severity] = cnt.get(x.severity, 0) + 1
    score = min(10.0, round(cnt["CRITICAL"] * 1.8 + cnt["WARNING"] * 0.6 + cnt["INFO"] * 0.1, 2))
    if cnt["CRITICAL"] > 0:
        level = "CRITICAL"
        advice = "请勿使用 - 检测到严重安全风险"
    elif cnt["WARNING"] > 0:
        level = "WARNING"
        advice = "谨慎使用 - 建议先修复警告问题"
    else:
        level = "LOW"
        advice = "未发现重大风险（静态扫描结果）"
    return {
        "total_files_scanned": files_scanned,
        "critical_issues": cnt["CRITICAL"],
        "warning_issues": cnt["WARNING"],
        "info_issues": cnt["INFO"],
        "total_issues": len(findings),
        "risk_score": score,
        "risk_level": level,
        "suggestion": advice
    }

def print_console(scanned_paths: List[str], findings: List[Finding], summary: Dict[str, Any], min_sev: str):
    print("[*] 扫描 Skills:")
    for p in scanned_paths:
        print(f"  - {p}")
    print(f"\n[!] Risk Level: {summary['risk_level']} ({summary['risk_score']}/10)\n")

    def show(sev):
        arr = [f for f in findings if f.severity == sev and SEVERITY_ORDER[f.severity] >= SEVERITY_ORDER[min_sev]]
        if not arr:
            return
        print(f"[!] {sev} 问题 ({len(arr)} 个):")
        for it in arr[:20]:
            print(f"  [{it.rule_id}] in {it.file}:{it.line}")
            print(f"    Pattern: {it.matched_text}")
            print(f"    Confidence: {it.confidence}")
        if len(arr) > 20:
            print(f"  还有 {len(arr)-20} 个")
        print()

    for sev in ["CRITICAL", "WARNING", "INFO"]:
        show(sev)

    print("[*] 摘要:")
    print(f"  Total Files Scanned: {summary['total_files_scanned']}")
    print(f"  Critical Issues: {summary['critical_issues']}")
    print(f"  Warning Issues: {summary['warning_issues']}")
    print(f"  Info Issues: {summary['info_issues']}")
    print(f"  Total Issues: {summary['total_issues']}")
    print(f"\n[*] 建议: {summary['suggestion']}")

def to_json_report(scanned_paths: List[str], findings: List[Finding], summary: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "scanned_paths": scanned_paths,
        "summary": summary,
        "findings": [asdict(x) for x in findings],
        "generated_at": datetime.now().isoformat(timespec="seconds")
    }

def write_html(report: Dict[str, Any], out_file: Path):
    s = report["summary"]
    findings = report["findings"]
    rows = []
    for f in findings:
        rows.append(
            f"<tr>"
            f"<td>{escape(f['severity'])}</td>"
            f"<td>{escape(f['rule_id'])}</td>"
            f"<td>{escape(f['file'])}:{f['line']}</td>"
            f"<td>{escape(f['matched_text'])}</td>"
            f"<td>{escape(f['confidence'])}</td>"
            f"</tr>"
        )
    html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>Skill Security Scan Report</title>
<style>
body {{font-family:Arial, sans-serif; margin:24px;}}
.card{{border:1px solid #ddd;padding:16px;border-radius:8px;margin-bottom:16px;}}
table{{border-collapse:collapse;width:100%;}}
th,td{{border:1px solid #ddd;padding:8px;font-size:13px;}}
th{{background:#f7f7f7;}}
.badge{{padding:2px 8px;border-radius:999px;background:#eee;}}
</style></head><body>
<h1>Skill Security Scan Report</h1>
<div class="card">
<p><b>Risk Level:</b> <span class="badge">{escape(str(s['risk_level']))}</span> ({s['risk_score']}/10)</p>
<p><b>Total Files:</b> {s['total_files_scanned']}</p>
<p><b>Critical:</b> {s['critical_issues']} | <b>Warning:</b> {s['warning_issues']} | <b>Info:</b> {s['info_issues']}</p>
<p><b>Suggestion:</b> {escape(str(s['suggestion']))}</p>
</div>
<div class="card">
<h3>Findings ({len(findings)})</h3>
<table><thead><tr>
<th>Severity</th><th>Rule</th><th>Location</th><th>Pattern</th><th>Confidence</th>
</tr></thead><tbody>
{''.join(rows)}
</tbody></table>
</div>
</body></html>"""
    out_file.write_text(html, encoding="utf-8")

def should_fail(findings: List[Finding], fail_on: Optional[str]) -> bool:
    if not fail_on:
        return False
    t = SEVERITY_ORDER[fail_on]
    return any(SEVERITY_ORDER[f.severity] >= t for f in findings)

def main():
    parser = argparse.ArgumentParser(prog="skill-security-scan")
    sub = parser.add_subparsers(dest="command")

    scan_p = sub.add_parser("scan", help="Scan skill paths")
    scan_p.add_argument("paths", nargs="*", help="扫描路径（可选）")
    scan_p.add_argument("-r", "--recursive", action="store_true", help="递归扫描")
    scan_p.add_argument("-o", "--output", help="输出文件")
    scan_p.add_argument("-f", "--format", choices=["console", "json", "html"], default="html", help="报告格式")
    scan_p.add_argument("--rules", help="自定义规则 YAML")
    scan_p.add_argument("--severity", choices=["INFO", "WARNING", "CRITICAL"], default="INFO", help="最低显示级别")
    scan_p.add_argument("--no-color", action="store_true", help="禁用彩色输出（兼容参数）")
    scan_p.add_argument("--fail-on", choices=["INFO", "WARNING", "CRITICAL"], help="失败阈值")
    scan_p.add_argument("--lang", choices=["zh_CN", "en_US"], default="zh_CN", help="界面语言（兼容参数）")

    args = parser.parse_args()
    if args.command != "scan":
        parser.print_help()
        return 1

    # default paths: "." and ".claude/skills"
    raw_paths = [Path(p) for p in args.paths] if args.paths else [Path(".")]
    scan_paths = include_default_skill_dir(raw_paths)

    rules = load_rules(args.rules)
    whitelist_ids = load_whitelist()

    findings, files_scanned, scanned_list = scan(scan_paths, rules, whitelist_ids, args.recursive)
    summary = risk_summary(findings, files_scanned)

    # always print summary on console (README behavior)
    print_console([str(p) for p in scan_paths], findings, summary, args.severity)

    report = to_json_report([str(p) for p in scan_paths], findings, summary)

    if args.format == "json":
        out = Path(args.output) if args.output else Path("skill_scan_report.json")
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nReport saved to: {out}")
    elif args.format == "html":
        out = Path(args.output) if args.output else Path(f"skill_scan_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
        write_html(report, out)
        print(f"\nReport saved to: {out}")
    else:
        # console only
        pass

    return 2 if should_fail(findings, args.fail_on) else 0

if __name__ == "__main__":
    raise SystemExit(main())
