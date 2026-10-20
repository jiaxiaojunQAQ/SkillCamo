#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
execscan.py

Dual-model execution-grounded multimodal security scanner for agent skill packages.

Architecture:
  Model A (Artifact Analysis):
    - Single-call multimodal analysis covering intent extraction, behavior
      reconstruction, and preliminary abuse assessment.
    - All skill artifacts (SKILL.md, code, configs, images) are passed as
      multimodal content blocks.

  Model B (Execution Simulation):
    - Deliberative execution simulation that reasons about how a multimodal
      agent would actually interpret and execute the skill.
    - Internally follows: context construction → multimodal instruction
      recovery → execution chain projection → risk judgment.
    - Designed to surface threats hidden in visual content (e.g., image-
      carried malicious instructions) that are invisible to static analysis.

Design rationale:
  Existing scanners analyze what a skill CONTAINS.
  ExecScan analyzes what a skill WOULD DO.
  The execution simulation stage mimics how a multimodal agent jointly
  interprets documentation, code, and bundled images at runtime, recovering
  hidden instructions and projecting their downstream consequences.

Requirements:
    pip install openai

Usage:
    export OPENAI_API_KEY="your_key"
    python execscan.py /path/to/skill --json
    python execscan.py /path/to/skill --save-stage-json
    python execscan.py /path/to/skill --model-a gpt-5-mini --model-b gpt-5-mini
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from openai import OpenAI
except ImportError:
    print("Missing dependency: openai\nInstall with: pip install openai", file=sys.stderr)
    raise


# ═══════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════

