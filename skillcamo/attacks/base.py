# Copyright 2026
#
# Base generator class for adversarial testing.

"""
Base generator class for adversarial skill testing.

All generators must inherit from BaseGenerator and implement
the required methods.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


def strip_markdown_fences(text: str) -> str:
    """Remove wrapping markdown code fences (```json / ```markdown / ```) from LLM output."""
    text = text.strip()
    text = re.sub(r"^```\w*\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _default_output_dir() -> Path:
    from skillcamo.output_paths import get_default_output_root
    return get_default_output_root()


def _flatten_config(config_dict: dict) -> dict:
    """将嵌套的 config: 字典合并到顶层（顶层 key 优先）。

    YAML 中每个 generator 的配置格式为：
        generators:
          SkillCamo:
            config:
              llm_model: "gpt-5-mini"

    此函数将 config: 子字典的值提升到顶层，使得 from_config_dict()
    可以统一从顶层读取所有字段。如果顶层和嵌套 config: 有同名 key，
    顶层值优先（保证 CLI 参数可覆盖 YAML 配置）。
    """
    flat = dict(config_dict)
    nested = flat.pop("config", {})
    if isinstance(nested, dict):
        for k, v in nested.items():
            flat.setdefault(k, v)
    return flat


@dataclass
class GeneratorConfig:
    """生成器配置基类"""

    base_skill_path: Path
    threat_type: str = "command_injection"
    max_iterations: int = 5
    output_dir: Path = field(default_factory=lambda: _default_output_dir())
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    verbose: bool = True
    api_key: str | None = None
    base_url: str | None = None
    harmful_script_path: Path = field(default_factory=lambda: Path(""))
    api_key_pool: Any = None  # ApiKeyPool | None, using Any to avoid circular import

    _iteration: int = 0
    _iteration_count: int = 0

    @property
    def iteration_count(self) -> int:
        return self._iteration_count

    def increment_iteration(self) -> None:
        self._iteration_count += 1

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


@dataclass
class GenerationResult:
    """单次生成结果"""

    iteration: int
    timestamp: datetime
    skill_path: Path
    detected: bool
    scan_result: dict[str, Any]
    analysis: dict[str, Any]  # 生成器的反馈分析
    notes: str = ""


@dataclass
class FeedbackAnalysis:
    """analyze_feedback() 的标准化返回类型。"""

    detected: bool
    strategy: str
    reason: str
    next_action: str  # "success" | "continue" | "adjust_strategy" | "stop"

    # 可选字段：需要反馈上下文的生成器使用
    compact_feedback: dict[str, Any] | None = None
    reduced_scan_result: dict[str, Any] | None = None
    script_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典，仅包含非 None 的可选字段。"""
        d: dict[str, Any] = {
            "detected": self.detected,
            "strategy": self.strategy,
            "reason": self.reason,
            "next_action": self.next_action,
        }
        if self.compact_feedback is not None:
            d["compact_feedback"] = self.compact_feedback
        if self.reduced_scan_result is not None:
            d["reduced_scan_result"] = self.reduced_scan_result
        if self.script_path is not None:
            d["script_path"] = self.script_path
        return d


class LLMClient:
    """LLM Client Protocol.

    Stores credentials (api_key, base_url, api_key_pool) and lazily creates
    an OpenAI-compatible client instance via ``get_or_create_client()``.
    Each generator owns one ``LLMClient`` — no shared mutable state across
    generator instances.
    """

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        base_url: str | None = None,
        api_key_pool: Any = None,
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.api_key_pool = api_key_pool  # ApiKeyPool | None
        self._client: Any = None

    def get_next_api_key(self) -> str | None:
        """Return the next API key from the pool, or the fixed key."""
        if self.api_key_pool:
            return self.api_key_pool.get_next_key()
        return self.api_key

    def get_or_create_client(self) -> Any:
        """Return an OpenAI-compatible client.

        Uses a shared connection pool keyed by (provider, api_key, base_url).
        """
        if self._client is not None:
            return self._client
        try:
            from .llm_compat import get_or_create_client
        except ImportError:
            from llm_compat import get_or_create_client
        self._client = get_or_create_client(
            self.provider,
            api_key=self.get_next_api_key(),
            base_url=self.base_url,
            use_pool=True,
        )
        return self._client


class BaseGenerator(ABC):
    """
    生成器基类

    所有生成器必须继承此类并实现抽象方法。
    """

    def __init__(self, config: GeneratorConfig):
        """
        初始化生成器

        Args:
            config: 生成器配置
        """
        self.config = config
        self._iteration: int = 0
        self._iteration_count: int = 0
        self._initialized: bool = False

    def _initialize(self) -> None:
        """Ensure the generator is initialized.

        Increments the iteration counter on every call. Subclasses that
        override this method MUST call ``super()._initialize()`` to
        maintain the counter correctly.
        """
        self._iteration_count += 1
        self._iteration = self._iteration_count
        self.config.increment_iteration()

    @classmethod
    def from_config_dict(cls, config_dict: dict) -> "BaseGenerator":
        """
        从配置字典创建生成器

        Args:
            config_dict: 配置字典（从 YAML 加载）

        Returns:
            生成器实例
        """
        flat = _flatten_config(config_dict)

        # 提取通用配置
        base_config = GeneratorConfig(
            base_skill_path=Path(flat.get("base_skill_path", ".")),
            threat_type=flat.get("threat_type", "command_injection"),
            max_iterations=flat.get("max_iterations", 5),
            output_dir=Path(flat["output_dir"]) if flat.get("output_dir") else _default_output_dir(),
            llm_provider=flat.get("llm_provider", "openai"),
            llm_model=flat.get("llm_model", "gpt-4o-mini"),
            verbose=flat.get("verbose", True),
            api_key=flat.get("api_key"),
            base_url=flat.get("base_url"),
            api_key_pool=flat.get("api_key_pool"),
        )

        # 收集子类特定配置（排除已被 GeneratorConfig 消费的 key）
        consumed = {
            "base_skill_path", "threat_type", "max_iterations", "output_dir",
            "llm_provider", "llm_model", "verbose",
            "harmful_script_path", "class", "name", "description",
            "api_key", "base_url", "api_key_pool",
        }
        extra = {k: v for k, v in flat.items() if k not in consumed}

        return cls(base_config, **extra)

    @abstractmethod
    def generate(
        self,
        iteration: int,
        feedback: dict[str, Any] | None = None,
        *,
        context: dict[str, Any] | None = None,
    ) -> Path:
        """
        生成恶意技能

        Args:
            iteration: 当前迭代次数
            feedback: 上一轮的扫描反馈
            context: 额外的上下文信息（如 finalized_prompt），由调用方从上层传下来

        Returns:
            生成的技能路径
        """
        pass

    @abstractmethod
    def analyze_feedback(self, feedback: dict[str, Any]) -> dict[str, Any]:
        """
        分析扫描反馈，决定下一步策略

        Args:
            feedback: 扫描反馈，包含:
                - scan_result: 完整的扫描结果
                - detected: bool 值，表示是否被检测到（应直接使用此值）

        Returns:
            分析结果字典，包含:
            - detected: 是否被检测到（应与 feedback["detected"] 一致）
            - strategy: 下一步策略（仅注入类生成器需要）
            - reason: 原因说明
            - next_action: 下一步动作
        """
        pass

    def validate_config(self) -> list[str]:
        """
        验证配置是否有效

        Returns:
            错误信息列表，空列表表示配置有效
        """
        errors = []

        if not self.config.base_skill_path.exists():
            errors.append(f"Base skill path not found: {self.config.base_skill_path}")

        return errors


class BaseGeneratorWithScript(BaseGenerator):
    """
    带脚本文件的生成器基类

    用于需要从脚本文件读取恶意命令的生成器。
    提供统一的脚本选取方法 _resolve_script()。
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
            harmful_sh_dir: 有害脚本目录（随机选择时使用）
        """
        super().__init__(config)
        self.script_path = script_path
        self.harmful_sh_dir = harmful_sh_dir
        self._script_result = None  # ScriptResult 缓存
        if script_path is not None and script_path.is_file():
            self.config.harmful_script_path = script_path

    def _resolve_script(self):
        """统一脚本选取：指定路径 > config 路径 > 随机选择。

        结果缓存，多次调用返回同一结果。

        Returns:
            ScriptResult(path, command)
        """
        if self._script_result is not None:
            return self._script_result

        from .skill_camo.script_loader import HarmfulScriptLoader, ScriptResult

        loader = HarmfulScriptLoader(self.harmful_sh_dir)

        if self.script_path and self.script_path.is_file():
            try:
                result = loader.load_script_from_path(self.script_path)
            except (ValueError, UnicodeDecodeError):
                # 非脚本文件（如图片）：仅返回路径，命令为空
                result = ScriptResult(path=self.script_path, command="")
        elif (
            self.config.harmful_script_path
            and self.config.harmful_script_path.name
            and self.config.harmful_script_path.is_file()
        ):
            try:
                result = loader.load_script_from_path(self.config.harmful_script_path)
            except (ValueError, UnicodeDecodeError):
                result = ScriptResult(path=self.config.harmful_script_path, command="")
        else:
            result = loader.load_random_script()

        self.script_path = result.path
        self.config.harmful_script_path = result.path
        self._script_result = result
        return result

    @classmethod
    def from_config_dict(cls, config_dict: dict) -> "BaseGeneratorWithScript":
        """从配置字典创建生成器"""
        flat = _flatten_config(config_dict)

        script_path = Path(flat.get("harmful_script_path", "")) if flat.get("harmful_script_path") else None
        base_config = GeneratorConfig(
            base_skill_path=Path(flat.get("base_skill_path", ".")),
            threat_type=flat.get("threat_type", "command_injection"),
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

        harmful_sh_dir = Path(flat["harmful_sh_dir"]) if flat.get("harmful_sh_dir") else None

        # 收集子类特定配置
        consumed = {
            "base_skill_path", "threat_type", "max_iterations", "output_dir",
            "llm_provider", "llm_model", "verbose",
            "harmful_script_path", "harmful_sh_dir", "class", "name", "description",
            "api_key", "base_url", "api_key_pool",
        }
        extra = {k: v for k, v in flat.items() if k not in consumed}

        return cls(base_config, script_path=script_path, harmful_sh_dir=harmful_sh_dir, **extra)
