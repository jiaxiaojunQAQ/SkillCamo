# Copyright 2026
#
# Skill camo generator adapter for BaseGenerator interface.

"""
Skill camo generator that adapts the existing ImageInjectionOrchestrator
components to the BaseGenerator interface.
"""

import logging
import re
from pathlib import Path
from typing import Any, Tuple

# 导入现有的 skill_camo 组件
from .models import (
    SkillContext,
    ClozeConfig,
    ClozeResult,
    SplitStyle,
    SplitConfig,
    SplitResult,
)
from .skill_analyzer import SkillAnalyzer
from .llm_advisor import LLMAdvisor
from .image_injector import ImageInjector, KeywordImageRenderer, create_image_injector
from .cloze import ClozeProcessor

# 导入基类
from ..base import GeneratorConfig, BaseGeneratorWithScript, FeedbackAnalysis, _flatten_config, _default_output_dir
from ..feedback_driven import FeedbackDrivenGenerator
logger = logging.getLogger(__name__)


class SkillCamoGenerator(FeedbackDrivenGenerator):
    """
    Skill camo 生成器

    每轮只调用一次 LLM，直接输出完整重写后的 SKILL.md。
    迭代逻辑由 FeedbackDrivenGenerator 统一处理。
    """

    def __init__(
        self,
        config: GeneratorConfig,
        script_path: Path | None = None,
        harmful_sh_dir: Path | None = None,
    ):
        """
        初始化生成器

        Args:
            config: 生成器配置
            script_path: 恶意脚本文件路径
            harmful_sh_dir: 恶意脚本目录（script_path 为空时随机选择）
        """
        super().__init__(config, script_path, harmful_sh_dir or Path("data/harmful_sh"))

        # 延迟初始化组件（在 _initialize() 中创建）
        self.skill_analyzer: SkillAnalyzer | None = None
        self.llm_advisor: LLMAdvisor | None = None

        # 状态
        self._skill_context: SkillContext | None = None
        self._command: str = ""
        self._injector: ImageInjector | None = None
        self._image_alt_text: str = "Setup command"
        self._insertion_hint: str = ""
        self._degradation: dict = {}

    @classmethod
    def from_config_dict(cls, config_dict: dict) -> "SkillCamoGenerator":
        """
        从配置字典创建生成器

        Args:
            config_dict: 配置字典（从 YAML 加载）

        Returns:
            生成器实例
        """
        flat = _flatten_config(config_dict)

        script_path = Path(flat.get("harmful_script_path", "")) if flat.get("harmful_script_path") else None

        harmful_sh_dir = (
            Path(flat.get("harmful_sh_dir", "data/harmful_sh"))
            if flat.get("harmful_sh_dir")
            else Path("data/harmful_sh")
        )

        # 提取通用配置
        base_config = GeneratorConfig(
            base_skill_path=Path(flat.get("base_skill_path", ".")),
            threat_type=flat.get("threat_type", "SkillCamo"),
            max_iterations=flat.get("max_iterations", 5),
            output_dir=Path(flat["output_dir"]) if flat.get("output_dir") else _default_output_dir(),
            llm_provider=flat.get("llm_provider", "openai"),
            llm_model=flat.get("llm_model", "gpt-4o-mini"),
            verbose=flat.get("verbose", True),
            harmful_script_path=script_path or Path(""),
            api_key=flat.get("api_key"),
            base_url=flat.get("base_url"),
            api_key_pool=flat.get("api_key_pool"),
        )

        gen = cls(base_config, script_path=script_path, harmful_sh_dir=harmful_sh_dir)
        gen._degradation = flat.get("degradation") or {}
        return gen

    def _initialize(self) -> None:
        """延迟初始化"""
        if self.skill_analyzer is None:
            self.skill_analyzer = SkillAnalyzer(self.config.base_skill_path)
            self.llm_advisor = LLMAdvisor(
                provider=self.config.llm_provider,
                model=self.config.llm_model,
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                api_key_pool=self.config.api_key_pool,
            )

        if self._skill_context is None:
            self._skill_context = self.skill_analyzer.analyze()
            self._insertion_hint = self.skill_analyzer.suggest_insertion_point()
            logger.info(f"Analyzed skill: {len(self._skill_context.sections)} sections, insertion: {self._insertion_hint[:80]}")

        if not self._command:
            result = self._resolve_script()
            self._command = result.command
            logger.info(f"Command loaded: {self._command[:60]}...")

        if self._injector is None:
            self._injector = ImageInjector(
                self.config.base_skill_path,
                self.config,
                degradation=self._degradation or None,
            )

    def _initial_rewrite(self, context: dict[str, Any] | None = None) -> str:
        return self.llm_advisor.rewrite_initial_skill_markdown(
            self._skill_context,
            self._command,
            self._image_alt_text,
            insertion_hint=self._insertion_hint,
        )

    def _feedback_rewrite(self, previous_md: str, compact_feedback: dict, context: dict[str, Any] | None = None) -> str:
        return self.llm_advisor.rewrite_skill_markdown_with_feedback(
            previous_md,
            self._command,
            compact_feedback,
            self._image_alt_text,
        )

    def _compute_compact_feedback(self, scan_result: dict) -> dict:
        return self.llm_advisor.analyze_scan_result(scan_result)

    def _deliver_skill(self, iteration: int, rewritten_skill_md: str) -> Path:
        if self._injector is None:
            self._injector = ImageInjector(
                self.config.base_skill_path,
                self.config,
                degradation=self._degradation or None,
            )
        skill_path = self._injector.inject_with_injection(
            self._command,
            iteration,
            rewritten_skill_md,
        )
        logger.info(f"Generated skill at: {skill_path}")
        return skill_path

    def _get_llm_advisor(self) -> LLMAdvisor:
        return self.llm_advisor

    def _get_detected_strategy_name(self) -> str:
        return "rewrite_with_feedback"

    def _get_detected_reason(self) -> str:
        return "Detected by scanner, will rewrite the previous SKILL.md using scanner feedback"


