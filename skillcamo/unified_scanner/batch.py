"""批量扫描目标发现与并行执行。"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

try:
    from .result_builder import build_batch_result
except ImportError:
    from result_builder import build_batch_result  # type: ignore[import-not-found,no-redef]

logger = logging.getLogger(__name__)


def discover_skill_paths(
    directory: str | Path,
    *,
    recursive: bool = False,
    pattern: str = "SKILL.md",
) -> list[Path]:
    """发现包含 skill 标识文件的目录。"""
    directory = Path(directory)
    if recursive:
        return [skill_file.parent for skill_file in directory.rglob(pattern)]

    return [
        item for item in directory.iterdir()
        if item.is_dir() and (item / pattern).exists()
    ]


def scan_batch(
    skill_paths: list[str | Path],
    *,
    scan_one: Callable[[str | Path], dict[str, Any]],
    max_skill_workers: int = 3,
) -> list[dict[str, Any]]:
    """并行扫描多个 skill。

    Args:
        skill_paths: 要扫描的技能路径列表
        scan_one: 单 skill 扫描回调
        max_skill_workers: skill 级最大并发数

    Returns:
        与 skill_paths 等长的结果列表，保持顺序一致
    """
    if not skill_paths:
        return []

    total = len(skill_paths)

    if total == 1:
        logger.info(f"[batch] [1/1] {Path(skill_paths[0]).name}")
        return [scan_one(skill_paths[0])]

    results: list[dict[str, Any] | None] = [None] * total

    with ThreadPoolExecutor(max_workers=max_skill_workers) as executor:
        future_to_idx = {
            executor.submit(scan_one, path): i
            for i, path in enumerate(skill_paths)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            skill_path = skill_paths[idx]
            try:
                results[idx] = future.result()
                logger.info(f"[batch] [{idx + 1}/{total}] {Path(skill_path).name}")
            except Exception as e:
                logger.error(f"[batch] [{idx + 1}/{total}] {Path(skill_path).name}: {e}")
                results[idx] = {"error": str(e)}

    return results


def scan_all(
    skill_paths: list[str | Path],
    *,
    scan_one: Callable[[str | Path], dict[str, Any]],
    max_skill_workers: int = 3,
) -> dict[str, Any]:
    """扫描多个显式路径。"""
    results = scan_batch(
        skill_paths,
        scan_one=scan_one,
        max_skill_workers=max_skill_workers,
    )
    return build_batch_result(results, target_type="batch")


def scan_directory(
    directory: str | Path,
    *,
    recursive: bool = False,
    pattern: str = "SKILL.md",
    scan_one: Callable[[Path], dict[str, Any]],
    max_skill_workers: int = 3,
) -> dict[str, Any]:
    """发现并扫描目录中的 skill。"""
    directory = Path(directory)
    skill_paths = discover_skill_paths(directory, recursive=recursive, pattern=pattern)
    results = scan_batch(
        skill_paths,
        scan_one=scan_one,
        max_skill_workers=max_skill_workers,
    )
    return build_batch_result(
        results,
        target_type="directory",
        target_path=directory,
    )
