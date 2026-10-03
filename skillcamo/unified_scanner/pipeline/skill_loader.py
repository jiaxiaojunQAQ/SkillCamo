# Copyright 2026
#
# Skill loader for adversarial testing.

"""
Skill loader for reading and parsing existing skills.

Provides functionality to load skill directories into a structured format
for analysis and modification during adversarial testing.
"""

from __future__ import annotations

import frontmatter
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MAX_TEXT_FILE_BYTES = 100_000


def _read_text_tree(base_dir: Path, *, verbose: bool = False, label: str = "file") -> dict[str, str]:
    """Recursively read small, non-hidden text files under a directory."""
    files: dict[str, str] = {}
    if not base_dir.exists() or not base_dir.is_dir():
        return files

    for file_path in sorted(base_dir.rglob("*")):
        if not file_path.is_file():
            continue
        relative = file_path.relative_to(base_dir)
        if any(part.startswith(".") for part in relative.parts):
            continue
        try:
            if file_path.stat().st_size > MAX_TEXT_FILE_BYTES:
                logger.warning("Skipping large %s: %s", label, file_path)
                continue
            files[relative.as_posix()] = file_path.read_text(encoding="utf-8")
            if verbose:
                logger.info("Loaded %s: %s", label, relative.as_posix())
        except Exception as e:
            logger.warning(f"Failed to read {file_path.name}: {e}")
    return files


@dataclass
class SkillStructure:
    """
    解析后的skill结构

    包含skill的所有内容，便于分析和修改。
    """

    name: str
    description: str
    frontmatter: dict[str, Any]  # YAML frontmatter 原始数据
    instructions: str  # markdown 内容
    scripts: dict[str, str]  # 文件名 -> 内容
    other_files: dict[str, str]  # 其他文件
    resources: dict[str, str]  # resources/ 目录内容
    skill_path: Path = field(default_factory=Path)

    @property
    def has_scripts(self) -> bool:
        """是否有scripts目录"""
        return len(self.scripts) > 0

    @property
    def has_resources(self) -> bool:
        """是否有resources目录"""
        return len(self.resources) > 0

    def get_script_names(self) -> list[str]:
        """获取所有脚本文件名"""
        return list(self.scripts.keys())

    def get_file_summary(self) -> str:
        """获取文件摘要"""
        summary = f"Skill: {self.name}\n"
        summary += f"Description: {self.description}\n"
        summary += f"Scripts: {len(self.scripts)} files\n"
        if self.scripts:
            for name in self.scripts.keys():
                summary += f"  - {name}\n"
        summary += f"Other files: {len(self.other_files)} files\n"
        summary += f"Resources: {len(self.resources)} files\n"
        return summary


class SkillLoader:
    """
    Skill加载器

    读取和解析现有skill目录，支持标准的Agent Skill格式。
    """

    def __init__(self, verbose: bool = False):
        """
        初始化加载器

        Args:
            verbose: 是否输出详细日志（通过入口统一控制）
        """
        self.verbose = verbose

    def load(self, skill_path: Path) -> SkillStructure:
        """
        加载skill目录

        Args:
            skill_path: skill目录路径

        Returns:
            SkillStructure 对象
        """
        if not skill_path.exists():
            raise FileNotFoundError(f"Skill path not found: {skill_path}")

        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            # 尝试小写的 skill.md
            skill_md = skill_path / "skill.md"
            if not skill_md.exists():
                raise FileNotFoundError(f"SKILL.md not found in {skill_path}")

        # 1. 读取 SKILL.md
        with open(skill_md, encoding="utf-8") as f:
            post = frontmatter.load(f)

        frontmatter_data = post.metadata
        instructions = post.content

        # 2. 读取 scripts/ 目录
        scripts = _read_text_tree(skill_path / "scripts", verbose=self.verbose, label="script")

        # 3. 读取 resources/ 目录
        resources = _read_text_tree(skill_path / "resources", verbose=self.verbose, label="resource")

        # 4. 读取其他根目录文件（排除目录和特殊文件）
        other_files = {}
        for file in skill_path.glob("*"):
            if file.is_file():
                # 跳过 SKILL.md 和特殊文件
                if file.name in ["SKILL.md", "skill.md", "LICENSE.txt", "_expected.json"]:
                    continue
                # 跳过已处理的目录
                if file.name in ["scripts", "resources", "examples", "references", "assets"]:
                    continue
                # 跳过隐藏文件
                if file.name.startswith("."):
                    continue
                try:
                    # 限制文件大小（避免读取大文件）
                    if file.stat().st_size < MAX_TEXT_FILE_BYTES:
                        other_files[file.name] = file.read_text(encoding="utf-8")
                        if self.verbose:
                            logger.info(f"Loaded other file: {file.name}")
                except Exception as e:
                    logger.warning(f"Failed to read {file.name}: {e}")

        # 5. 读取安全审查相关的辅助目录。保留目录名前缀，避免与根文件重名。
        for dirname in ("examples", "references", "assets"):
            for relative, content in _read_text_tree(
                skill_path / dirname,
                verbose=self.verbose,
                label=dirname,
            ).items():
                other_files[f"{dirname}/{relative}"] = content

        return SkillStructure(
            name=frontmatter_data.get("name", skill_path.name),
            description=frontmatter_data.get("description", ""),
            frontmatter=frontmatter_data,
            instructions=instructions,
            scripts=scripts,
            other_files=other_files,
            resources=resources,
            skill_path=skill_path,
        )

    def load_multiple(self, skill_paths: list[Path]) -> dict[str, SkillStructure]:
        """
        批量加载多个skill

        Args:
            skill_paths: skill路径列表

        Returns:
            {skill_name: SkillStructure} 字典
        """
        skills = {}
        for path in skill_paths:
            try:
                structure = self.load(path)
                skills[structure.name] = structure
                logger.info(f"Loaded skill: {structure.name}")
            except Exception as e:
                logger.error(f"Failed to load {path}: {e}")
        return skills

    def discover_skills(self, base_dir: Path) -> list[Path]:
        """
        自动发现base_dir下的所有skill

        Args:
            base_dir: 基础目录

        Returns:
            skill路径列表
        """
        skills = []

        # 查找包含 SKILL.md 的目录
        for skill_md in base_dir.glob("**/SKILL.md"):
            skill_path = skill_md.parent
            # 跳过隐藏目录和特殊目录
            if any(part.startswith(".") for part in skill_path.parts):
                continue
            if "__pycache__" in skill_path.parts or "node_modules" in skill_path.parts:
                continue
            skills.append(skill_path)

        return sorted(skills)


# 便捷函数
def load_skill(skill_path: str | Path) -> SkillStructure:
    """
    便捷函数：加载单个skill

    Args:
        skill_path: skill路径

    Returns:
        SkillStructure 对象
    """
    loader = SkillLoader()
    return loader.load(Path(skill_path))


def discover_skills(base_dir: str | Path) -> list[Path]:
    """
    便捷函数：自动发现skills

    Args:
        base_dir: 基础目录

    Returns:
        skill路径列表
    """
    loader = SkillLoader()
    return loader.discover_skills(Path(base_dir))
