# Copyright 2026
#
# Batch configuration models for adversarial framework.

"""
Batch configuration models for adversarial framework.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import get_adversarial_defaults
from ..paths import PROJECT_ROOT


def resolve_project_root() -> Path:
    """解析项目根目录，优先使用 CWD（若含 pyproject.toml/.git），否则回退到内置 PROJECT_ROOT。

    Shared by validate-time and run-time path resolution so relative
    script/output paths in skill specs resolve identically in both layers.
    """
    cwd = Path.cwd()
    if (cwd / "pyproject.toml").exists() or (cwd / ".git").exists():
        return cwd
    return PROJECT_ROOT

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class SkillSpec:
    """Specification for a single skill test.

    支持多种配置方式：
    - 直接路径字符串: "./test_skill/docx"
    - 带选项的字典: {path: "./test_skill/docx", script: "./custom.sh"}
    - Glob 模式: {glob: "./test_skill/*"}
    """

    name: str | None = None
    path: Path | None = None
    glob: str | None = None
    script: Path | None = None
    generator: str | None = None
    max_iterations: int | None = None
    output_dir: Path | None = None
    # Cap a glob-expanded list to the first N matches (sorted, deterministic).
    # Handy for cheap validation runs without creating a subset directory.
    limit: int | None = None
    # Per-skill override of the generator's `config:` block (deep-merged over
    # the canonical config.generator.yaml block at orchestration time). Lets
    # one generator drive a baseline matrix from sibling profiles.
    generator_config: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: str | dict[str, Any]) -> "SkillSpec":
        """从字典或字符串创建 SkillSpec。

        Args:
            data: 字符串路径或配置字典

        Returns:
            SkillSpec 实例
        """
        if isinstance(data, str):
            path = Path(data)
            return cls(path=path, name=path.name)

        if "mode" in data:
            raise ValueError("Unsupported key 'mode'. Use 'generator' instead.")

        # 处理简写形式: {path: "./skill", script: "./script.sh"}
        path = data.get("path")
        glob_pattern = data.get("glob")
        script_path = data.get("script")
        gen = data.get("generator")
        max_iter = data.get("max_iterations")
        out_dir = data.get("output_dir")
        gen_config = data.get("generator_config")
        name = data.get("name")
        limit = data.get("limit")

        # 如果没有 name，使用路径的 basename
        if name is None and path:
            name = Path(path).name
        if name is None and glob_pattern:
            name = glob_pattern

        return cls(
            name=name,
            path=Path(path) if path else None,
            glob=glob_pattern,
            script=Path(script_path) if script_path else None,
            generator=gen,
            max_iterations=max_iter,
            output_dir=Path(out_dir) if out_dir else None,
            generator_config=gen_config if isinstance(gen_config, dict) else None,
            limit=int(limit) if limit is not None else None,
        )

    def is_valid(self) -> bool:
        """检查规格是否有效。"""
        return self.path is not None or self.glob is not None


@dataclass
class ReportConfig:
    """报告配置。"""

    format: str = "json"  # json, markdown, both
    per_skill: bool = True
    aggregate: bool = True
    verbose: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ReportConfig":
        """从字典创建 ReportConfig。"""
        if data is None:
            return cls()
        return cls(
            format=data.get("format", "json"),
            per_skill=data.get("per_skill", True),
            aggregate=data.get("aggregate", True),
            verbose=data.get("verbose", False),
        )


@dataclass
class BatchConfig:
    """批量执行配置。

    通过 BatchConfig.load() 从 YAML 文件加载，
    或通过 BatchConfig.from_profile() 从 profile 字典 + pipeline 默认值创建。
    """

    # 内部运行配置数据；公开配置入口为 defaults.adversarial
    batch: dict[str, Any]
    skills: list[SkillSpec]
    reports: ReportConfig
    _config_path: Path = field(default_factory=lambda: Path("config/main.yaml"))

    # 解析后的技能列表（展开 glob 后）
    _resolved_skills: list[SkillSpec] = field(default_factory=list)

    @classmethod
    def load(cls, config_path: Path) -> "BatchConfig":
        """加载并解析批量配置文件。

        Args:
            config_path: 统一配置文件路径 (main.yaml)

        Returns:
            BatchConfig 实例

        Raises:
            FileNotFoundError: 配置文件不存在
            ValueError: 配置文件格式错误
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        if not YAML_AVAILABLE:
            raise ImportError("PyYAML is required for batch configuration")

        try:
            from ..config import load_yaml_config

            data = load_yaml_config(config_path)
        except ImportError:
            with open(config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

        # 公开配置使用 defaults.adversarial；旧的 batch 仍兼容
        batch_data = get_adversarial_defaults(data)

        # 解析 skills
        skills_data = batch_data.get("skills", [])
        skills = []
        for skill_data in skills_data:
            spec = SkillSpec.from_dict(skill_data)
            if spec.is_valid():
                skills.append(spec)

        # 解析 reports
        reports = ReportConfig.from_dict(batch_data.get("reports"))

        config = cls(
            batch=batch_data,
            skills=skills,
            reports=reports,
            _config_path=config_path,
        )

        # 展开 glob 模式
        config._resolve_skills()

        return config

    @classmethod
    def from_profile(cls, profile: dict[str, Any], pipeline_defaults: dict[str, Any], config_path: Path) -> "BatchConfig":
        """从 profile 字典 + adversarial 默认值创建 BatchConfig。

        Args:
            profile:           profiles 列表中的一个 profile 条目
            pipeline_defaults: config.generator.yaml 的 defaults.adversarial 默认值
            config_path:       配置文件路径（用于解析相对路径）

        Returns:
            BatchConfig 实例
        """
        from ..config import deep_merge

        merged = deep_merge(pipeline_defaults, profile)

        skills_data = merged.get("skills", [])
        skills = []
        for skill_data in skills_data:
            spec = SkillSpec.from_dict(skill_data)
            if spec.is_valid():
                skills.append(spec)

        reports = ReportConfig.from_dict(merged.get("reports"))

        config = cls(
            batch=merged,
            skills=skills,
            reports=reports,
            _config_path=config_path,
        )
        config._resolve_skills()
        return config

    def _resolve_skills(self) -> None:
        """展开 glob 模式，生成最终的技能列表。"""
        resolved = []
        seen_paths = set()

        for spec in self.skills:
            if spec.glob:
                # 展开 glob 模式
                glob_path = Path(spec.glob)
                parent_dir = glob_path.parent
                pattern = glob_path.name

                # 使用 glob 查找匹配的目录
                matches = sorted(parent_dir.glob(pattern))

                # 可选 limit：取排序后的前 N 个（确定性，便于廉价验证跑）
                kept = 0
                for match_dir in matches:
                    if spec.limit is not None and kept >= spec.limit:
                        break
                    if match_dir.is_dir() and (match_dir / "SKILL.md").exists():
                        # 去重：检查路径是否已存在
                        if str(match_dir.resolve()) in seen_paths:
                            continue
                        seen_paths.add(str(match_dir.resolve()))

                        # 创建新的 SkillSpec，保留原始配置
                        new_spec = SkillSpec(
                            name=match_dir.name,
                            path=match_dir,
                            script=spec.script,
                            generator=spec.generator,
                            max_iterations=spec.max_iterations,
                            output_dir=spec.output_dir,
                            generator_config=spec.generator_config,
                        )
                        resolved.append(new_spec)
                        kept += 1
            elif spec.path:
                # 直接路径
                resolved_path = str(spec.path.resolve())
                if resolved_path not in seen_paths:
                    seen_paths.add(resolved_path)
                    resolved.append(spec)

        self._resolved_skills = resolved

    def get_resolved_skills(self) -> list[SkillSpec]:
        """获取解析后的技能列表。"""
        return self._resolved_skills

    def get_skill_config(
        self,
        spec: SkillSpec,
        base_dir: Path,
    ) -> dict[str, Any]:
        """合并全局配置和技能特定配置。

        Args:
            spec: 技能规格
            base_dir: 基础目录

        Returns:
            合并后的配置字典
        """
        config = {}

        # 从内部运行默认值复制
        config["script"] = Path(self.batch.get("script", "")) if self.batch.get("script") else None
        config["generator"] = self.batch.get("generator")
        config["max_iterations"] = self.batch.get("max_iterations")
        config["output_dir"] = Path(self.batch.get("output_dir")) if self.batch.get("output_dir") else None
        # 启用的扫描器列表
        config["enabled_scanners"] = self.batch.get("enabled_scanners", None)
        # profile 级 generator config 覆盖（deep-merge 在 orchestrator.from_config）
        config["generator_config"] = self.batch.get("generator_config")

        # 技能特定配置覆盖
        if spec.script:
            config["script"] = spec.script
        if spec.generator:
            config["generator"] = spec.generator
        if spec.max_iterations is not None:
            config["max_iterations"] = spec.max_iterations
        if spec.output_dir:
            config["output_dir"] = spec.output_dir
        if spec.generator_config is not None:
            config["generator_config"] = spec.generator_config

        # 解析相对路径
        if config["script"] and not config["script"].is_absolute():
            config["script"] = base_dir / config["script"]
        if config["output_dir"] is not None and not config["output_dir"].is_absolute():
            config["output_dir"] = base_dir / config["output_dir"]
        if config["generator"] == "direct_scan":
            config["max_iterations"] = 1

        return config

    def get_max_workers(self) -> int:
        """获取最大工作线程数。"""
        return self.batch.get("max_workers", 3)

    def validate(self, allowed_generators: set[str] | None = None) -> list[str]:
        """验证配置，返回错误列表。

        Returns:
            错误消息列表，空列表表示无错误
        """
        errors = []

        if not self._resolved_skills:
            errors.append("No valid skills found in configuration")
        if self.batch.get("mode") is not None:
            errors.append("Unsupported key 'mode' in adversarial defaults. Use 'generator' instead.")
        if self.batch.get("max_iterations") is None:
            errors.append("defaults.adversarial.max_iterations is required")
        if not self.batch.get("output_dir"):
            errors.append("defaults.adversarial.output_dir is required")

        # Base dir MUST match the runtime base (batch_orchestrator uses
        # resolve_project_root()); using _config_path.parent here made
        # relative script/output paths resolve differently at validate time
        # vs run time, so one of the two layers always failed.
        base_dir = resolve_project_root()

        for spec in self._resolved_skills:
            if spec.path and not spec.path.exists():
                errors.append(f"Skill path does not exist: {spec.path}")
            if spec.path and not (spec.path / "SKILL.md").exists():
                errors.append(f"SKILL.md not found in: {spec.path}")
            skill_config = self.get_skill_config(spec, base_dir)
            generator = skill_config.get("generator")
            if not generator:
                errors.append(f"Generator is required for skill: {spec.path}")
                continue
            if allowed_generators is not None:
                supported_generators = allowed_generators
            else:
                from ..generators import GeneratorRegistry
                supported_generators = set(GeneratorRegistry.list_all()) | {
                    "bash_script_drop", "image_drop",
                }
            if generator not in supported_generators:
                errors.append(f"Unsupported generator '{generator}' for skill: {spec.path}")
                continue
            if generator == "direct_scan":
                continue

            # Generators that load scripts from harmful_sh_dir (random by default) — script is optional
            _RANDOM_SCRIPT_GENERATORS = {"skillject",
                                         "SkillCamo", "SkillCamo_cloze", "SkillCamo_split",
                                         "SkillCamo_replace"}

            script_path = skill_config.get("script")
            if script_path is None:
                if generator not in _RANDOM_SCRIPT_GENERATORS:
                    errors.append(f"Script file is required for generator '{generator}': {spec.path}")
                continue
            if not script_path.exists():
                errors.append(f"Script file does not exist: {script_path}")

        return errors