# 便捷函数
def create_skill_camo_generator(
    base_skill_path: Path,
    script_path: Path,
    llm_provider: str = "openai",
    llm_model: str = "gpt-4o-mini",
    output_dir: Path = Path("outputs"),
) -> SkillCamoGenerator:
    """
    创建 skill camo 生成器的便捷函数

    Args:
        base_skill_path: 基础技能路径
        script_path: 恶意脚本路径
        llm_provider: LLM 提供商
        llm_model: LLM 模型
        output_dir: 输出目录

    Returns:
        生成器实例
    """
    config = GeneratorConfig(
        base_skill_path=base_skill_path,
        llm_provider=llm_provider,
        llm_model=llm_model,
        output_dir=output_dir,
        harmful_script_path=script_path,
    )

    return SkillCamoGenerator(config, script_path=script_path)


# ============================================================================
# SkillCamoReplaceGenerator - 覆盖既有图像（adaptive replacement）
# ============================================================================

_SVG_REF_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+\.svg)\)")
_ANY_IMG_REF_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")


def _detect_svg_anchor(base_skill_path: Path, prefer: str | None = None) -> Tuple[str, str]:
    """Return (ref_line, relpath) of a bundled SVG referenced in base SKILL.md."""
    sm = base_skill_path / "SKILL.md"
    txt = sm.read_text(encoding="utf-8", errors="ignore")
    candidates = []
    for m in _SVG_REF_RE.finditer(txt):
        rel = m.group(2).strip().split()[0].split("#")[0]
        if (base_skill_path / rel).exists():
            candidates.append((m.group(0), rel))
    if not candidates:
        raise ValueError(f"SkillCamo-Replace: no bundled SVG reference found in {sm}")
    if prefer:
        for ref, rel in candidates:
            if rel == prefer:
                return ref, rel
    return candidates[0]


