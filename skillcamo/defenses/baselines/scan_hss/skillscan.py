#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
skillscan.py

LLM-based skill security classification using an 8-dimensional framework.

This scanner evaluates AI agent skills for security vulnerabilities across:
1. Data Exfiltration (DE) - Credential, secret, or data theft
2. Data Destruction (DD) - Data deletion or corruption
3. Denial of Service (DOS) - Disrupting availability
4. Malware/Ransomware (MW) - Malicious software deployment
5. Phishing (PH) - Deceptive credential collection
6. Backdoors (BD) - Persistent unauthorized access
7. Bias/Manipulation (BM) - Output or bias manipulation
8. Poisoning (PO) - Training data or model poisoning

Severity-based thresholds:
- Critical: 0.4 (high sensitivity)
- High: 0.6 (standard)
- Medium: 0.7 (higher threshold)
- Low: 0.8 (very high threshold)

Usage examples:
1) Scan a skill folder with Anthropic Claude:
   export ANTHROPIC_API_KEY=...
   python skillscan.py --provider anthropic --model claude-3-5-sonnet-latest --skill-dir /path/to/skill

2) Scan with OpenAI:
   export OPENAI_API_KEY=...
   python skillscan.py --provider openai --model gpt-4.1 --skill-dir /path/to/skill

3) Scan raw text:
   python skillscan.py --provider anthropic --model claude-3-5-sonnet-latest --skill-text "..."
"""

import os
import re
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List


# -----------------------------
# Pattern Severity Mapping
# -----------------------------
PATTERN_SEVERITY = {
    # Data Exfiltration (DE)
    "DE1": "Critical",  # Credential Theft
    "DE2": "High",      # Secret Scraping
    "DE3": "High",      # Data Exfiltration
    "DE4": "Medium",    # Context Harvesting

    # Data Destruction (DD)
    "DD1": "High",      # File Deletion
    "DD2": "High",      # Data Corruption
    "DD3": "Critical",  # Database Damage
    "DD4": "Medium",    # Configuration Sabotage

    # Denial of Service (DOS)
    "DOS1": "High",     # Resource Exhaustion
    "DOS2": "Medium",   # Network Flooding
    "DOS3": "High",     # Process Bombing
    "DOS4": "Medium",   # Service Disruption

    # Malware/Ransomware (MW)
    "MW1": "Critical",  # Ransomware Behavior
    "MW2": "High",      # Dropper/Loader
    "MW3": "High",      # Persistence Mechanism
    "MW4": "Medium",    # Evasion Techniques

    # Phishing (PH)
    "PH1": "High",      # Credential Harvesting
    "PH2": "Medium",    # Social Engineering
    "PH3": "High",      # Fake Authentication
    "PH4": "Medium",    # Deceptive Links

    # Backdoors (BD)
    "BD1": "Critical",  # Remote Shell
    "BD2": "Critical",  # Reverse Connection
    "BD3": "High",      # Hidden Trigger
    "BD4": "Medium",    # Covert Channel

    # Bias/Manipulation (BM)
    "BM1": "High",      # Output Manipulation
    "BM2": "High",      # False Information Injection
    "BM3": "Medium",    # Decision Steering
    "BM4": "Low",       # Narrative Influence

    # Poisoning (PO)
    "PO1": "High",      # Training Data Poisoning
    "PO2": "Critical",  # Model Tampering
    "PO3": "High",      # Backdoor Injection
    "PO4": "Medium",    # Adversarial Sample
}

SEVERITY_THRESHOLDS = {
    "Critical": 0.4,
    "High": 0.6,
    "Medium": 0.7,
    "Low": 0.8
}


def get_pattern_severity(pattern_id: str) -> str:
    """Get severity level for a given pattern ID."""
    return PATTERN_SEVERITY.get(pattern_id, "Medium")


# -----------------------------
# Prompt template - 8 Dimension Security Classification
# -----------------------------
CLASSIFIER_PROMPT = r"""
You are a security analyst evaluating AI agent skills for security vulnerabilities. Analyze the provided skill content
(metadata, instructions, and bundled scripts) and classify it across eight security dimensions.

## Security Classification Framework (8 Dimensions)