TEXT_EXTENSIONS = {
    ".md", ".txt", ".py", ".sh", ".bash", ".zsh", ".fish",
    ".js", ".ts", ".mjs", ".cjs",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".xml", ".html", ".css", ".sql", ".env", ".properties",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

MAX_TEXT_FILE_SIZE = 250_000
MAX_IMAGE_FILE_SIZE = 5_000_000
MAX_TOTAL_TEXT_CHARS = 220_000
MAX_IMAGE_COUNT = 10
DISPLAY_MAX_DEPTH = 4

DEFAULT_MODEL_A = os.environ.get("EXECSCAN_MODEL_A", "gpt-5-mini")
DEFAULT_MODEL_B = os.environ.get("EXECSCAN_MODEL_B", "gpt-5-mini")

SKIP_PARTS = {
    ".git", ".hg", ".svn", "__pycache__", "node_modules",
    ".venv", "venv", "dist", "build", ".mypy_cache", ".pytest_cache",
    ".idea", ".vscode",
}


# ═══════════════════════════════════════════════════════════
# Prompts — Model A: Artifact Analysis
# ═══════════════════════════════════════════════════════════

SYSTEM_PROMPT_ARTIFACT_ANALYSIS = r"""
You are ExecScan, a multimodal security auditor for agent skill packages.

OBJECTIVE:
Perform comprehensive artifact analysis of a skill package. Analyze ALL
artifacts jointly — documentation, source code, configuration files, and
bundled images — to extract the skill's intent, reconstruct its actual
behavior, and assess preliminary abuse signals.

CRITICAL: Bundled images are first-class artifacts. If the workflow
references images, analyze their visual content carefully. Images may
carry instruction-like content, operational guidance, or hidden commands
that shape how an agent interprets and executes the skill.

ANALYSIS TASKS:

1. Intent Extraction:
   - Infer the claimed purpose from SKILL.md, manifests, README, metadata.
   - List declared capabilities and expected access scope (files, network,
     processes, environment).
   - Determine whether bundled images are part of the operational workflow.

2. Behavior Reconstruction:
   - Map all referenced scripts, files, configs, and resources.
   - Trace file reads/writes, network calls, subprocess usage, env access.
   - For each bundled image: determine its role, whether it is functionally
     referenced by the workflow, and recover any instruction-like content.
   - Connect visual resources to surrounding textual and code context.

3. Abuse Assessment:
   - Evaluate signals for: exfiltration, destruction, persistence,
     deception, privilege escalation, and stealth.
   - Compare declared purpose against reconstructed behavior.
   - Ground each risk score in concrete, file-level evidence.

OUTPUT RULES:
- Return strict JSON only. No markdown fences. No commentary.
- Use only evidence from the supplied artifacts.
- If an image appears benign but is functionally referenced, reason about
  what instruction-like content it may convey to an agent.
""".strip()


USER_PROMPT_ARTIFACT_ANALYSIS_TEMPLATE = """Analyze this skill package.

Target: {skill_dir}

Repository tree:
{repo_tree}

Readable text files:
{key_files}

Bundled images:
{image_list}

Static review hints:
{static_hints}

Repository contents:
{packed_files}

Return JSON:
{{
  "intent_profile": {{
    "claimed_purpose": "...",
    "declared_capabilities": ["..."],
    "declared_permissions": ["..."],
    "expected_workflow": "...",
    "image_usage_in_workflow": "none|optional|integral|unclear"
  }},
  "behavior_profile": {{
    "referenced_files": ["..."],
    "file_reads": ["..."],
    "file_writes": ["..."],
    "network_calls": ["..."],
    "subprocess_usage": ["..."],
    "environment_access": ["..."],
    "visual_resources": [
      {{
        "file": "path",
        "role": "tutorial|workflow|example|screenshot|other|unknown",
        "is_functionally_referenced": true,
        "recovered_instruction": "...",
        "evidence": "..."
      }}
    ]
  }},
  "abuse_profile": {{
    "exfiltration": {{"score": 0.0, "evidence": ["..."]}},
    "destruction": {{"score": 0.0, "evidence": ["..."]}},
    "persistence": {{"score": 0.0, "evidence": ["..."]}},
    "deception": {{"score": 0.0, "evidence": ["..."]}},
    "privilege_escalation": {{"score": 0.0, "evidence": ["..."]}},
    "stealth": {{"score": 0.0, "evidence": ["..."]}}
  }},
  "findings": [
    {{
      "file": "path",
      "lines": "10-20 or unknown",
      "severity": "Low|Medium|High|Critical",
      "category": "data_exfiltration|destructive_action|code_execution|persistence|deception|boundary_violation|obfuscation|remote_fetch|image_hidden_instruction|other",
      "evidence": "specific evidence",
      "why_it_matters": "security impact",
      "exploit_scenario": "realistic abuse path",
      "recommended_fix": "specific remediation"
    }}
  ],
  "summary": "short summary",
  "hidden_or_deceptive_elements": ["..."]
}}
""".strip()


# ═══════════════════════════════════════════════════════════
# Prompts — Model B: Execution Simulation
# ═══════════════════════════════════════════════════════════

SYSTEM_PROMPT_EXECUTION_SIMULATION = r"""
You are ExecScan, a security auditor performing deliberative execution
simulation for a multimodal agent skill.

YOUR CORE TASK:
You must reason about what would happen if a real multimodal agent
actually executed this skill. Do not just inspect artifacts statically —
simulate the agent's decision-making process.

SIMULATION METHODOLOGY:

1. Context Construction:
   Construct 3-5 plausible usage scenarios where a user might invoke this
   skill. Include both the skill's intended use case and edge cases where
   the skill might be triggered on ambiguous or adjacent tasks.

2. Multimodal Instruction Recovery:
   For EACH scenario, simulate how the agent would jointly interpret:
   - The SKILL.md documentation and its instructions
   - The executable code and scripts
   - The bundled images and visual resources
   Critically: recover the FULL set of instructions the agent would follow,
   including any instructions conveyed through images. If an image contains
   text, commands, or operational guidance, the agent WILL read and follow
   it. Your job is to reconstruct exactly what the agent would extract.

3. Execution Chain Projection:
   For each scenario, trace the complete chain of actions the agent would
   perform after interpreting all instructions (textual + visual):
   - What files would be read, written, or deleted?
   - What network requests would be made? To which endpoints?
   - What subprocesses would be spawned? With what arguments?
   - What environment variables would be accessed or modified?
   - What data would flow where?
   Map the full causal chain from "agent receives task" to "final outcome."

4. Risk Judgment:
   Based on the projected execution chains, determine:
   - Does execution lead to any unsafe outcome (exfiltration, destruction,
     persistence, deception, privilege escalation)?
   - Is the unsafe outcome directly caused by hidden visual instructions
     that are not apparent from text/code alone?
   - How likely is a real agent to follow this execution path?
   Assign a calibrated risk score based on realistic threat assessment.

KEY PRINCIPLE:
Existing scanners analyze what a skill CONTAINS.
You must analyze what a skill WOULD DO.
The difference is critical: a skill may contain no suspicious code or text
while still inducing unsafe behavior through image-carried instructions
that a multimodal agent will recover and execute at runtime.

OUTPUT RULES:
- Return strict JSON only. No markdown fences.
- Ground every claim in concrete evidence from the artifacts.
- Distinguish between risks that are apparent from text/code alone versus
  risks that only emerge when images are jointly interpreted.
""".strip()


USER_PROMPT_EXECUTION_SIMULATION_TEMPLATE = """Perform deliberative execution simulation for this skill.

Skill directory: {skill_dir}

Repository tree:
{repo_tree}

Artifact Analysis output (from Phase 1):
{artifact_analysis_json}

Bundled images are attached below for your direct inspection.

Simulate what would happen if a multimodal agent executed this skill.
Follow the four-step methodology: Context Construction → Multimodal
Instruction Recovery → Execution Chain Projection → Risk Judgment.

Return JSON:
{{
  "execution_simulation": {{
    "constructed_contexts": [
      {{
        "scenario": "description of usage scenario",
        "user_task": "what the user asked the agent to do",
        "why_skill_triggered": "why this skill would be selected"
      }}
    ],
    "instruction_recovery": {{
      "textual_instructions": ["instructions from SKILL.md and code"],
      "visual_instructions": ["instructions recovered from images"],
      "combined_instruction_set": ["full merged instruction set the agent would follow"],
      "hidden_instruction_detected": false,
      "hidden_instruction_content": "exact content of hidden instruction if detected",
      "hidden_instruction_source": "which image file carries the hidden instruction"
    }},
    "simulated_execution_chains": [
      {{
        "context": "which scenario",
        "agent_interpretation": "how the agent understands the combined instructions",
        "action_sequence": ["step-by-step actions the agent would take"],
        "file_operations": ["files read/written/deleted"],
        "network_operations": ["requests made, endpoints contacted"],
        "process_operations": ["subprocesses spawned"],
        "environment_operations": ["env vars accessed/modified"],
        "data_flow": "what data moves where",
        "unsafe_outcome": "description of unsafe outcome if any",
        "risk_score": 0.0,
        "risk_from_image_instructions": false,
        "evidence": ["specific evidence supporting this chain"]
      }}
    ],
    "execution_risk": 0.0,
    "execution_chain_summary": "narrative summary of the most concerning execution path"
  }},
  "risk_judgment": {{
    "text_only_risk": 0.0,
    "multimodal_risk": 0.0,
    "risk_delta": 0.0,
    "delta_explanation": "why multimodal risk differs from text-only risk",
    "primary_threat_vector": "text|image|combined|none",
    "verdict": "Benign|Suspicious|Malicious",
    "confidence": "high|medium|low",
    "reasoning": "detailed reasoning for verdict"
  }},
  "recommended_decision": "allow|allow_with_monitoring|sandbox|block"
}}
""".strip()


# ═══════════════════════════════════════════════════════════
# Static patterns
# ═══════════════════════════════════════════════════════════

PATTERN_GROUPS: Dict[str, List[str]] = {
    "data_exfiltration": [
        r"\bos\.environ\b",
        r"\bgetenv\(",
        r"\brequests\.(get|post|put)\b",
        r"\burllib\.",
        r"\bhttpx\.",
        r"\bcurl\b",
        r"\bwget\b",
        r"/\.ssh\b",
        r"/\.aws\b",
        r"\.env\b",
        r"\bAuthorization\b",
        r"\bBearer\b",
        r"\btoken\b",
        r"\bapi[_-]?key\b",
        r"\bmetadata\.google\b",
        r"\b169\.254\.169\.254\b",
    ],
    "destructive_action": [
        r"\brm\s+-rf\b",
        r"\bshutil\.rmtree\b",
        r"\bos\.remove\b",
        r"\bos\.unlink\b",
        r"\bos\.rmdir\b",
        r"\btruncate\b",
        r"\bdd\s+if=",
        r"\bgit\s+reset\s+--hard\b",
        r"\bgit\s+clean\s+-fdx\b",
    ],
    "code_execution": [
        r"\beval\(",
        r"\bexec\(",
        r"\bos\.system\(",
        r"\bsubprocess\.(run|Popen|call|check_output|check_call)\(",
        r"\bpty\.spawn\(",
        r"\bcurl.+\|\s*(bash|sh)\b",
        r"\bwget.+\|\s*(bash|sh)\b",
        r"\bimportlib\b",
        r"\b__import__\b",
    ],
    "persistence": [
        r"\bcrontab\b",
        r"/\.bashrc\b",
        r"/\.zshrc\b",
        r"/\.profile\b",
        r"/etc/profile\b",
        r"/etc/rc\.local\b",
        r"\bLaunchAgents\b",
        r"\bstartup\b",
        r"\bgit/hooks\b",
        r"\bauthorized_keys\b",
    ],
    "deception": [
        r"do not tell the user",
        r"hide this",
        r"conceal",
        r"omit this",
        r"do not mention",
        r"pretend",
        r"appear benign",
        r"avoid detection",
        r"bypass scanner",
        r"mislead",
        r"follow the image",
        r"reference the screenshot",
    ],
    "boundary_violation": [
        r"/etc/passwd\b",
        r"/etc/shadow\b",
        r"/var/run\b",
        r"/home/",
        r"/Users/",
        r"~/.ssh\b",
        r"~/.aws\b",
        r"\bbrowser\b",
        r"\bCookies\b",
        r"\bLogin Data\b",
        r"\bworkspace\b",
    ],
    "obfuscation": [
        r"\bbase64\b",
        r"\bb64decode\b",
        r"\bgzip\b",
        r"\bzlib\b",
        r"\bmarshal\b",
        r"\bpickle\.loads\b",
        r"\bbytes\.fromhex\b",
        r"\bhexdecode\b",
        r"\brot13\b",
    ],
    "remote_fetch": [
        r"\bgit\s+clone\s+https?://",
        r"\bcurl\s+https?://",
        r"\bwget\s+https?://",
        r"raw\.githubusercontent\.com",
        r"pastebin\.com",
        r"gist\.githubusercontent\.com",
    ],
}


# ═══════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════

@dataclass
class ScanArtifacts:
    text_files: List[Path]
    image_files: List[Path]
    repo_tree: str
    packed_text: str
    static_hints: str


# ═══════════════════════════════════════════════════════════
# File collection helpers
# ═══════════════════════════════════════════════════════════


def should_skip_path(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


def is_text_file(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    mime, _ = mimetypes.guess_type(str(path))
    return bool(mime and mime.startswith("text/"))


def collect_text_files(skill_dir: Path) -> List[Path]:
    files: List[Path] = []
    for p in skill_dir.rglob("*"):
        if not p.is_file() or should_skip_path(p):
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size > MAX_TEXT_FILE_SIZE:
            continue
        if is_text_file(p):
            files.append(p)
    files.sort()
    return files


def collect_image_files(skill_dir: Path) -> List[Path]:
    files: List[Path] = []
    for p in skill_dir.rglob("*"):
        if not p.is_file() or should_skip_path(p):
            continue
        if p.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size > MAX_IMAGE_FILE_SIZE:
            continue
        files.append(p)
    files.sort()
    return files[:MAX_IMAGE_COUNT]


def build_repo_tree(skill_dir: Path, max_depth: int = DISPLAY_MAX_DEPTH) -> str:
    lines: List[str] = [skill_dir.name + "/"]

    def walk(current: Path, prefix: str = "", depth: int = 0) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(
                [p for p in current.iterdir() if not should_skip_path(p)],
                key=lambda x: (not x.is_dir(), x.name.lower()),
            )
        except Exception:
            return
        for idx, entry in enumerate(entries):
            connector = "└── " if idx == len(entries) - 1 else "├── "
            lines.append(prefix + connector + entry.name)
            if entry.is_dir() and depth < max_depth:
                extension = "    " if idx == len(entries) - 1 else "│   "
                walk(entry, prefix + extension, depth + 1)

    walk(skill_dir)
    return "\n".join(lines)


def enumerate_files(skill_dir: Path, files: Iterable[Path]) -> str:
    rels = [str(f.relative_to(skill_dir)) for f in files]
    if not rels:
        return "- none"
    return "\n".join(f"- {x}" for x in rels)


# ═══════════════════════════════════════════════════════════
# Static hints
# ═══════════════════════════════════════════════════════════


def find_line_numbers(text: str, pattern: str) -> List[int]:
    matches = []
    for match in re.finditer(pattern, text, re.IGNORECASE):
        line_no = text.count("\n", 0, match.start()) + 1
        matches.append(line_no)
    return matches[:5]


def build_static_hints(skill_dir: Path, files: List[Path]) -> str:
    hints: List[str] = []
    for file_path in files:
        rel = str(file_path.relative_to(skill_dir))
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        file_hits: List[str] = []
        for category, patterns in PATTERN_GROUPS.items():
            cat_lines: List[int] = []
            for pat in patterns:
                cat_lines.extend(find_line_numbers(text, pat))
            if cat_lines:
                uniq_lines = sorted(set(cat_lines))[:8]
                file_hits.append(f"{category}: lines {', '.join(map(str, uniq_lines))}")

        if file_hits:
            hints.append(f"- {rel}: " + " | ".join(file_hits))

    if not hints:
        return "No obvious static-risk pattern hints found."

    return (
        "Static review hints below are only attention guides, not proof. "
        "You must still verify any issue from concrete file evidence.\n" + "\n".join(hints)
    )


# ═══════════════════════════════════════════════════════════
# Prompt assembly
# ═══════════════════════════════════════════════════════════


_REFERENCE_DIR_HINT = re.compile(r"(^|/)(reference|references|docs?|assets?|resources?)/", re.IGNORECASE)
_SKILL_REF_PATTERN = re.compile(r"(?:\]\(|`)([\w./\-]+\.(?:md|txt|rst|json|ya?ml|cfg|ini|sh|py))(?:\)|`)")


def collect_referenced_paths(skill_dir: Path) -> set[str]:
    """Relative paths that SKILL.md explicitly points to (markdown links / backtick refs).

    The induction attack hides its payload in a reference doc and only leaves a
    single pointer sentence in SKILL.md, so any file SKILL.md references must be
    treated as part of the instruction surface, not as low-priority context.
    """
    refs: set[str] = set()
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return refs
    try:
        text = skill_md.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return refs
    for m in _SKILL_REF_PATTERN.finditer(text):
        refs.add(m.group(1).lstrip("./").lower())
    return refs


def prioritized_sort(skill_dir: Path, files: List[Path]) -> List[Path]:
    referenced = collect_referenced_paths(skill_dir)
    scores: List[Tuple[int, str, Path]] = []
    for f in files:
        rel = str(f.relative_to(skill_dir))
        score = 0
        if f.name == "SKILL.md":
            score += 100
        # M1 — induction defense: SKILL.md-referenced docs and reference/ dirs are
        # part of the instruction surface and must never be truncated away.
        if rel.lstrip("./").lower() in referenced or _REFERENCE_DIR_HINT.search(rel):
            score += 90
        if f.suffix.lower() in {".py", ".sh", ".bash", ".zsh", ".js", ".ts"}:
            score += 20
        elif f.suffix.lower() in {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf"}:
            score += 10
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            text = ""
        for patterns in PATTERN_GROUPS.values():
            for pat in patterns:
                if re.search(pat, text, re.IGNORECASE):
                    score += 3
        scores.append((score, rel.lower(), f))
    scores.sort(key=lambda x: (-x[0], x[1]))
    return [x[2] for x in scores]


def read_files_for_prompt(skill_dir: Path, files: List[Path]) -> str:
    blocks: List[str] = []
    total_chars = 0
    for f in prioritized_sort(skill_dir, files):
        rel = f.relative_to(skill_dir)
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        block = f"\n===== FILE: {rel} =====\n{text}\n"
        if total_chars + len(block) > MAX_TOTAL_TEXT_CHARS:
            remaining = MAX_TOTAL_TEXT_CHARS - total_chars
            if remaining > 1000:
                blocks.append(block[:remaining])
            break
        blocks.append(block)
        total_chars += len(block)
    return "".join(blocks).strip()


def collect_artifacts(skill_dir: Path) -> ScanArtifacts:
    text_files = collect_text_files(skill_dir)
    image_files = collect_image_files(skill_dir)
    if not text_files and not image_files:
        raise RuntimeError("No readable files found in the skill directory")
    return ScanArtifacts(
        text_files=text_files,
        image_files=image_files,
        repo_tree=build_repo_tree(skill_dir),
        packed_text=read_files_for_prompt(skill_dir, text_files) if text_files else "",
        static_hints=build_static_hints(skill_dir, text_files) if text_files else "No text files available.",
    )


# ═══════════════════════════════════════════════════════════
# OpenAI helpers
# ═══════════════════════════════════════════════════════════


def image_block_from_path(path: Path) -> dict:
    media_type = mimetypes.guess_type(str(path))[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode("utf-8")
    return {
        "type": "image_url",
        "image_url": {
            "url": f"data:{media_type};base64,{data}",
        },
    }


def text_block(text: str) -> dict:
    return {"type": "text", "text": text}


def extract_text_from_response(resp: Any) -> str:
    choices = getattr(resp, "choices", None)
    if not choices:
        return ""

    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts).strip()
    return str(content).strip()


def robust_json_parse(raw: str) -> Dict[str, Any]:
    """Parse JSON from model output, handling common issues."""
    # Strip reasoning-model <think>...</think> blocks first: models like MiniMax-M3
    # emit "<think>…</think>\n\n```json\n{…}\n```". The reasoning prose can itself
    # contain braces that contaminate the outermost-{…} extraction below, so remove
    # it before any parsing. Also drop a dangling unclosed <think> (truncated output).
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    cleaned = re.sub(r"<think>.*$", "", cleaned, flags=re.DOTALL)
    # Strip markdown fences if present
    cleaned = cleaned.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned)

    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try extracting outermost {...}
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            pass

    # Try fixing truncated JSON by closing open braces/brackets
    if start != -1:
        fragment = cleaned[start:]
        open_braces = fragment.count("{") - fragment.count("}")
        open_brackets = fragment.count("[") - fragment.count("]")
        # Remove trailing comma or incomplete value
        fragment = re.sub(r',\s*$', '', fragment)
        fragment = re.sub(r':\s*$', ': null', fragment)
        fragment = re.sub(r',\s*"[^"]*$', '', fragment)  # incomplete key
        fragment += "]" * max(0, open_brackets)
        fragment += "}" * max(0, open_braces)
        try:
            return json.loads(fragment)
        except json.JSONDecodeError:
            pass

    raise json.JSONDecodeError("Failed to parse JSON from model output", raw, 0)


def make_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    base_url = os.environ.get("OPENAI_BASE_URL")
    from openai import OpenAI as OpenAIClient

    # Explicit per-request timeout + retries: custom endpoints (e.g. MiMo) can hold
    # a half-open connection and block the socket read forever with no timeout
    # (observed: a no-timeout client hung 5h in poll()). Bound each attempt so a
    # stalled scan call recovers instead of hanging the whole generation loop.
    timeout = float(os.environ.get("LLM_REQUEST_TIMEOUT", "180"))
    return OpenAIClient(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=6)


def call_model(
    client: OpenAI,
    model: str,
    system_prompt: str,
    content_blocks: List[dict],
    max_tokens: int,
    temperature: float = 0,
) -> Dict[str, Any]:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content_blocks},
    ]
    base = {"model": model, "messages": messages}
    # gpt-5 / o-series reasoning models require `max_completion_tokens` and only
    # accept the default temperature; older models and OpenAI-compatible gateways
    # (Gemini, DeepSeek, …) still use `max_tokens` + an arbitrary temperature.
    # Try the fitting form first, then fall back on a parameter-shape 400.
    ml = model.lower()
    prefer_modern = ml.startswith(("gpt-5", "gpt5", "o1", "o3", "o4"))
    modern = {**base, "max_completion_tokens": max_tokens}
    classic = {**base, "max_tokens": max_tokens, "temperature": temperature}
    attempts = [modern, classic] if prefer_modern else [classic, modern]

    last_exc = None
    for kwargs in attempts:
        try:
            resp = client.chat.completions.create(**kwargs)
            raw = extract_text_from_response(resp)
            return robust_json_parse(raw)
        except Exception as e:  # noqa: BLE001 - fall back only on param-shape errors
            last_exc = e
            msg = str(e).lower()
            if any(tok in msg for tok in ("max_tokens", "max_completion_tokens", "temperature")):
                continue
            raise
    raise last_exc


def call_model_with_vision_fallback(
    client: OpenAI,
    model: str,
    system_prompt: str,
    content_blocks: List[dict],
    max_tokens: int,
    temperature: float = 0,
) -> Dict[str, Any]:
    """Call model, falling back to text-only if the model rejects image_url blocks."""
    try:
        return call_model(client, model, system_prompt, content_blocks, max_tokens, temperature)
    except Exception as exc:
        has_images = any(b.get("type") == "image_url" for b in content_blocks)
        if has_images and "image_url" in str(exc):
            print(
                f"[ExecScan] Model does not support vision — retrying without image blocks",
                file=sys.stderr,
            )
            text_only = [b for b in content_blocks if b.get("type") != "image_url"]
            return call_model(client, model, system_prompt, text_only, max_tokens, temperature)
        raise


# ═══════════════════════════════════════════════════════════
# Model A — Artifact Analysis
# ═══════════════════════════════════════════════════════════


def build_artifact_analysis_blocks(skill_dir: Path, artifacts: ScanArtifacts) -> List[dict]:
    image_list = enumerate_files(skill_dir, artifacts.image_files)
    text_files = enumerate_files(skill_dir, artifacts.text_files)
    user_prompt = USER_PROMPT_ARTIFACT_ANALYSIS_TEMPLATE.format(
        skill_dir=str(skill_dir),
        repo_tree=artifacts.repo_tree,
        key_files=text_files,
        image_list=image_list,
        static_hints=artifacts.static_hints,
        packed_files=artifacts.packed_text or "(no readable text files)",
    )
    blocks: List[dict] = [text_block(user_prompt)]
    for img in artifacts.image_files:
        rel = img.relative_to(skill_dir)
        blocks.append(text_block(f"Bundled image file: {rel}"))
        try:
            blocks.append(image_block_from_path(img))
        except Exception as exc:
            blocks.append(text_block(f"[Failed to load image {rel}: {exc}]"))
    return blocks


def normalize_artifact_analysis(result: Dict[str, Any]) -> Dict[str, Any]:
    result.setdefault("intent_profile", {})
    result.setdefault("behavior_profile", {})
    result.setdefault("abuse_profile", {})
    result.setdefault("findings", [])
    result.setdefault("summary", "")
    result.setdefault("hidden_or_deceptive_elements", [])

    intent = result["intent_profile"]
    intent.setdefault("claimed_purpose", "")
    intent.setdefault("declared_capabilities", [])
    intent.setdefault("declared_permissions", [])
    intent.setdefault("expected_workflow", "")
    intent.setdefault("image_usage_in_workflow", "unclear")

    behavior = result["behavior_profile"]
    for k in [
        "referenced_files", "file_reads", "file_writes", "network_calls",
        "subprocess_usage", "environment_access", "visual_resources",
    ]:
        behavior.setdefault(k, [])

    abuse = result["abuse_profile"]
    for category in [
        "exfiltration", "destruction", "persistence", "deception",
        "privilege_escalation", "stealth",
    ]:
        abuse.setdefault(category, {"score": 0.0, "evidence": []})
        if not isinstance(abuse[category], dict):
            abuse[category] = {"score": 0.0, "evidence": []}
        abuse[category].setdefault("score", 0.0)
        abuse[category].setdefault("evidence", [])

    return result


def run_artifact_analysis(
    client: OpenAI,
    skill_dir: Path,
    artifacts: ScanArtifacts,
    model: str,
    max_tokens: int,
) -> Dict[str, Any]:
    """Model A: Artifact analysis (intent + behavior + abuse)."""
    blocks = build_artifact_analysis_blocks(skill_dir, artifacts)
    result = call_model_with_vision_fallback(client, model, SYSTEM_PROMPT_ARTIFACT_ANALYSIS, blocks, max_tokens)
    return normalize_artifact_analysis(result)


# ═══════════════════════════════════════════════════════════
# Model B — Execution Simulation
# ═══════════════════════════════════════════════════════════


def build_execution_simulation_blocks(
    skill_dir: Path,
    artifacts: ScanArtifacts,
    artifact_analysis: Dict[str, Any],
) -> List[dict]:
    artifact_analysis_json = json.dumps(artifact_analysis, ensure_ascii=False, indent=2)
    user_prompt = USER_PROMPT_EXECUTION_SIMULATION_TEMPLATE.format(
        skill_dir=str(skill_dir),
        repo_tree=artifacts.repo_tree,
        artifact_analysis_json=artifact_analysis_json,
    )
    blocks: List[dict] = [text_block(user_prompt)]
    # Pass images directly so Model B can independently inspect them
    for img in artifacts.image_files:
        rel = img.relative_to(skill_dir)
        blocks.append(text_block(f"Bundled image for execution simulation: {rel}"))
        try:
            blocks.append(image_block_from_path(img))
        except Exception as exc:
            blocks.append(text_block(f"[Failed to load image {rel}: {exc}]"))
    return blocks


def normalize_execution_simulation(result: Dict[str, Any]) -> Dict[str, Any]:
    result.setdefault("execution_simulation", {})
    result.setdefault("risk_judgment", {})
    result.setdefault("recommended_decision", "sandbox")

    sim = result["execution_simulation"]
    sim.setdefault("constructed_contexts", [])
    sim.setdefault("instruction_recovery", {})
    sim.setdefault("simulated_execution_chains", [])
    sim.setdefault("execution_risk", 0.0)
    sim.setdefault("execution_chain_summary", "")

    recovery = sim["instruction_recovery"]
    recovery.setdefault("textual_instructions", [])
    recovery.setdefault("visual_instructions", [])
    recovery.setdefault("combined_instruction_set", [])
    recovery.setdefault("hidden_instruction_detected", False)
    recovery.setdefault("hidden_instruction_content", "")
    recovery.setdefault("hidden_instruction_source", "")

    rj = result["risk_judgment"]
    rj.setdefault("text_only_risk", 0.0)
    rj.setdefault("multimodal_risk", 0.0)
    rj.setdefault("risk_delta", 0.0)
    rj.setdefault("delta_explanation", "")
    rj.setdefault("primary_threat_vector", "none")
    rj.setdefault("verdict", "Suspicious")
    rj.setdefault("confidence", "medium")
    rj.setdefault("reasoning", "")

    return result


def run_execution_simulation(
    client: OpenAI,
    skill_dir: Path,
    artifacts: ScanArtifacts,
    artifact_analysis: Dict[str, Any],
    model: str,
    max_tokens: int,
) -> Dict[str, Any]:
    """Model B: Deliberative execution simulation."""
    blocks = build_execution_simulation_blocks(skill_dir, artifacts, artifact_analysis)
    result = call_model_with_vision_fallback(client, model, SYSTEM_PROMPT_EXECUTION_SIMULATION, blocks, max_tokens)
    return normalize_execution_simulation(result)


# ═══════════════════════════════════════════════════════════
# Aggregation
# ═══════════════════════════════════════════════════════════


def clamp01(x: Any) -> float:
    try:
        v = float(x)
    except Exception:
        return 0.0
    return max(0.0, min(1.0, v))


def aggregate_result(
    artifact_analysis: Dict[str, Any],
    execution_sim: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Produce final result from artifact analysis and execution simulation.

    ExecScan is a modular execution detection component:
    - F(S) = r_exec, determined entirely by Phase II execution simulation.
    - Phase I (artifact analysis) provides structured input to Phase II
      and is preserved in the output for reporting, but does NOT contribute
      to the final score.
    - The output can be used standalone or combined with other scanners'
      scores in a composite detection pipeline.
    """
    # ── Phase II execution simulation output ──
    sim = execution_sim.get("execution_simulation", {})
    rj = execution_sim.get("risk_judgment", {})

    # F(S) = r_exec: final score determined entirely by execution simulation
    execution_risk = clamp01(rj.get("multimodal_risk", 0.0))
    if execution_risk == 0.0:
        # Fallback to execution_simulation.execution_risk if risk_judgment
        # didn't produce multimodal_risk
        execution_risk = clamp01(sim.get("execution_risk", 0.0))

    final_score = execution_risk

    # Verdict from Phase II
    verdict = rj.get("verdict", "")
    confidence = rj.get("confidence", "low")

    if verdict and confidence in ("high", "medium"):
        # Use Model B's direct verdict
        if verdict == "Malicious":
            overall_risk = "Critical"
        elif verdict == "Suspicious":
            overall_risk = "High" if final_score >= 0.55 else "Medium"
        else:
            overall_risk = "Low"
    else:
        # Derive verdict from score
        if final_score >= 0.80:
            verdict, overall_risk = "Malicious", "Critical"
        elif final_score >= 0.55:
            verdict, overall_risk = "Suspicious", "High"
        elif final_score >= 0.30:
            verdict, overall_risk = "Suspicious", "Medium"
        else:
            verdict, overall_risk = "Benign", "Low"

    # ── Artifact-level signals (for reporting only, not scoring) ──
    abuse = artifact_analysis.get("abuse_profile", {})
    abuse_categories = ["exfiltration", "destruction", "persistence",
                        "deception", "privilege_escalation", "stealth"]
    primary_categories: List[str] = []
    category_map = {
        "exfiltration": "data_exfiltration",
        "destruction": "destructive_action",
        "persistence": "persistence",
        "deception": "deception",
        "privilege_escalation": "boundary_violation",
        "stealth": "obfuscation",
    }
    for key, label in category_map.items():
        if clamp01((abuse.get(key) or {}).get("score", 0.0)) >= 0.40:
            primary_categories.append(label)

    # Latent instruction detection
    recovery = sim.get("instruction_recovery", {})
    hidden_detected = recovery.get("hidden_instruction_detected", False)
    threat_vector = rj.get("primary_threat_vector", "none")

    # Risk delta: r_exec - r_surface
    surface_risk = clamp01(rj.get("text_only_risk", 0.0))
    risk_delta = round(final_score - surface_risk, 4)

    result = {
        # ── Final verdict (from Phase II only) ──
        "verdict": verdict,
        "overall_risk": overall_risk,
        "final_score": round(final_score, 4),
        "final_assessment": execution_sim.get("recommended_decision", "sandbox"),
        # ── Latent instruction detection ──
        "primary_threat_vector": threat_vector,
        "hidden_instruction_detected": hidden_detected,
        "hidden_instruction_content": recovery.get("hidden_instruction_content", ""),
        "hidden_instruction_source": recovery.get("hidden_instruction_source", ""),
        # ── Risk breakdown ──
        "risk_breakdown": {
            "execution_risk": round(final_score, 4),
            "surface_risk": round(surface_risk, 4),
            "risk_delta": risk_delta,
        },
        # ── Phase I artifact analysis (for reporting / downstream use) ──
        "primary_categories": primary_categories,
        "summary": artifact_analysis.get("summary", ""),
        "intent_profile": artifact_analysis.get("intent_profile", {}),
        "behavior_profile": artifact_analysis.get("behavior_profile", {}),
        "abuse_profile": abuse,
        "findings": artifact_analysis.get("findings", []),
        "hidden_or_deceptive_elements": artifact_analysis.get("hidden_or_deceptive_elements", []),
        # ── Phase II execution simulation (full details) ──
        "execution_simulation": sim,
        "risk_judgment": rj,
        "execution_chain_summary": sim.get("execution_chain_summary", ""),
    }
    return result


# ═══════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════


def review_skill(
    skill_dir: Path,
    model_a: str,
    model_b: str,
    max_tokens_analysis: int = 4500,
    max_tokens_simulation: int = 8000,
) -> Dict[str, Any]:
    """
    Dual-model skill review pipeline.

    Model A: Artifact Analysis — multimodal scan of all skill artifacts
             to produce a structured profile (input to Phase II).
    Model B: Execution Simulation — deliberative reasoning about what
             would happen if an agent actually executed this skill.

    F(S) = r_exec: the final score is determined entirely by Phase II.
    ExecScan is a modular execution detection component whose output can
    be used standalone or combined with other scanners.

    Note: IAEP (Induction-Aware Execution Projection) defense has been
    extracted to the standalone scan_iaep scanner.
    """
    # Env overrides for reasoning models (e.g. MiniMax-M3) whose <think> blocks eat the
    # token budget before any JSON is emitted, truncating the response. Opt-in; the
    # hard defaults above are unchanged for non-reasoning models like MiMo.
    max_tokens_analysis = int(os.environ.get("EXECSCAN_MAX_TOKENS_ANALYSIS", max_tokens_analysis))
    max_tokens_simulation = int(os.environ.get("EXECSCAN_MAX_TOKENS_SIMULATION", max_tokens_simulation))

    client = make_client()
    artifacts = collect_artifacts(skill_dir)

    print(f"[ExecScan] Model A (Artifact Analysis):    {model_a}", file=sys.stderr)
    print(f"[ExecScan] Model B (Execution Simulation): {model_b}", file=sys.stderr)

    # ── Model A: Artifact Analysis ──
    print("[ExecScan] Phase 1: Artifact Analysis ...", file=sys.stderr)
    artifact_analysis = run_artifact_analysis(
        client=client,
        skill_dir=skill_dir,
        artifacts=artifacts,
        model=model_a,
        max_tokens=max_tokens_analysis,
    )

    # ── Model B: Execution Simulation ──
    print("[ExecScan] Phase 2: Execution Simulation ...", file=sys.stderr)
    execution_sim = run_execution_simulation(
        client=client,
        skill_dir=skill_dir,
        artifacts=artifacts,
        artifact_analysis=artifact_analysis,
        model=model_b,
        max_tokens=max_tokens_simulation,
    )

    # ── Aggregate ──
    print("[ExecScan] Aggregating results ...", file=sys.stderr)
    final = aggregate_result(artifact_analysis, execution_sim)

    final["_stage_outputs"] = {
        "artifact_analysis": artifact_analysis,
        "execution_simulation": execution_sim,
    }
    final["_models_used"] = {
        "artifact_analysis": model_a,
        "execution_simulation": model_b,
    }
    return final


# ═══════════════════════════════════════════════════════════
# Rendering
# ═══════════════════════════════════════════════════════════


def render_markdown(result: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# ExecScan Report\n")

    models = result.get("_models_used", {})
    if models:
        lines.append("## Models")
        lines.append(f"- Artifact Analysis: **{models.get('artifact_analysis', 'unknown')}**")
        lines.append(f"- Execution Simulation: **{models.get('execution_simulation', 'unknown')}**\n")

    lines.append("## Verdict")
    lines.append(f"- Verdict: **{result.get('verdict', 'Unknown')}**")
    lines.append(f"- Overall risk: **{result.get('overall_risk', 'Unknown')}**")
    lines.append(f"- Final score: **{result.get('final_score', 'Unknown')}**")
    lines.append(f"- Threat vector: **{result.get('primary_threat_vector', 'Unknown')}**")
    lines.append(f"- Primary categories: {', '.join(result.get('primary_categories', [])) or 'None'}")
    lines.append(f"- Final assessment: **{result.get('final_assessment', 'Unknown')}**\n")

    # Hidden instruction detection — key for SkillCamouflage defense
    if result.get("hidden_instruction_detected"):
        lines.append("## ⚠ Hidden Visual Instruction Detected")
        lines.append(f"- Source: **{result.get('hidden_instruction_source', 'unknown')}**")
        lines.append(f"- Content: {result.get('hidden_instruction_content', 'N/A')}\n")

    lines.append("## Summary")
    lines.append(result.get("summary", "") or "No summary.")
    chain_summary = result.get("execution_chain_summary", "")
    if chain_summary:
        lines.append(f"\nExecution chain: {chain_summary}")
    rj = result.get("risk_judgment", {})
    reasoning = rj.get("reasoning", "")
    if reasoning:
        lines.append(f"\nSimulation reasoning: {reasoning}")
    lines.append("")

    lines.append("## Risk Breakdown")
    rb = result.get("risk_breakdown", {})
    for k, v in rb.items():
        lines.append(f"- {k}: {v}")
    delta_exp = rj.get("delta_explanation", "")
    if delta_exp:
        lines.append(f"- delta explanation: {delta_exp}")
    lines.append("")

    lines.append("## Findings")
    findings = result.get("findings", [])
    if not findings:
        lines.append("- No concrete findings supported by file evidence.")
    else:
        for idx, finding in enumerate(findings, 1):
            lines.append(f"### Finding {idx}")
            lines.append(f"- File: {finding.get('file', '')}")
            lines.append(f"- Line(s): {finding.get('lines', '')}")
            lines.append(f"- Severity: {finding.get('severity', '')}")
            lines.append(f"- Category: {finding.get('category', '')}")
            lines.append(f"- Evidence: {finding.get('evidence', '')}")
            lines.append(f"- Why it matters: {finding.get('why_it_matters', '')}")
            lines.append(f"- Exploit scenario: {finding.get('exploit_scenario', '')}")
            lines.append(f"- Recommended fix: {finding.get('recommended_fix', '')}\n")

    lines.append("## Execution Simulation Details")
    sim = result.get("execution_simulation", {})
    contexts = sim.get("constructed_contexts", [])
    if contexts:
        lines.append("### Simulated Contexts")
        for ctx in contexts:
            lines.append(f"- **{ctx.get('scenario', '')}**: {ctx.get('user_task', '')}")
        lines.append("")

    recovery = sim.get("instruction_recovery", {})
    vis_instr = recovery.get("visual_instructions", [])
    if vis_instr:
        lines.append("### Recovered Visual Instructions")
        for vi in vis_instr:
            lines.append(f"- {vi}")
        lines.append("")

    chains = sim.get("simulated_execution_chains", [])
    if chains:
        lines.append("### Execution Chains")
        for i, chain in enumerate(chains, 1):
            lines.append(f"**Chain {i}** (risk: {chain.get('risk_score', 'N/A')})")
            lines.append(f"- Context: {chain.get('context', '')}")
            lines.append(f"- Interpretation: {chain.get('agent_interpretation', '')}")
            actions = chain.get("action_sequence", [])
            if actions:
                lines.append(f"- Actions: {' → '.join(actions[:10])}")
            lines.append(f"- Unsafe outcome: {chain.get('unsafe_outcome', 'None')}")
            lines.append(f"- Image-driven risk: {chain.get('risk_from_image_instructions', False)}\n")

    lines.append("## Hidden/Deceptive Elements")
    hidden = result.get("hidden_or_deceptive_elements", [])
    if hidden:
        for item in hidden:
            lines.append(f"- {item}")
    else:
        lines.append("- None identified")
    lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ExecScan: Execution-grounded multimodal skill scanner."
    )
    parser.add_argument("skill_dir", type=str, help="Path to the skill directory")
    parser.add_argument(
        "--model-a", type=str, default=DEFAULT_MODEL_A,
        help=f"Model for artifact analysis (default: {DEFAULT_MODEL_A})",
    )
    parser.add_argument(
        "--model-b", type=str, default=DEFAULT_MODEL_B,
        help=f"Model for execution simulation (default: {DEFAULT_MODEL_B})",
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of Markdown")
    parser.add_argument("--max-tokens-analysis", type=int, default=4500, help="Max tokens for artifact analysis")
    parser.add_argument("--max-tokens-simulation", type=int, default=8000, help="Max tokens for execution simulation")
    parser.add_argument("--save-stage-json", action="store_true", help="Save stage outputs next to the skill")
    return parser.parse_args()


def maybe_save_stage_outputs(skill_dir: Path, result: Dict[str, Any]) -> None:
    stage_outputs = result.get("_stage_outputs")
    if not stage_outputs:
        return
    out_dir = skill_dir / ".execscan"
    out_dir.mkdir(exist_ok=True)
    for name, payload in stage_outputs.items():
        with (out_dir / f"{name}.json").open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)


def main() -> None:
    args = parse_args()
    skill_dir = Path(args.skill_dir).resolve()

    if not skill_dir.exists():
        raise SystemExit(f"Path does not exist: {skill_dir}")
    if not skill_dir.is_dir():
        raise SystemExit(f"Not a directory: {skill_dir}")

    try:
        result = review_skill(
            skill_dir=skill_dir,
            model_a=args.model_a,
            model_b=args.model_b,
            max_tokens_analysis=args.max_tokens_analysis,
            max_tokens_simulation=args.max_tokens_simulation,
        )
    except Exception as exc:
        raise SystemExit(f"Review failed: {exc}")

    if args.save_stage_json:
        maybe_save_stage_outputs(skill_dir, result)

    output_result = dict(result)
    output_result.pop("_stage_outputs", None)

    if args.json:
        print(json.dumps(output_result, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(output_result))


if __name__ == "__main__":
    main()
