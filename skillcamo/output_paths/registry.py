"""
线程安全的路径注册表 - 管理输出路径分配

确保并发场景下不会产生路径冲突。
"""

import threading
from pathlib import Path
from typing import Dict, Optional, Tuple

from .config import ExperimentContext, OutputPathsConfig
from .utils import ensure_dir


class PathRegistry:
    """
    线程安全的路径注册表

    用于在并发场景下分配唯一的输出路径，避免多线程写入冲突。
    """

    def __init__(self, config: Optional[OutputPathsConfig] = None):
        """
        初始化路径注册表

        Args:
            config: 输出路径配置，如果为 None 则使用默认配置
        """
        self._config = config or OutputPathsConfig()
        self._lock = threading.Lock()
        self._allocated: Dict[str, Path] = {}
        self._seen_dirs: set = set()  # 缓存已创建的目录

    def resolve(
        self,
        module: str,
        output_type: str,
        filename: str,
        create_parents: bool = True,
    ) -> Path:
        """
        解析并注册输出路径（线程安全）

        Args:
            module: 模块名称（如 "unified", "scan_cisco"）
            output_type: 输出类型（如 "json", "html"）
            filename: 文件名
            create_parents: 是否创建父目录

        Returns:
            完整的输出路径
        """
        # 生成唯一键
        key = self._make_key(module, output_type, filename)

        with self._lock:
            if key not in self._allocated:
                path = self._config.get_output_path(module, output_type, filename)

                if create_parents:
                    dir_path = path.parent
                    if dir_path not in self._seen_dirs:
                        ensure_dir(dir_path)
                        self._seen_dirs.add(dir_path)

                self._allocated[key] = path

            return self._allocated[key]

    def resolve_with_context(
        self,
        context: ExperimentContext,
        module: str,
        output_type: str,
        filename: str,
        create_parents: bool = True,
    ) -> Path:
        """
        使用指定实验上下文解析输出路径（线程安全）

        Args:
            context: 实验上下文
            module: 模块名称
            output_type: 输出类型
            filename: 文件名
            create_parents: 是否创建父目录

        Returns:
            完整的输出路径
        """
        key = self._make_key(module, output_type, filename, context.timestamp)

        with self._lock:
            if key not in self._allocated:
                path = context.build_path(self._config.root, module, output_type, filename)

                if create_parents:
                    dir_path = path.parent
                    if dir_path not in self._seen_dirs:
                        ensure_dir(dir_path)
                        self._seen_dirs.add(dir_path)

                self._allocated[key] = path

            return self._allocated[key]

    def _make_key(
        self,
        module: str,
        output_type: str,
        filename: str,
        timestamp: Optional[str] = None,
    ) -> str:
        """
        生成唯一键

        Args:
            module: 模块名称
            output_type: 输出类型
            filename: 文件名
            timestamp: 可选时间戳

        Returns:
            唯一键字符串
        """
        if timestamp:
            return f"{timestamp}:{module}:{output_type}:{filename}"
        return f"{self._config.experiment.timestamp}:{module}:{output_type}:{filename}"

    def get_resolved_path(
        self, module: str, output_type: str, filename: str
    ) -> Optional[Path]:
        """
        获取已注册的路径（如果存在）

        Args:
            module: 模块名称
            output_type: 输出类型
            filename: 文件名

        Returns:
            如果已注册则返回路径，否则返回 None
        """
        key = self._make_key(module, output_type, filename)
        with self._lock:
            return self._allocated.get(key)

    def is_registered(
        self, module: str, output_type: str, filename: str
    ) -> bool:
        """
        检查路径是否已注册

        Args:
            module: 模块名称
            output_type: 输出类型
            filename: 文件名

        Returns:
            如果已注册则返回 True
        """
        return self.get_resolved_path(module, output_type, filename) is not None

    def clear(self) -> None:
        """
        清空所有已注册的路径（通常在新的实验开始时调用）
        """
        with self._lock:
            self._allocated.clear()
            self._seen_dirs.clear()

    @property
    def config(self) -> OutputPathsConfig:
        """获取当前配置"""
        return self._config

    def set_config(self, config: OutputPathsConfig) -> None:
        """
        更新配置

        Args:
            config: 新的输出路径配置
        """
        with self._lock:
            self._config = config