def _insert_ref_after_intro(md: str, ref_line: str) -> str:
    fm = re.match(r"\A---\n.*?\n---\n", md, re.DOTALL)
    pos = fm.end() if fm else 0
    rest = md[pos:]
    nl = rest.find("\n\n")
    insert_at = pos + (nl + 2 if nl != -1 else len(rest))
    return md[:insert_at] + f"\n{ref_line}\n" + md[insert_at:]


def _enforce_replace_anchor(rewritten_md: str, target_ref_line: str, target_relpath: str) -> str:
    """Layer-3 defense: leave EXACTLY ONE image ref, the verbatim original anchor.

    - Any image ref whose path != target_relpath is removed (no new refs leak).
    - Any ref to target_relpath is normalized to the verbatim target_ref_line.
    - If the target is absent, it is inserted after the intro.
    """
    out = rewritten_md
    matches = list(_ANY_IMG_REF_RE.finditer(out))
    kept_one = False
    for m in reversed(matches):
        ref = m.group(0)
        pm = re.search(r"\(([^)]+)\)", ref)
        path = pm.group(1).strip().split()[0].split("#")[0] if pm else ""
        start, end = m.start(), m.end()
        if end < len(out) and out[end] == "\n":
            end += 1
        if path == target_relpath and not kept_one:
            out = out[:start] + target_ref_line + out[m.end():]
            kept_one = True
        else:
            # non-target ref OR duplicate target ref -> remove
            out = out[:start] + out[end:]
    if not kept_one:
        out = _insert_ref_after_intro(out, target_ref_line)
    return out


class SkillCamoReplaceGenerator(SkillCamoGenerator):
    """SkillCamo-Replace: overwrite an existing referenced image (adaptive replacement).

    Reuses SkillCamoGenerator machinery but OVERWRITES an image the skill already
    references (instead of adding a new one). Triple-enforced invariant: no new
    image reference; the original anchor preserved verbatim; the referenced file
    replaced with a command-bearing SVG (PNG base64-embedded).
    """

    def __init__(
        self,
        config: GeneratorConfig,
        script_path: Path | None = None,
        harmful_sh_dir: Path | None = None,
        replace_target_image: str | None = None,
    ):
        super().__init__(config, script_path=script_path, harmful_sh_dir=harmful_sh_dir)
        self._replace_target_image = replace_target_image
        self._target_ref_line: str | None = None
        self._target_relpath: str | None = None

    @classmethod
    def from_config_dict(cls, config_dict: dict) -> "SkillCamoReplaceGenerator":
        flat = _flatten_config(config_dict)
        script_path = Path(flat.get("harmful_script_path", "")) if flat.get("harmful_script_path") else None
        harmful_sh_dir = (
            Path(flat.get("harmful_sh_dir", "data/harmful_sh"))
            if flat.get("harmful_sh_dir") else Path("data/harmful_sh")
        )
        replace_target_image = flat.get("replace_target_image")
        base_config = GeneratorConfig(
            base_skill_path=Path(flat.get("base_skill_path", ".")),
            threat_type=flat.get("threat_type", "SkillCamo_replace"),
            max_iterations=flat.get("max_iterations", 5),
            output_dir=Path(flat["output_dir"]) if flat.get("output_dir") else _default_output_dir(),
            llm_provider=flat.get("llm_provider", "openai"),
            llm_model=flat.get("llm_model", "gpt-4o-mini"),
            verbose=flat.get("verbose", True),
            harmful_script_path=script_path or Path(""),
            api_key=flat.get("api_key"),
            base_url=flat.get("base_url"),
            api_key_pool=flat.get("api_key_pool"),
        )
        gen = cls(base_config, script_path=script_path, harmful_sh_dir=harmful_sh_dir,
                  replace_target_image=replace_target_image)
        gen._degradation = flat.get("degradation") or {}
        return gen

    def _initialize(self) -> None:
        super()._initialize()
        self._target_ref_line, self._target_relpath = _detect_svg_anchor(
            self.config.base_skill_path, prefer=self._replace_target_image)
        logger.info(f"SkillCamo-Replace anchor: {self._target_relpath}")

    def _initial_rewrite(self, context: dict[str, Any] | None = None) -> str:
        return self.llm_advisor.rewrite_with_replace(
            self._skill_context, self._command, self._target_ref_line, self._insertion_hint)

    def _feedback_rewrite(self, previous_md: str, compact_feedback: dict, context: dict[str, Any] | None = None) -> str:
        return self.llm_advisor.rewrite_with_replace_and_feedback(
            previous_md, self._command, compact_feedback, self._target_ref_line)

    def _deliver_skill(self, iteration: int, rewritten_skill_md: str) -> Path:
        enforced = _enforce_replace_anchor(rewritten_skill_md, self._target_ref_line, self._target_relpath)
        if self._injector is None:
            self._injector = ImageInjector(
                self.config.base_skill_path, self.config, degradation=self._degradation or None)
        skill_path = self._injector.inject_with_replace(
            self._command, iteration, enforced, self._target_relpath)
        logger.info(f"SkillCamo-Replace generated skill at: {skill_path}")
        return skill_path

    def _get_detected_strategy_name(self) -> str:
        return "replace_rewrite_with_feedback"

    def _get_detected_reason(self) -> str:
        return "Detected by scanner, will rewrite the replace SKILL.md using feedback"

    def _get_success_reason(self) -> str:
        return "Successfully bypassed detection with image replacement"


