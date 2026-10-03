"""
输出路径配置模块 - 集中管理所有扫描器输出路径

实验结果按 {timestamp}/{model}/{dataset}/ 结构组织：

    results/
    ├── {timestamp}/                    # 2026-04-09_14-30-00/
    │   ├── {model}/                   # claude-3-5-sonnet/
    │   │   └── {dataset}/             # malicious_skills/
    │   │       ├── unified/
    │   │       ├── scan_cisco/
    │   │       ├── virustotal/
    │   │       └── ...

使用示例:
    from output_paths import OutputPathsConfig, ExperimentContext, PathRegistry
    from output_paths import atomic_write_json, ensure_dir

    # 方式1: 创建实验配置
    config = OutputPathsConfig.create(
        model="claude-3-5-sonnet",
        dataset="malicious_skills",
        experiment_name="baseline"
    )

    # 方式2: 使用默认配置（向后兼容）
    config = OutputPathsConfig()

    # 获取输出路径
    path = config.get_output_path("unified", "json", "scan_result.json")
    # → results/2026-04-09_14-30-00/claude-3-5-sonnet/malicious_skills/unified/json/scan_result.json

    # 线程安全的路径注册
    registry = PathRegistry(config)
    path = registry.resolve("scan_cisco", "json", "report.json")
    ensure_dir(path)
    atomic_write_json(data, path)
"""

from .config import (
    DEFAULT_MODULE,
    OUTPUT_TYPES,
    ExperimentContext,
    OutputPathsConfig,
    get_default_output_root,
)
from .registry import PathRegistry
from .utils import (
    atomic_write_bytes,
    atomic_write_json,
    atomic_write_text,
    build_output_filename,
    ensure_dir,
    parse_experiment_path,
)

__all__ = [
    # 配置类
    "ExperimentContext",
    "OutputPathsConfig",
    # 路径注册表
    "PathRegistry",
    # 工具函数
    "ensure_dir",
    "atomic_write_json",
    "atomic_write_text",
    "atomic_write_bytes",
    "build_output_filename",
    "parse_experiment_path",
    # 常量
    "DEFAULT_MODULE",
    "OUTPUT_TYPES",
    # 默认路径
    "get_default_output_root",
]
