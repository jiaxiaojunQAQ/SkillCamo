# Copyright 2026
#
# Generator factory and registry.

"""
Generator factory and registry for loading generators from configuration.
"""

import importlib
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class GeneratorRegistry:
    """
    生成器注册表

    管理所有可用的生成器。
    """

    _generators: dict[str, type] = {}

    @classmethod
    def register(cls, name: str, generator_class: type) -> None:
        """
        注册生成器

        Args:
            name: 生成器名称
            generator_class: 生成器类

        Raises:
            TypeError: 如果 generator_class 不是 BaseGenerator 的子类
        """
        if not (isinstance(generator_class, type) and issubclass(generator_class, BaseGenerator)):
            raise TypeError(
                f"Cannot register {generator_class}: must be a BaseGenerator subclass"
            )
        cls._generators[name] = generator_class
        logger.debug(f"Registered generator: {name}")

    @classmethod
    def get(cls, name: str) -> type | None:
        """获取生成器类"""
        return cls._generators.get(name)

    @classmethod
    def list_all(cls) -> list[str]:
        """列出所有已注册的生成器"""
        return list(cls._generators.keys())


def load_generator_from_config(
    name: str,
    config_dict: dict,
) -> Any:
    """
    从配置字典加载生成器

    Args:
        name: 生成器名称
        config_dict: 配置字典

    Returns:
        生成器实例

    Raises:
        ValueError: 如果生成器未找到或加载失败
    """
    # 检查是否已注册
    generator_class = GeneratorRegistry.get(name)
    if generator_class:
        return generator_class.from_config_dict(config_dict)

    # 尝试从类路径动态加载
    class_path = config_dict.get("class")
    if not class_path:
        raise ValueError(f"No class specified for generator: {name}")

    try:
        module_path, class_name = class_path.split(":")
        module = importlib.import_module(module_path)
        generator_class = getattr(module, class_name)

        # 注册以便下次使用
        GeneratorRegistry.register(name, generator_class)

        return generator_class.from_config_dict(config_dict)

    except Exception as e:
        raise ValueError(f"Failed to load generator '{name}': {e}") from e


def create_generator(
    name: str,
    base_skill_path: Path,
    **kwargs
) -> Any:
    """
    创建生成器实例的便捷函数

    Args:
        name: 生成器名称
        base_skill_path: 基础技能路径
        **kwargs: 额外配置参数

    Returns:
        生成器实例
    """
    config_dict = {
        "base_skill_path": str(base_skill_path),
        **kwargs
    }

    return load_generator_from_config(name, config_dict)


# Import generators and register them
from .base import BaseGenerator, GeneratorConfig, FeedbackAnalysis
from .feedback_driven import FeedbackDrivenGenerator
from .direct_scan import DirectScanGenerator
from .skillject import SkilljectGenerator

# Import skill camo generators
from .skill_camo.generator import (
    SkillCamoGenerator,
    SkillCamoClozeGenerator,
    SkillCamoSplitGenerator,
    SkillCamoReplaceGenerator,
)

# Register all generators
GeneratorRegistry.register("direct_scan", DirectScanGenerator)
GeneratorRegistry.register("skillject", SkilljectGenerator)
GeneratorRegistry.register("SkillCamo", SkillCamoGenerator)
GeneratorRegistry.register("SkillCamo_cloze", SkillCamoClozeGenerator)
GeneratorRegistry.register("SkillCamo_split", SkillCamoSplitGenerator)
GeneratorRegistry.register("SkillCamo_replace", SkillCamoReplaceGenerator)