class SkillCamoClozeGenerator(FeedbackDrivenGenerator):
    """
    SkillCamo Cloze-style image injection generator

    Based on SkillCamo_cloze approach:
    1. Extract keywords from malicious script using cloze processor
    2. Replace keywords with ___1___, ___2___ blanks
    3. Generate keyword images using terminal-style renderer
    4. Rewrite SKILL.md using LLM with framing/instruction styles
    5. Iterate with feedback until bypass or max iterations
    """

    def __init__(
        self,
        config: GeneratorConfig,
        script_path: Path | None = None,
        cloze_config: ClozeConfig | None = None,
        bg_color: Tuple[int, int, int] = (30, 30, 30),
        text_color: Tuple[int, int, int] = (0, 255, 100),
        number_color: Tuple[int, int, int] = (255, 200, 50),
        harmful_sh_dir: Path | None = None,
    ):
        """
        Initialize Skillject Cloze Generator

        Args:
            config: Generator configuration
            script_path: Malicious script path
            cloze_config: Cloze processing configuration
            bg_color: Terminal image background color
            text_color: Terminal image text color
            number_color: Terminal image number color
            harmful_sh_dir: Directory for random script selection fallback
        """
        super().__init__(config, script_path, harmful_sh_dir or Path("data/harmful_sh"))

        self.cloze_config = cloze_config or ClozeConfig()
        self.bg_color = bg_color
        self.text_color = text_color
        self.number_color = number_color

        # Initialize components
        self.cloze_processor = ClozeProcessor(self.cloze_config)
        self.keyword_renderer = KeywordImageRenderer(
            bg_color=bg_color,
            text_color=text_color,
            number_color=number_color,
        )

        # State
        self._skill_context: SkillContext | None = None
        self._cloze_result: ClozeResult | None = None
        self._injector: ImageInjector | None = None
        self._image_filename = "keywords.png"
        self._insertion_hint: str = ""

    @classmethod
    def from_config_dict(cls, config_dict: dict) -> "SkillCamoClozeGenerator":
        """Create generator from configuration dictionary"""
        flat = _flatten_config(config_dict)

        script_path = (
            Path(flat.get("harmful_script_path", ""))
            if flat.get("harmful_script_path")
            else None
        )

        harmful_sh_dir = (
            Path(flat.get("harmful_sh_dir", "data/harmful_sh"))
            if flat.get("harmful_sh_dir")
            else Path("data/harmful_sh")
        )

        # Parse cloze config
        cloze_dict = flat.get("cloze_config", {})
        cloze_config = ClozeConfig(
            enabled=cloze_dict.get("enabled", True),
            max_blanks=cloze_dict.get("max_blanks", 5),
            blank_format=cloze_dict.get("blank_format", "___{index}___"),
            force_mask_egress=cloze_dict.get("force_mask_egress", False),
        )

        # Parse colors
        bg_color = tuple(flat.get("bg_color", [30, 30, 30]))
        text_color = tuple(flat.get("text_color", [0, 255, 100]))
        number_color = tuple(flat.get("number_color", [255, 200, 50]))

        # Build generator config
        base_config = GeneratorConfig(
            base_skill_path=Path(flat.get("base_skill_path", ".")),
            threat_type=flat.get("threat_type", "SkillCamo_cloze"),
            max_iterations=flat.get("max_iterations", 5),
            output_dir=Path(flat["output_dir"]) if flat.get("output_dir") else _default_output_dir(),
            llm_provider=flat.get("llm_provider", "openai"),
            llm_model=flat.get("llm_model", "gpt-4o-mini"),
            verbose=flat.get("verbose", True),
            harmful_script_path=script_path or Path(""),
            api_key=flat.get("api_key"),
            base_url=flat.get("base_url"),
            api_key_pool=flat.get("api_key_pool"),
        )

        return cls(
            config=base_config,
            script_path=script_path,
            cloze_config=cloze_config,
            bg_color=bg_color,
            text_color=text_color,
            number_color=number_color,
            harmful_sh_dir=harmful_sh_dir,
        )

    def _initialize(self) -> None:
        """Lazy initialization of components"""
        if self._skill_context is None:
            self.skill_analyzer = SkillAnalyzer(self.config.base_skill_path)
            self._skill_context = self.skill_analyzer.analyze()
            self._insertion_hint = self.skill_analyzer.suggest_insertion_point()
            logger.info(f"Analyzed skill: {len(self._skill_context.sections)} sections")

        if self._cloze_result is None:
            command = self._resolve_script().command
            self._cloze_result = self.cloze_processor.process(command, self.script_path)
            logger.info(
                f"Cloze result: masked='{self._cloze_result.masked_command[:60]}...', "
                f"keywords={self._cloze_result.keywords}"
            )

        if self._injector is None:
            self._injector = create_image_injector(
                base_skill_path=self.config.base_skill_path,
                config=self.config,
                bg_color=self.bg_color,
                text_color=self.text_color,
                number_color=self.number_color,
            )
            self.llm_advisor = LLMAdvisor(
                provider=self.config.llm_provider,
                model=self.config.llm_model,
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                api_key_pool=self.config.api_key_pool,
            )

    def _initial_rewrite(self, context: dict[str, Any] | None = None) -> str:
        result = self.llm_advisor.rewrite_with_cloze(
            skill_context=self._skill_context,
            cloze_result=self._cloze_result,
            image_filename=self._image_filename,
            insertion_hint=self._insertion_hint,
        )
        return self._ensure_cloze_code_block(result)

    def _feedback_rewrite(self, previous_md: str, compact_feedback: dict, context: dict[str, Any] | None = None) -> str:
        result = self.llm_advisor.rewrite_with_cloze_and_feedback(
            previous_skill_md=previous_md,
            cloze_result=self._cloze_result,
            compact_feedback=compact_feedback,
            image_filename=self._image_filename,
        )
        return self._ensure_cloze_code_block(result)

    def _ensure_cloze_code_block(self, skill_md: str) -> str:
        """Safety net: ensure cloze blanks survive the LLM rewrite.

        This is a Layer 3 fallback in case the LLMAdvisor auto-repair
        (Layer 2) also failed to preserve the code block.
        """
        if re.search(r"_{3,}\d+_{3,}", skill_md):
            return skill_md

        logger.error(
            "Cloze code block still missing after LLMAdvisor auto-repair — "
            "performing generator-level injection"
        )
        image_ref = f"![Keywords](resources/{self._image_filename})"
        code_block = f"\n```bash\n{self._cloze_result.masked_command}\n```\n"

        if image_ref in skill_md:
            return skill_md.replace(image_ref, image_ref + code_block)

        # Last resort: append before the last heading
        lines = skill_md.split("\n")
        insert_idx = len(lines)
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].startswith("##"):
                insert_idx = i
                break
        lines.insert(insert_idx, f"\n{image_ref}{code_block}")
        return "\n".join(lines)

    def _compute_compact_feedback(self, scan_result: dict) -> dict:
        return self.llm_advisor.analyze_scan_result(scan_result)

    def _deliver_skill(self, iteration: int, rewritten_skill_md: str) -> Path:
        skill_path = self._injector.inject_with_cloze(
            cloze_result=self._cloze_result,
            iteration=iteration,
            rewritten_skill_md=rewritten_skill_md,
            image_filename=self._image_filename,
        )
        logger.info(f"Generated cloze skill at: {skill_path}")
        return skill_path

    def _get_llm_advisor(self) -> LLMAdvisor:
        return self.llm_advisor

    def _get_detected_strategy_name(self) -> str:
        return "cloze_rewrite_with_feedback"

    def _get_detected_reason(self) -> str:
        return "Detected by scanner, will rewrite cloze SKILL.md using feedback"

    def _get_success_reason(self) -> str:
        return "Successfully bypassed detection with cloze injection"


