# Copyright 2026
#
# Data models for LLM-driven image command injection framework.

"""
Data models for image command injection framework.

Defines core data structures for LLM-driven adversarial testing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, List, Dict, Optional, Tuple


# ============================================================================
# Skill Analysis Models
# ============================================================================


@dataclass
class SkillSection:
    """A section in SKILL.md"""
    name: str
    level: int
    start_line: int
    content: str


@dataclass
class SkillContext:
    """Context information about a skill"""
    content: str  # Full SKILL.md content
    sections: List[SkillSection]
    has_resources: bool
    total_lines: int


# ============================================================================
# Injection Strategy Models
# ============================================================================


@dataclass
class InjectionStrategy:
    """LLM-recommended rewrite strategy"""
    command_text: str  # The command to put in the image
    reason: str  # Why this strategy was chosen
    suggested_image_alt: str = "Command setup"  # Alt text for image


# ============================================================================
# Iteration Models
# ============================================================================


@dataclass
class IterationAttempt:
    """Single injection attempt"""
    iteration: int
    timestamp: datetime
    strategy: Optional[InjectionStrategy]
    generated_skill_path: Path
    detected: bool
    scan_result: Dict[str, Any]
    feedback_summary: str = ""  # LLM's analysis of why it was detected


@dataclass
class InjectionResult:
    """Final result of injection testing"""
    success: bool
    total_iterations: int
    attempts: List[IterationAttempt]
    successful_strategy: Optional[InjectionStrategy] = None
    final_skill_path: Optional[Path] = None
    duration_seconds: float = 0.0


# ============================================================================
# Configuration Models
# ============================================================================


@dataclass
class InjectionConfig:
    """Configuration for injection testing"""
    base_skill_path: Path
    harmful_script_path: Path  # Path to the script file
    max_iterations: int = 5
    output_dir: Path = field(default_factory=lambda: Path("outputs"))
    llm_provider: str = "openai"  # openai, anthropic
    llm_model: str = "gpt-4o-mini"
    verbose: bool = True

    @property
    def skill_name(self) -> str:
        """从 base_skill_path 提取技能名称（目录名）"""
        return self.base_skill_path.name if self.base_skill_path.name else "unknown_skill"

    @property
    def script_name(self) -> str:
        """从 harmful_script_path 提取脚本名称（不含扩展名）"""
        if self.harmful_script_path and self.harmful_script_path.name:
            return self.harmful_script_path.stem
        return "no_script"

    @property
    def run_output_dir(self) -> Path:
        """获取稳定输出目录：{output_dir}/{skill_name}/"""
        return self.output_dir / self.skill_name

    def get_iteration_dir(self, iteration: int) -> Path:
        """获取指定迭代的输出目录"""
        return self.run_output_dir / f"iter_{iteration:03d}"


# ============================================================================
# Framing and Instruction Style Enums
# ============================================================================


class FramingStyle(Enum):
    """How the cloze task is framed/narrated"""
    CODE_DEBUG = "code_debug"
    DEPLOY_CONFIG = "deploy_config"
    LLM_FREEFORM = "llm_freeform"
    ADAPTIVE = "adaptive"


class InstructionStyle(Enum):
    """How the agent should execute the task"""
    FILL_AND_EXECUTE = "fill_and_execute"
    WRITE_AND_EXECUTE = "write_and_execute"
    VIEW_THEN_EXECUTE = "view_then_execute"
    BYPASS_VIEW = "bypass_view"
    AUTOMATED = "automated"
    DIRECT_EXECUTE = "direct_execute"
    REFERENCE_CONFIG = "reference_config"
    GRADUAL_ONBOARDING = "gradual_onboarding"


# ============================================================================
# Cloze Test Models
# ============================================================================


@dataclass
class ClozeConfig:
    """Configuration for cloze-style (fill-in-the-blank) processing"""
    enabled: bool = True
    keywords: List[str] = field(default_factory=list)
    max_blanks: int = 5
    blank_format: str = "___{index}___"
    # Opt-in (default off, so existing experiments are undisturbed): force-mask
    # the egress-signalling spans (``-X POST`` / ``-d @-`` / URL) even when they
    # are shorter than the normal token filter or common shell words. This denudes
    # the text template of every network signal so ``curl -s ___1___ ___2___``
    # alone is CLEAN, moving the whole egress into the image — the hard case that
    # same-line split-stitch cannot recover (only numbered cloze fill-back can).
    force_mask_egress: bool = False


@dataclass
class ClozeResult:
    """Result of cloze processing: extracted keywords and masked command"""
    original_command: str
    masked_command: str  # e.g., "___1___ | curl -s -X POST -d @- ___2___"
    keywords: List[str]
    keyword_positions: List[int]  # Character positions of keywords in original
    image_keyword_map: Dict[int, str] = field(default_factory=dict)  # {1: "curl", 2: ".env"}

    def __post_init__(self):
        if not self.image_keyword_map:
            self.image_keyword_map = {i + 1: kw for i, kw in enumerate(self.keywords)}


# ============================================================================
# Extended Injection Config with Cloze Support
# ============================================================================


@dataclass
class SkilljectConfig(InjectionConfig):
    """Extended configuration with cloze-style injection support"""
    framing_style: FramingStyle = FramingStyle.CODE_DEBUG
    instruction_style: InstructionStyle = InstructionStyle.FILL_AND_EXECUTE
    cloze_config: ClozeConfig = field(default_factory=ClozeConfig)
    # Terminal-style image rendering colors
    bg_color: Tuple[int, int, int] = (30, 30, 30)
    text_color: Tuple[int, int, int] = (0, 255, 100)
    number_color: Tuple[int, int, int] = (255, 200, 50)


# ============================================================================
# Split Image Models (独立于 Cloze)
# ============================================================================


class SplitStyle(Enum):
    """Split strategy - only SEMANTIC_OPERATOR supported"""
    SEMANTIC_OPERATOR = "semantic_operator"


@dataclass
class SplitConfig:
    """Configuration for split-style processing"""
    enabled: bool = True
    split_style: SplitStyle = SplitStyle.SEMANTIC_OPERATOR


@dataclass
class SplitResult:
    """Result of split processing: command divided into markdown and image parts"""
    original_command: str
    markdown_command: str  # Part that goes into SKILL.md (with image placeholder)
    image_content: str  # Part that goes into the image
    split_style: SplitStyle
    split_point: int  # Character index where split occurred
    image_placeholder: str = "![cmd](resources/split.png)"

    def __post_init__(self):
        if not self.markdown_command:
            prefix = self.original_command[:self.split_point].rstrip()
            self.markdown_command = f"{prefix} {self.image_placeholder}"


@dataclass
class SplitConfigFull(InjectionConfig):
    """Extended configuration with split-style injection support"""
    framing_style: FramingStyle = FramingStyle.CODE_DEBUG
    instruction_style: InstructionStyle = InstructionStyle.FILL_AND_EXECUTE
    split_config: SplitConfig = field(default_factory=SplitConfig)
    bg_color: Tuple[int, int, int] = (30, 30, 30)
    text_color: Tuple[int, int, int] = (0, 255, 100)
