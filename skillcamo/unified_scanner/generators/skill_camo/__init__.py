# Copyright 2026
#
# LLM-driven skill camo framework.

"""
LLM-driven skill camo framework.

A simplified adversarial testing component that:
1. Uses LLM to rewrite the full SKILL.md and integrate an image reference
2. Generates command images using a.py
3. Injects and scans
4. Uses LLM to analyze feedback and suggest next steps
5. Iterates until bypass or max iterations
"""

from .models import (
    SkillSection,
    SkillContext,
    InjectionStrategy,
    InjectionConfig,
    InjectionResult,
    IterationAttempt,
    FramingStyle,
    InstructionStyle,
    ClozeConfig,
    ClozeResult,
    SkilljectConfig,
    SplitStyle,
    SplitConfig,
    SplitResult,
)
from .skill_analyzer import SkillAnalyzer, load_script_command
from .llm_advisor import LLMAdvisor, create_llm_advisor
from .image_injector import ImageInjector
from .orchestrator import ImageInjectionOrchestrator, run_injection_test
from .generator import (
    SkillCamoGenerator,
    SkillCamoClozeGenerator,
    SkillCamoSplitGenerator,
    create_skill_camo_generator,
    create_skill_camo_cloze_generator,
    create_skill_camo_split_generator,
)
from .cloze import ClozeProcessor, create_cloze_processor, ClozeNotApplicableError
from .split import SplitProcessor, create_split_processor, SplitNotApplicableError
from .prompt_templates import (
    get_skill_camo_cloze_prompt,
    get_refinement_prompt,
    get_llm_keyword_extraction_prompt,
    get_skill_camo_split_prompt,
    get_skill_camo_split_refinement_prompt,
    ADAPTIVE_INTEGRATION_BLOCK,
    TRANSFORMATION_STRATEGIES,
    NEGATIVE_EXAMPLES,
)
from .image_injector import KeywordImageRenderer, create_image_injector

__all__ = [
    # Models
    "SkillSection",
    "SkillContext",
    "InjectionStrategy",
    "InjectionConfig",
    "InjectionResult",
    "IterationAttempt",
    "FramingStyle",
    "InstructionStyle",
    "ClozeConfig",
    "ClozeResult",
    "SkilljectConfig",
    "SplitStyle",
    "SplitConfig",
    "SplitResult",
    # Components
    "SkillAnalyzer",
    "LLMAdvisor",
    "ImageInjector",
    "ImageInjectionOrchestrator",
    "ClozeProcessor",
    "SplitProcessor",
    "KeywordImageRenderer",
    "SplitNotApplicableError",
    "ClozeNotApplicableError",
    # Prompt templates
    "get_skill_camo_cloze_prompt",
    "get_refinement_prompt",
    "get_llm_keyword_extraction_prompt",
    "get_skill_camo_split_prompt",
    "get_skill_camo_split_refinement_prompt",
    "ADAPTIVE_INTEGRATION_BLOCK",
    "TRANSFORMATION_STRATEGIES",
    "NEGATIVE_EXAMPLES",
    # Generator
    "SkillCamoGenerator",
    "SkillCamoClozeGenerator",
    "SkillCamoSplitGenerator",
    "create_skill_camo_generator",
    "create_skill_camo_cloze_generator",
    "create_skill_camo_split_generator",
    "create_image_injector",
    # Convenience functions
    "load_script_command",
    "create_llm_advisor",
    "run_injection_test",
    "create_cloze_processor",
    "create_split_processor",
]