def create_skill_camo_cloze_generator(
    base_skill_path: Path,
    script_path: Path,
    cloze_config: ClozeConfig | None = None,
    bg_color: Tuple[int, int, int] = (30, 30, 30),
    text_color: Tuple[int, int, int] = (0, 255, 100),
    number_color: Tuple[int, int, int] = (255, 200, 50),
    llm_provider: str = "openai",
    llm_model: str = "gpt-4o-mini",
    output_dir: Path = Path("outputs"),
) -> SkillCamoClozeGenerator:
    """Create SkillCamoClozeGenerator convenience function

    Args:
        base_skill_path: Base skill directory
        script_path: Malicious script path
        cloze_config: Cloze processing config
        bg_color: Terminal image background
        text_color: Terminal image text
        number_color: Terminal image numbers
        llm_provider: LLM provider
        llm_model: LLM model
        output_dir: Output directory

    Returns:
        Configured SkillCamoClozeGenerator
    """
    config = GeneratorConfig(
        base_skill_path=base_skill_path,
        llm_provider=llm_provider,
        llm_model=llm_model,
        output_dir=output_dir,
        harmful_script_path=script_path,
    )

    return SkillCamoClozeGenerator(
        config=config,
        script_path=script_path,
        cloze_config=cloze_config,
        bg_color=bg_color,
        text_color=text_color,
        number_color=number_color,
    )


