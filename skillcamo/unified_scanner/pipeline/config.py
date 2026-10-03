# Copyright 2026
#
# Configuration loader for adversarial framework.

"""
Configuration loader for adversarial framework.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..config import get_adversarial_defaults
from ..api_key_pool import ApiKeyPool

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class AdversarialConfig:
    """统一配置"""

    generators: dict[str, dict[str, Any]]
    available_scanners: list[str]  # 可用的扫描器名称列表
    generator: dict[str, dict[str, Any]]  # LLM provider 配置（供生成器使用）
    batch: dict[str, Any]  # 内部运行默认值；公开配置入口为 defaults.adversarial
    _config_path: Path = field(default_factory=lambda: Path("main.yaml"))
    _key_pools: dict[str, ApiKeyPool] = field(default_factory=dict)

    @classmethod
    def load(cls, config_path: Path | None = None) -> "AdversarialConfig":
        """
        加载配置文件

        支持两种模式：
        1. 通过 unified_scanner.config.load_yaml_config() 加载（支持 includes）
        2. 直接读取 YAML 文件（fallback）

        Args:
            config_path: 配置文件路径，默认为项目根目录的 main.yaml

        Returns:
            配置对象
        """
        if config_path is None:
            # 默认查找项目根目录的配置文件
            project_root = Path(__file__).parent.parent.parent.parent
            config_path = project_root / "config" / "main.yaml"

        if not config_path.exists():
            logger.warning(f"Config file not found: {config_path}, using fallback config")
            return cls._get_fallback_config()

        # 尝试使用统一配置加载器（支持 includes）
        try:
            from ..config import load_yaml_config
            data = load_yaml_config(config_path)
        except ImportError:
            if not YAML_AVAILABLE:
                logger.warning("PyYAML not installed, using fallback config")
                return cls._get_fallback_config()
            with open(config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

        return cls.from_dict(data, config_path=config_path)

    @classmethod
    def from_dict(cls, data: dict[str, Any], config_path: Path | None = None) -> "AdversarialConfig":
        """从已加载（且 includes 已合并）的配置字典构造。

        与 :meth:`load` 等价，但跳过磁盘读取——供已经持有 raw 配置字典的调用方
        复用，避免重复加载 YAML。
        """
        return cls(
            generators=data.get("generators", {}),
            available_scanners=data.get("available_scanners") or data.get("scanners", {}).get("enabled", []),
            generator=data.get("generator", {}),
            batch=get_adversarial_defaults(data),
            _config_path=config_path or Path("main.yaml"),
        )

    @classmethod
    def _get_fallback_config(cls) -> "AdversarialConfig":
        """获取回退配置"""
        return cls(
            generators={
                "SkillCamo": {
                    "name": "Skill Camo",
                    "class": "skillcamo.unified_scanner.generators.skill_camo:SkillCamoGenerator",
                }
            },
            available_scanners=[
                "scan_skill_auditor",
                "scan_cisco",
                "scan_hss",
                "scan_skill_vetter",
                "scan_skillfortify",
                "scan_skill_slowmist",
                "scan_execscan",
            ],
            generator={
                "anthropic": {"api_key_env": "ANTHROPIC_API_KEY"},
                "openai": {"api_key_env": "OPENAI_API_KEY"},
            },
            batch={},
        )

    def get_generator_config(self, name: str) -> dict[str, Any]:
        """获取生成器配置"""
        return self.generators.get(name, {})

    def get_llm_api_key(self, provider: str) -> str | None:
        """
        获取 LLM API 密钥

        Args:
            provider: 提供商名称 (anthropic, openai)

        Returns:
            API 密钥
        """
        import os

        if provider not in self.generator:
            return None

        env_var = self.generator[provider].get("api_key_env")
        if env_var:
            return os.environ.get(env_var)

        return None

    def get_llm_api_key_pool(self, provider: str) -> ApiKeyPool | None:
        """
        获取或创建 LLM API 密钥轮换池。

        优先级：
        1. generator.{provider}.api_keys（YAML 显式列表）
        2. generator.{provider}.api_key_env 发现编号环境变量（{ENV}_1, {ENV}_2, ...）

        结果按 provider 缓存，重复调用返回同一池实例。

        Args:
            provider: 提供商名称 (anthropic, openai)

        Returns:
            ApiKeyPool 实例，或 None（provider 未配置时）
        """
        if provider not in self.generator:
            return None

        # 返回缓存
        if provider in self._key_pools:
            return self._key_pools[provider]

        provider_cfg = self.generator[provider]

        # 优先使用 YAML 显式列表
        explicit_keys = provider_cfg.get("api_keys")
        if isinstance(explicit_keys, list) and explicit_keys:
            pool = ApiKeyPool.from_explicit_list(provider, explicit_keys)
            self._key_pools[provider] = pool
            return pool

        # 从环境变量发现编号 key
        env_var = provider_cfg.get("api_key_env")
        if env_var:
            try:
                pool = ApiKeyPool.from_env_pattern(provider, env_var)
                self._key_pools[provider] = pool
                return pool
            except ValueError:
                logger.debug(f"No API keys found for {provider} via env pattern")
                return None

        return None

    def get_llm_base_url(self, provider: str) -> str | None:
        """
        获取 LLM API base URL

        Args:
            provider: 提供商名称 (anthropic, openai)

        Returns:
            base URL，如果未配置则返回 None
        """
        import os

        if provider not in self.generator:
            return None

        env_var = self.generator[provider].get("base_url_env")
        if env_var:
            return os.environ.get(env_var)

        return None