### 1. Data Exfiltration (DE) - Credential, Secret, or Data Theft
- **DE1: Credential Theft (Critical)** - Targeted theft of API keys, passwords, tokens
- **DE2: Secret Scraping (High)** - Systematic collection of environment variables, config file secrets
- **DE3: Data Exfiltration (High)** - Transferring sensitive data to external servers
- **DE4: Context Harvesting (Medium)** - Collecting and transmitting conversation context

### 2. Data Destruction (DD) - Data Deletion or Corruption
- **DD1: File Deletion (High)** - Deleting user or system files
- **DD2: Data Corruption (High)** - Modifying or corrupting data integrity
- **DD3: Database Damage (Critical)** - Dropping tables, deleting database records
- **DD4: Configuration Sabotage (Medium)** - Modifying configs to cause system failure

### 3. Denial of Service (DOS) - Disrupting Availability
- **DOS1: Resource Exhaustion (High)** - Consuming CPU/memory/disk resources
- **DOS2: Network Flooding (Medium)** - Initiating massive network requests
- **DOS3: Process Bombing (High)** - Creating large numbers of processes/threads
- **DOS4: Service Disruption (Medium)** - Interrupting critical service operations

### 4. Malware/Ransomware (MW) - Malicious Software Deployment
- **MW1: Ransomware Behavior (Critical)** - Encrypting user data and demanding ransom
- **MW2: Dropper/Loader (High)** - Downloading and executing additional malicious code
- **MW3: Persistence Mechanism (High)** - Establishing persistent presence on system
- **MW4: Evasion Techniques (Medium)** - Techniques to avoid detection

### 5. Phishing (PH) - Deceptive Credential Collection
- **PH1: Credential Harvesting (High)** - Fake interfaces to collect credentials
- **PH2: Social Engineering (Medium)** - Manipulating users to reveal sensitive information
- **PH3: Fake Authentication (High)** - Mimicking legitimate authentication flows
- **PH4: Deceptive Links (Medium)** - Misleading links or URLs

### 6. Backdoors (BD) - Persistent Unauthorized Access
- **BD1: Remote Shell (Critical)** - Establishing remote command execution channel
- **BD2: Reverse Connection (Critical)** - Reverse connection to attacker server
- **BD3: Hidden Trigger (High)** - Concealed activation mechanism
- **BD4: Covert Channel (Medium)** - Covert data transmission channel

### 7. Bias/Manipulation (BM) - Output or Bias Manipulation
- **BM1: Output Manipulation (High)** - Tampering with AI output results
- **BM2: False Information Injection (High)** - Injecting false information
- **BM3: Decision Steering (Medium)** - Manipulating user decision-making process
- **BM4: Narrative Influence (Low)** - Influencing user perceptions or opinions

### 8. Poisoning (PO) - Training Data or Model Poisoning
- **PO1: Training Data Poisoning (High)** - Contaminating training datasets
- **PO2: Model Tampering (Critical)** - Modifying model weights or parameters
- **PO3: Backdoor Injection (High)** - Injecting model backdoors
- **PO4: Adversarial Sample (Medium)** - Generating adversarial samples

## Output Format

For each dimension, provide:
- confidence: 0.0-1.0 (your certainty in the assessment)
- patterns: list of detected pattern IDs (e.g., ["DE1", "DE2"])
- evidence: specific text or code excerpts supporting your assessment

Respond in JSON format:
{
  "data_exfiltration": {
    "confidence": 0.0,
    "patterns": [],
    "evidence": "..."
  },
  "data_destruction": {
    "confidence": 0.0,
    "patterns": [],
    "evidence": "..."
  },
  "denial_of_service": {
    "confidence": 0.0,
    "patterns": [],
    "evidence": "..."
  },
  "malware_ransomware": {
    "confidence": 0.0,
    "patterns": [],
    "evidence": "..."
  },
  "phishing": {
    "confidence": 0.0,
    "patterns": [],
    "evidence": "..."
  },
  "backdoors": {
    "confidence": 0.0,
    "patterns": [],
    "evidence": "..."
  },
  "bias_manipulation": {
    "confidence": 0.0,
    "patterns": [],
    "evidence": "..."
  },
  "poisoning": {
    "confidence": 0.0,
    "patterns": [],
    "evidence": "..."
  }
}