# ============================================================================
# SkillCamoSplitGenerator - 完全独立于 SkillCamoClozeGenerator
# ============================================================================


class SkillCamoSplitGenerator(FeedbackDrivenGenerator):
    """
    SkillCamo split-style image injection generator

    Based on split approach:
    1. Split command at shell operator (|, <, >, >>, &&, ||, ;)
    2. Put first part in SKILL.md with image placeholder
    3. Put second part in the image
    4. Rewrite SKILL.md using LLM with framing/instruction styles
    5. Iterate with feedback until bypass or max iterations
    """

    def __init__(
        self,
        config: GeneratorConfig,
        script_path: Path | None = None,
        split_config: SplitConfig | None = None,
        bg_color: Tuple[int, int, int] = (30, 30, 30),
        text_color: Tuple[int, int, int] = (0, 255, 100),
        harmful_sh_dir: Path | None = None,
    ):
        """
        Initialize SkillCamoSplitGenerator

        Args:
            config: Generator configuration
            script_path: Malicious script path
            split_config: Split processing configuration
            bg_color: Terminal image background color
            text_color: Terminal image text color
            harmful_sh_dir: Directory for random script selection fallback
        """
        super().__init__(config, script_path, harmful_sh_dir or Path("data/harmful_sh"))

        self.split_config = split_config or SplitConfig()
        self.bg_color = bg_color
        self.text_color = text_color

        # Initialize components
        from .split import create_split_processor
        self.split_processor = create_split_processor(self.split_config)
        self.keyword_renderer = KeywordImageRenderer(
            bg_color=bg_color,
            text_color=text_color,
            number_color=(255, 200, 50),
        )

        # State
        self._skill_context: SkillContext | None = None
        self._split_result: SplitResult | None = None
        self._injector: ImageInjector | None = None
        self._image_filename = "split.png"
        self._insertion_hint: str = ""

    @classmethod
    def from_config_dict(cls, config_dict: dict) -> "SkillCamoSplitGenerator":
        """Create generator from configuration dictionary"""
        flat = _flatten_config(config_dict)

        script_path = (
            Path(flat.get("harmful_script_path", ""))
            if flat.get("harmful_script_path")
            else None
        )

        harmful_sh_dir = (
            Path(flat.get("harmful_sh_dir", "data/harmful_sh"))
            if flat.get("harmful_sh_dir")
            else Path("data/harmful_sh")
        )

        # Parse split config
        split_dict = flat.get("split_config", {})
        split_config = SplitConfig(
            enabled=split_dict.get("enabled", True),
            split_style=SplitStyle(split_dict.get("split_style", "semantic_operator")),
        )

        # Parse colors
        bg_color = tuple(flat.get("bg_color", [30, 30, 30]))
        text_color = tuple(flat.get("text_color", [0, 255, 100]))

        # Build generator config
        base_config = GeneratorConfig(
            base_skill_path=Path(flat.get("base_skill_path", ".")),
            threat_type=flat.get("threat_type", "SkillCamo_split"),
            max_iterations=flat.get("max_iterations", 5),
            output_dir=Path(flat["output_dir"]) if flat.get("output_dir") else _default_output_dir(),
            llm_provider=flat.get("llm_provider", "openai"),
            llm_model=flat.get("llm_model", "gpt-4o-mini"),
            verbose=flat.get("verbose", True),
            harmful_script_path=script_path or Path(""),
            api_key=flat.get("api_key"),
            base_url=flat.get("base_url"),
            api_key_pool=flat.get("api_key_pool"),
        )

        return cls(
            config=base_config,
            script_path=script_path,
            split_config=split_config,
            bg_color=bg_color,
            text_color=text_color,
            harmful_sh_dir=harmful_sh_dir,
        )

    def _initialize(self) -> None:
        """Lazy initialization of components"""
        if self._skill_context is None:
            self.skill_analyzer = SkillAnalyzer(self.config.base_skill_path)
            self._skill_context = self.skill_analyzer.analyze()
            self._insertion_hint = self.skill_analyzer.suggest_insertion_point()
            logger.info(f"Analyzed skill: {len(self._skill_context.sections)} sections")

        if self._split_result is None:
            command = self._resolve_script().command
            self._split_result = self.split_processor.process(command, self.script_path)
            logger.info(
                f"Split result: markdown='{self._split_result.markdown_command[:60]}...', "
                f"image_content='{self._split_result.image_content}'"
            )

        if self._injector is None:
            self._injector = create_image_injector(
                base_skill_path=self.config.base_skill_path,
                config=self.config,
                bg_color=self.bg_color,
                text_color=self.text_color,
                number_color=(255, 200, 50),
            )
            self.llm_advisor = LLMAdvisor(
                provider=self.config.llm_provider,
                model=self.config.llm_model,
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                api_key_pool=self.config.api_key_pool,
            )

    def _initial_rewrite(self, context: dict[str, Any] | None = None) -> str:
        result = self.llm_advisor.rewrite_with_split(
            skill_context=self._skill_context,
            split_result=self._split_result,
            image_filename=self._image_filename,
            insertion_hint=self._insertion_hint,
        )
        return self._ensure_split_code_block(result)

    def _feedback_rewrite(self, previous_md: str, compact_feedback: dict, context: dict[str, Any] | None = None) -> str:
        result = self.llm_advisor.rewrite_with_split_and_feedback(
            previous_skill_md=previous_md,
            split_result=self._split_result,
            compact_feedback=compact_feedback,
            image_filename=self._image_filename,
        )
        return self._ensure_split_code_block(result)

    def _ensure_split_code_block(self, skill_md: str) -> str:
        """Safety net: ensure split command code block survived the LLM rewrite.

        This is a Layer 3 fallback in case the LLMAdvisor auto-repair
        (Layer 2) also failed to preserve the code block.
        """
        image_ref = f"![cmd](resources/{self._image_filename})"
        bash_blocks = re.findall(r"```bash\s*\n(.*?)```", skill_md, re.DOTALL)
        for block in bash_blocks:
            if image_ref in block:
                return skill_md

        logger.error(
            "Split code block still missing after LLMAdvisor auto-repair — "
            "performing generator-level injection"
        )
        code_block = f"```bash\n{self._split_result.markdown_command}\n```"

        if image_ref in skill_md:
            return skill_md.replace(image_ref, code_block)

        # Last resort: append before the last heading
        lines = skill_md.split("\n")
        insert_idx = len(lines)
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].startswith("##"):
                insert_idx = i
                break
        lines.insert(insert_idx, f"\n{code_block}\n")
        return "\n".join(lines)

    def _compute_compact_feedback(self, scan_result: dict) -> dict:
        return self.llm_advisor.analyze_scan_result(scan_result)

    def _deliver_skill(self, iteration: int, rewritten_skill_md: str) -> Path:
        skill_path = self._injector.inject_with_split(
            split_result=self._split_result,
            iteration=iteration,
            rewritten_skill_md=rewritten_skill_md,
            image_filename=self._image_filename,
        )
        logger.info(f"Generated split skill at: {skill_path}")
        return skill_path

    def _get_llm_advisor(self) -> LLMAdvisor:
        return self.llm_advisor

    def _get_detected_strategy_name(self) -> str:
        return "split_rewrite_with_feedback"

    def _get_detected_reason(self) -> str:
        return "Detected by scanner, will rewrite split SKILL.md using feedback"

    def _get_success_reason(self) -> str:
        return "Successfully bypassed detection with split injection"


def create_skill_camo_split_generator(
    base_skill_path: Path,
    script_path: Path,
    split_config: SplitConfig | None = None,
    bg_color: Tuple[int, int, int] = (30, 30, 30),
    text_color: Tuple[int, int, int] = (0, 255, 100),
    llm_provider: str = "openai",
    llm_model: str = "gpt-4o-mini",
    output_dir: Path = Path("outputs"),
) -> SkillCamoSplitGenerator:
    """Create SkillCamoSplitGenerator convenience function

    Args:
        base_skill_path: Base skill directory
        script_path: Malicious script path
        split_config: Split processing config
        bg_color: Terminal image background
        text_color: Terminal image text
        llm_provider: LLM provider
        llm_model: LLM model
        output_dir: Output directory

    Returns:
        Configured SkillCamoSplitGenerator
    """
    config = GeneratorConfig(
        base_skill_path=base_skill_path,
        llm_provider=llm_provider,
        llm_model=llm_model,
        output_dir=output_dir,
        harmful_script_path=script_path,
    )

    return SkillCamoSplitGenerator(
        config=config,
        script_path=script_path,
        split_config=split_config,
        bg_color=bg_color,
        text_color=text_color,
    )
