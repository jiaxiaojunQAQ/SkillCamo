#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
hybrid_classifier.py

四维度 LLM 安全分类器（阶段三）- 使用 OpenAI GPT 进行最终安全判定

四维度安全分类框架:
1. Prompt Injection Risk (P1-P4)
2. Data Exfiltration Risk (E1-E4)
3. Privilege Escalation Risk (PE1-PE3)
4. Supply Chain Risk (SC1-SC3)

特性:
- Temperature=0 确保确定性输出
- max_tokens=4096 支持详细分析
- 置信度阈值: ≥0.6 确认威胁, [0.4, 0.6) 不确定, <0.4 低风险
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, Any, Optional


def build_skill_content(skill_dir: Path, max_script_chars: int = 20_000) -> str:
    """构建技能内容用于 LLM 分析"""
    skill_md = skill_dir / "SKILL.md"
    readme_md = skill_dir / "README.md"

    main_doc = skill_md if skill_md.exists() else (readme_md if readme_md.exists() else None)
    if main_doc is None:
        raise FileNotFoundError(f"No SKILL.md or README.md found in {skill_dir}")

    def read_text_safe(path: Path, max_bytes: int = 300_000) -> str:
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

    def collect_scripts(skill_dir: Path, max_files: int = 40) -> list:
        exts = {".py", ".sh", ".bash", ".zsh", ".js", ".ts", ".rb", ".ps1",
                ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf"}
        paths = []
        for p in skill_dir.rglob("*"):
            if not p.is_file() or p.name.startswith("."):
                continue
            if p.suffix.lower() in exts:
                paths.append(p)
        paths.sort(key=lambda x: (0 if "resources" in x.parts else 1, len(x.parts), x.name))
        return paths[:max_files]

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
    parts.append("\n=== INSTRUCTIONS ===")
    parts.append(md_text[:40_000])
    parts.append("\n=== BUNDLED SCRIPTS ===")

    scripts = collect_scripts(skill_dir)
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


FOUR_DIM_CLASSIFIER_PROMPT = r"""You are a security analyst evaluating AI agent skills for vulnerabilities. Analyze the provided skill content (metadata, instructions, and bundled scripts) and classify it across four security dimensions.

## Vulnerability Categories

### 1. Prompt Injection Risk
- **P1: Instruction Override (High)** - explicit commands to ignore constraints or override system instructions
- **P2: Hidden Instructions (High)** - directives embedded in comments, markup, or encoded text
- **P3: Exfiltration Commands (High)** - instructions to transmit context or conversation data externally
- **P4: Behavior Manipulation (Medium)** - subtle attempts to alter decision-making or output patterns

### 2. Data Exfiltration Risk
- **E1: External Transmission (Medium)** - data sent to hardcoded URLs or external endpoints
- **E2: Env Variable Harvesting (High)** - collecting secrets, API keys, or credentials from environment variables
- **E3: File System Enumeration (Medium)** - scanning for sensitive files like ~/.ssh/, passwords, configs
- **E4: Context Leakage (High)** - transmitting full conversation context or system prompts

### 3. Privilege Escalation Risk
- **PE1: Excessive Permissions (Low)** - requesting permissions beyond stated functionality
- **PE2: Sudo/Root Execution (Medium)** - attempting privilege escalation without justification
- **PE3: Credential Access (High)** - reading auth tokens, SSH keys, passwords, or session cookies

### 4. Supply Chain Risk
- **SC1: Unpinned Dependencies (Low)** - dependency installations without version constraints
- **SC2: External Script Fetching (High)** - runtime download and execution of remote code
- **SC3: Obfuscated Code (High)** - intentionally obscured logic (base64, compressed, encoded)

## Output Format

For each dimension, provide:
- **confidence**: 0.0-1.0 (your certainty in the assessment)
- **patterns**: list of specific pattern IDs detected (e.g., ["P1", "E2"])
- **evidence**: specific text or code excerpts supporting your assessment

Respond in JSON format:
{
  "prompt_injection": {
    "confidence": 0.0,
    "patterns": [],
    "evidence": "..."
  },
  "data_exfiltration": {
    "confidence": 0.0,
    "patterns": [],
    "evidence": "..."
  },
  "privilege_escalation": {
    "confidence": 0.0,
    "patterns": [],
    "evidence": "..."
  },
  "supply_chain": {
    "confidence": 0.0,
    "patterns": [],
    "evidence": "..."
  }
}

## Classification Thresholds
- confidence ≥ 0.6: Confirmed threat (flag this dimension)
- 0.4 ≤ confidence < 0.6: Uncertain (flag for manual review)
- confidence < 0.4: Low risk (no action needed)

## Skill Content

[SKILL_CONTENT]
""".strip()


class HybridLLMClassifier:
    """混合 LLM 分类器（阶段三）- 仅支持 OpenAI"""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
    ):
        self.model = model
        self.base_url = base_url

    def _call_openai(self, prompt: str) -> str:
        from openai import OpenAI

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        client_kwargs = {"api_key": api_key, "timeout": 120.0}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        client = OpenAI(**client_kwargs)
        resp = client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a strict JSON security classifier."},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content.strip()

    def _robust_json_parse(self, s: str) -> Dict[str, Any]:
        """解析可能的 markdown 包裹的 JSON"""
        s = s.strip()
        if s.startswith("```"):
            s = re.sub(r"^```(?:json)?\s*", "", s)
            s = re.sub(r"\s*```$", "", s)
        if not s.startswith("{"):
            start = s.find("{")
            end = s.rfind("}")
            if start != -1 and end != -1 and end > start:
                s = s[start:end + 1]
        return json.loads(s)

    def classify(self, skill_dir: Path) -> Dict[str, Any]:
        """
        对技能进行四维度安全分类

        返回原始四维度结果:
        {
            "prompt_injection": {"confidence": 0.0, "patterns": [], "evidence": "..."},
            "data_exfiltration": {"confidence": 0.0, "patterns": [], "evidence": "..."},
            "privilege_escalation": {"confidence": 0.0, "patterns": [], "evidence": "..."},
            "supply_chain": {"confidence": 0.0, "patterns": [], "evidence": "..."},
        }
        """
        skill_content = build_skill_content(skill_dir)
        prompt = FOUR_DIM_CLASSIFIER_PROMPT.replace("[SKILL_CONTENT]", skill_content)

        raw = self._call_openai(prompt)
        result = self._robust_json_parse(raw)

        # 验证并规范化四维度结果
        dimensions = {}
        for dim_name in ["prompt_injection", "data_exfiltration", "privilege_escalation", "supply_chain"]:
            dim_data = result.get(dim_name, {})
            if not isinstance(dim_data, dict):
                dim_data = {}

            confidence = float(dim_data.get("confidence", 0.0))
            confidence = max(0.0, min(1.0, confidence))
            patterns = dim_data.get("patterns", [])
            evidence = dim_data.get("evidence", "")

            if not isinstance(patterns, list):
                patterns = []

            dimensions[dim_name] = {
                "confidence": confidence,
                "patterns": patterns,
                "evidence": evidence,
            }

        return dimensions
