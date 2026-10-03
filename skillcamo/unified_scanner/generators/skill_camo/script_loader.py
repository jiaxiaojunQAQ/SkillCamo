# Copyright 2026
#
# Harmful script loader for dynamic command loading.

"""
HarmfulScriptLoader - dynamically loads malicious commands from data/harmful_sh/.

This class provides a unified interface for generators to load commands
from the harmful_sh directory, supporting both random selection and
named script loading.
"""

from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger(__name__)


class ScriptResult(NamedTuple):
    """Result of loading a script"""
    path: Path
    command: str


class HarmfulScriptLoader:
    """
    从 data/harmful_sh/ 目录动态加载脚本

    提供统一的脚本加载接口，支持：
    - 随机选择脚本
    - 按名称加载脚本
    - 列出可用脚本
    """

    DEFAULT_HARMFUL_SH = Path("data/harmful_sh")

    def __init__(self, harmful_sh_dir: Path | None = None):
        """
        初始化加载器

        Args:
            harmful_sh_dir: 有害脚本目录路径，默认为 data/harmful_sh
        """
        self.harmful_sh_dir = self._resolve_dir(harmful_sh_dir)

    def _resolve_dir(self, dir_path: Path | None) -> Path:
        """解析目录路径，支持相对路径和绝对路径"""
        if dir_path is None:
            return self.DEFAULT_HARMFUL_SH
        if dir_path.is_absolute():
            return dir_path
        # 相对路径基于项目根目录
        return Path(__file__).parent.parent.parent.parent.parent / dir_path

    def list_available_scripts(self) -> list[Path]:
        """
        列出所有可用的 .sh 脚本

        Returns:
            脚本路径列表
        """
        if not self.harmful_sh_dir.exists():
            logger.warning(f"harmful_sh directory not found: {self.harmful_sh_dir}")
            return []

        scripts = [
            p for p in self.harmful_sh_dir.iterdir()
            if p.is_file() and p.suffix == ".sh"
        ]
        logger.info(f"Found {len(scripts)} scripts in {self.harmful_sh_dir}")
        return scripts

    def load_random_script(self) -> ScriptResult:
        """
        随机选择一个脚本并返回其第一条命令

        Returns:
            ScriptResult (path, command)

        Raises:
            ValueError: 如果没有可用脚本
        """
        scripts = self.list_available_scripts()
        if not scripts:
            raise ValueError(f"No scripts found in {self.harmful_sh_dir}")

        selected = random.choice(scripts)
        command = self.load_command(selected)
        logger.info(f"Randomly selected script: {selected.name}")
        return ScriptResult(path=selected, command=command)

    def load_script_by_name(self, name: str) -> ScriptResult:
        """
        按名称加载脚本（不含扩展名）

        Args:
            name: 脚本名称（不含 .sh 扩展名）

        Returns:
            ScriptResult (path, command)

        Raises:
            ValueError: 如果脚本不存在
        """
        script_path = self.harmful_sh_dir / f"{name}.sh"
        if not script_path.exists():
            raise ValueError(f"Script not found: {script_path}")

        command = self.load_command(script_path)
        logger.info(f"Loaded script by name: {script_path.name}")
        return ScriptResult(path=script_path, command=command)

    @staticmethod
    def load_command(script_path: Path) -> str:
        """
        从脚本文件加载第一条有效命令

        Args:
            script_path: 脚本文件路径

        Returns:
            第一条非注释、非空行的命令
        """
        content = script_path.read_text(encoding="utf-8")

        for line in content.split("\n"):
            line = line.strip()
            # 跳过注释、shebang 和空行
            if not line or line.startswith("#") or line.startswith("!"):
                continue
            return line

        raise ValueError(f"No command found in {script_path}")

    def load_script_from_path(self, script_path: Path) -> ScriptResult:
        """
        从指定路径加载脚本（不要求文件在 harmful_sh_dir 内）

        Args:
            script_path: 脚本文件路径

        Returns:
            ScriptResult (path, command)

        Raises:
            ValueError: 如果文件不存在
        """
        if not script_path.is_file():
            raise ValueError(f"Script not found: {script_path}")
        command = self.load_command(script_path)
        logger.info(f"Loaded script from path: {script_path.name}")
        return ScriptResult(path=script_path, command=command)


# 全局默认实例（延迟初始化）
_default_loader: HarmfulScriptLoader | None = None


def get_default_loader() -> HarmfulScriptLoader:
    """获取全局默认加载器"""
    global _default_loader
    if _default_loader is None:
        _default_loader = HarmfulScriptLoader()
    return _default_loader
