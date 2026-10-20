"""
输出路径配置模块 - 集中管理所有扫描器输出路径

实验结果按 {timestamp}/{model}/{dataset}/ 结构组织，方便追溯多次实验。

使用示例:
    from output_paths import OutputPathsConfig, ExperimentContext

    # 创建实验上下文（自动带时间戳）
    config = OutputPathsConfig.create(
        model="claude-3-5-sonnet",
        dataset="malicious_skills",
        experiment_name="baseline_run"
    )

    # 获取输出路径
    json_path = config.get_output_path("unified", "json", "scan_result.json")
    # → results/2026-04-09_14-30-00/claude-3-5-sonnet/malicious_skills/unified/json/scan_result.json
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


def get_default_output_root() -> Path:
    """获取默认输出根目录（项目根/outputs），基于 paths.PROJECT_ROOT 计算。"""
    from skillcamo.framework.paths import PROJECT_ROOT
    return PROJECT_ROOT / "outputs"


# 默认模块名称
DEFAULT_MODULE = "default"

# 支持的输出类型
OUTPUT_TYPES = ["json", "html", "markdown", "sarif", "logs", "temp", "raw"]


@dataclass
class ExperimentContext:
    """实验上下文 - 包含时间戳、模型、数据集信息"""

    timestamp: str  # 自动生成: 2026-04-09_14-30-00
    model: str  # 如 "claude-3-5-sonnet"
    dataset: str  # 如 "malicious_skills"
    experiment_name: Optional[str] = None  # 可选实验名称

    @classmethod
    def create(
        cls, model: str, dataset: str, experiment_name: Optional[str] = None
    ) -> "ExperimentContext":
        """
        创建实验上下文，自动生成时间戳

        Args:
            model: 模型名称（如 "claude-3-5-sonnet"）
            dataset: 数据集名称（如 "malicious_skills"）
            experiment_name: 可选实验名称

        Returns:
            ExperimentContext 实例
        """
        return cls(
            timestamp=datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
            model=cls._sanitize(model),
            dataset=cls._sanitize(dataset),
            experiment_name=cls._sanitize(experiment_name) if experiment_name else None,
        )

    @staticmethod
    def _sanitize(name: str) -> str:
        """
        清理路径中的非法字符

        Args:
            name: 原始名称

        Returns:
            清理后的名称
        """
        if not name:
            return "unknown"
        # 替换路径非法字符
        for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
            name = name.replace(char, "_")
        return name

    def build_path(
        self, root: Path, module: str, output_type: str, filename: str
    ) -> Path:
        """
        构建完整输出路径

        Args:
            root: 根目录（如 "results"）
            module: 模块名称（如 "unified", "scan_cisco"）
            output_type: 输出类型（如 "json", "html"）
            filename: 文件名（如 "scan_result.json"）

        Returns:
            完整的输出路径
        """
        path_parts = [root, self.timestamp, self.model, self.dataset]

        if self.experiment_name:
            path_parts.append(self.experiment_name)

        path_parts.extend([module, output_type, filename])

        return Path(*path_parts)

    @classmethod
    def default(cls) -> "ExperimentContext":
        """
        创建默认上下文（用于向后兼容）

        Returns:
            使用 "default" 作为 model 和 dataset 的上下文
        """
        return cls(
            timestamp="default",
            model="default",
            dataset="default",
            experiment_name=None,
        )


@dataclass
class OutputPathsConfig:
    """输出路径配置主类"""

    root: Path = field(default_factory=get_default_output_root)  # 默认 {PROJECT_ROOT}/outputs
    experiment: ExperimentContext = field(
        default_factory=ExperimentContext.default
    )  # 实验上下文

    @classmethod
    def create(
        cls,
        model: str,
        dataset: str,
        experiment_name: Optional[str] = None,
        root: Optional[Path] = None,
    ) -> "OutputPathsConfig":
        """
        创建配置，自动生成时间戳

        Args:
            model: 模型名称
            dataset: 数据集名称
            experiment_name: 可选实验名称
            root: 可选根目录（默认 "results"）

        Returns:
            OutputPathsConfig 实例
        """
        return cls(
            root=root or get_default_output_root(),
            experiment=ExperimentContext.create(model, dataset, experiment_name),
        )

    def get_output_path(
        self, module: str, output_type: str, filename: str
    ) -> Path:
        """
        获取输出路径（自动包含 timestamp/model/dataset）

        Args:
            module: 模块名称（如 "unified", "scan_cisco"）
            output_type: 输出类型（如 "json", "html"）
            filename: 文件名

        Returns:
            完整的输出路径
        """
        return self.experiment.build_path(self.root, module, output_type, filename)

    def get_module_dir(self, module: str, output_type: str) -> Path:
        """
        获取模块输出目录（不含文件名）

        Args:
            module: 模块名称
            output_type: 输出类型

        Returns:
            模块输出目录路径
        """
        return self.experiment.build_path(self.root, module, output_type, "")