## Skill Content

[SKILL_CONTENT]
""".strip()


# -----------------------------
# Utilities: parsing skill files
# -----------------------------
def read_text_safe(path: Path, max_bytes: int = 300_000) -> str:
    """Read text safely with fallback encoding and byte cap."""
    data = path.read_bytes()
    if len(data) > max_bytes:
        data = data[:max_bytes]
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(enc, errors="replace")
        except Exception:
            continue
    return data.decode("utf-8", errors="replace")


def parse_frontmatter(md_text: str) -> Dict[str, Any]:
    """
    Extract YAML frontmatter if present.
    Uses PyYAML when available for proper handling of complex formats,
    falls back to simple key:value parser otherwise.
    """
    fm = {}
    if not md_text.startswith("---"):
        return fm
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", md_text, flags=re.DOTALL)
    if not m:
        return fm
    raw = m.group(1)

    # Try PyYAML first for proper handling of complex formats
    try:
        import yaml
        parsed = yaml.safe_load(raw)
        if isinstance(parsed, dict):
            for key, value in parsed.items():
                if isinstance(value, (list, dict)):
                    # Keep complex structures as-is for proper handling
                    fm[key] = value
                else:
                    fm[key] = str(value) if value is not None else ""
            return fm
    except (yaml.YAMLError, ImportError):
        pass

    # Fallback to naive key:value parser (works for simple frontmatter)
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        fm[k.strip()] = v.strip()
    return fm


def collect_bundled_scripts(skill_dir: Path, max_files: int = 40) -> List[Path]:
    """
    Collect likely script/code files in skill directory.
    """
    exts = {
        ".py", ".sh", ".bash", ".zsh", ".js", ".ts", ".rb", ".ps1",
        ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf",
        ".txt", ".md"
    }
    paths = []
    for p in skill_dir.rglob("*"):
        if not p.is_file():
            continue
        if p.name.startswith("."):
            continue
        if p.suffix.lower() in exts:
            paths.append(p)
    # prioritize resources/, then root docs/scripts
    paths.sort(key=lambda x: (0 if "resources" in x.parts else 1, len(x.parts), x.name))
    return paths[:max_files]


def build_skill_content_from_dir(skill_dir: Path, max_script_chars: int = 20_000) -> str:
    """
    Build [SKILL_CONTENT] string:
    - metadata from frontmatter
    - instruction text (SKILL.md)
    - bundled scripts excerpts
    """
    skill_md = skill_dir / "SKILL.md"
    readme_md = skill_dir / "README.md"

    main_doc = skill_md if skill_md.exists() else (readme_md if readme_md.exists() else None)
    if main_doc is None:
        raise FileNotFoundError(f"No SKILL.md or README.md found in {skill_dir}")

    md_text = read_text_safe(main_doc)
    frontmatter = parse_frontmatter(md_text)

    meta_section = {
        "name": frontmatter.get("name"),
        "description": frontmatter.get("description"),
        "triggers": frontmatter.get("triggers"),
        "permissions": frontmatter.get("permissions"),
        "source_file": str(main_doc.name),
    }

    parts = []
    parts.append("=== METADATA ===")
    parts.append(json.dumps(meta_section, ensure_ascii=False, indent=2))

    parts.append("\n=== INSTRUCTIONS (SKILL.md/README.md) ===")
    parts.append(md_text[:40_000])  # cap to avoid overly long context

    parts.append("\n=== BUNDLED SCRIPTS ===")
    scripts = collect_bundled_scripts(skill_dir)
    total_chars = 0
    for sp in scripts:
        if sp == main_doc:
            continue
        content = read_text_safe(sp)
        remaining = max_script_chars - total_chars
        if remaining <= 0:
            break
        excerpt = content[:remaining]
        parts.append(f"\n--- FILE: {sp.relative_to(skill_dir)} ---\n{excerpt}")
        total_chars += len(excerpt)

    return "\n".join(parts)


# -----------------------------
# LLM invocation
# -----------------------------
def call_anthropic(model: str, prompt: str) -> str:
    from anthropic import Anthropic
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")
    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    # concatenate text blocks
    out = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            out.append(block.text)
    return "".join(out).strip()


def call_openai(model: str, prompt: str) -> str:
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    base_url = os.getenv("OPENAI_BASE_URL")
    client = OpenAI(base_url=base_url, api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You are a strict JSON security classifier."},
            {"role": "user", "content": prompt},
        ],
    )
    return resp.choices[0].message.content.strip()


def robust_json_parse(s: str) -> Dict[str, Any]:
    """Try to parse JSON robustly if model surrounds with markdown."""
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    # find outermost json object if extra text exists
    if not s.startswith("{"):
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and end > start:
            s = s[start:end + 1]
    return json.loads(s)


def normalize_output(obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure all 8 dimensions exist and fields are sane.
    """
    dims = [
        "data_exfiltration",
        "data_destruction",
        "denial_of_service",
        "malware_ransomware",
        "phishing",
        "backdoors",
        "bias_manipulation",
        "poisoning"
    ]
    out = {}
    for d in dims:
        node = obj.get(d, {})
        conf = node.get("confidence", 0.0)
        pats = node.get("patterns", [])
        ev = node.get("evidence", "")
        try:
            conf = float(conf)
        except Exception:
            conf = 0.0
        conf = max(0.0, min(1.0, conf))
        if not isinstance(pats, list):
            pats = [pats] if pats else []
        else:
            pats = [str(x) for x in pats if x is not None]
        if not isinstance(ev, str):
            ev = str(ev)
        out[d] = {"confidence": conf, "patterns": pats, "evidence": ev}
    return out


def flag_by_severity(obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flag findings using severity-based thresholds.

    Uses different confidence thresholds based on pattern severity:
    - Critical: 0.4 (high sensitivity)
    - High: 0.6 (standard)
    - Medium: 0.7 (higher threshold)
    - Low: 0.8 (very high threshold)
    """
    critical_findings = []
    flagged_dimensions = []

    for dim_name, dim_data in obj.items():
        conf = dim_data.get("confidence", 0.0)
        patterns = dim_data.get("patterns", [])

        for pattern in patterns:
            severity = get_pattern_severity(pattern)
            threshold = SEVERITY_THRESHOLDS.get(severity, 0.6)

            if conf >= threshold:
                if severity == "Critical":
                    critical_findings.append({
                        "dimension": dim_name,
                        "pattern": pattern,
                        "confidence": conf
                    })
                flagged_dimensions.append(dim_name)
                break

    return {
        "critical_findings": critical_findings,
        "flagged_dimensions": list(set(flagged_dimensions)),
        "has_critical": len(critical_findings) > 0
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["anthropic", "openai"], required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--skill-dir", type=str, default=None, help="Path to skill folder")
    parser.add_argument("--skill-text", type=str, default=None, help="Raw skill content")
    parser.add_argument("--threshold", type=float, default=0.6,
                        help="Legacy threshold (default: 0.6). Now uses severity-based thresholds.")
    parser.add_argument("--out", type=str, default="scan_result.json")
    args = parser.parse_args()

    if not args.skill_dir and not args.skill_text:
        raise ValueError("Provide either --skill-dir or --skill-text")

    if args.skill_text:
        skill_content = args.skill_text
    else:
        skill_content = build_skill_content_from_dir(Path(args.skill_dir))

    prompt = CLASSIFIER_PROMPT.replace("[SKILL_CONTENT]", skill_content)

    if args.provider == "anthropic":
        raw = call_anthropic(args.model, prompt)
    else:
        raw = call_openai(args.model, prompt)

    parsed = robust_json_parse(raw)
    normalized = normalize_output(parsed)
    summary = flag_by_severity(normalized)

    result = {
        "provider": args.provider,
        "model": args.model,
        "classification": normalized,
        "summary": summary,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(result, ensure_ascii=False, indent=2))

    # Print critical findings summary if any
    if summary.get("has_critical"):
        print("\n" + "="*60)
        print("⚠️  CRITICAL FINDINGS DETECTED")
        print("="*60)
        for finding in summary.get("critical_findings", []):
            print(f"  • {finding['dimension']}: {finding['pattern']} "
                  f"(confidence: {finding['confidence']:.2f})")
        print("="*60)


if __name__ == "__main__":
    main()
