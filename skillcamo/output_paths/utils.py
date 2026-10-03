"""
输出路径工具函数 - 原子写入、目录创建等
"""

import json
import logging
import os
import uuid
from pathlib import Path
from threading import Lock
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)


def ensure_dir(path: Union[str, Path]) -> None:
    """
    确保目录存在，不存在则创建

    Args:
        path: 目录路径（文件或目录路径均可）
    """
    path = Path(path)
    # 如果传入的是文件路径，获取其父目录
    if path.suffix and "." in path.name:
        dir_path = path.parent
    else:
        dir_path = path
    dir_path.mkdir(parents=True, exist_ok=True)


def atomic_write_json(
    data: Any,
    path: Union[str, Path],
    lock: Optional[Lock] = None,
    indent: int = 2,
    ensure_ascii: bool = False,
) -> None:
    """
    原子写入 JSON 文件

    使用 temp 文件 + rename 模式，确保写入中途失败不会损坏原有文件

    Args:
        data: 要写入的数据（必须是 JSON 可序列化对象）
        path: 目标文件路径
        lock: 可选的线程锁（用于多线程场景）
        indent: JSON 缩进空格数
        ensure_ascii: 是否转义非 ASCII 字符

    Raises:
        IOError: 写入失败时抛出
    """
    path = Path(path)
    ensure_dir(path)

    # 生成临时文件
    temp_path = path.with_suffix(f".tmp.{uuid.uuid4().hex[:8]}")

    try:
        if lock:
            with lock:
                _write_json_to_file(
                    temp_path, data, indent=indent, ensure_ascii=ensure_ascii
                )
                temp_path.replace(path)
        else:
            _write_json_to_file(
                temp_path, data, indent=indent, ensure_ascii=ensure_ascii
            )
            temp_path.replace(path)
    except Exception as e:
        # 清理临时文件
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        logger.error(f"原子写入 JSON 失败: {path}, 错误: {e}")
        raise


def _write_json_to_file(
    path: Path, data: Any, indent: int = 2, ensure_ascii: bool = False
) -> None:
    """内部函数：写入 JSON 到文件"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)


def atomic_write_text(
    content: str,
    path: Union[str, Path],
    lock: Optional[Lock] = None,
) -> None:
    """
    原子写入文本文件

    Args:
        content: 要写入的文本内容
        path: 目标文件路径
        lock: 可选的线程锁

    Raises:
        IOError: 写入失败时抛出
    """
    path = Path(path)
    ensure_dir(path)

    temp_path = path.with_suffix(f".tmp.{uuid.uuid4().hex[:8]}")

    try:
        if lock:
            with lock:
                temp_path.write_text(content, encoding="utf-8")
                temp_path.replace(path)
        else:
            temp_path.write_text(content, encoding="utf-8")
            temp_path.replace(path)
    except Exception as e:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        logger.error(f"原子写入文本失败: {path}, 错误: {e}")
        raise


def atomic_write_bytes(
    content: bytes,
    path: Union[str, Path],
    lock: Optional[Lock] = None,
) -> None:
    """
    原子写入二进制文件

    Args:
        content: 要写入的二进制内容
        path: 目标文件路径
        lock: 可选的线程锁

    Raises:
        IOError: 写入失败时抛出
    """
    path = Path(path)
    ensure_dir(path)

    temp_path = path.with_suffix(f".tmp.{uuid.uuid4().hex[:8]}")

    try:
        if lock:
            with lock:
                temp_path.write_bytes(content)
                temp_path.replace(path)
        else:
            temp_path.write_bytes(content)
            temp_path.replace(path)
    except Exception as e:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        logger.error(f"原子写入二进制失败: {path}, 错误: {e}")
        raise


def build_output_filename(
    base_name: str,
    suffix: str,
    extension: str,
    timestamp: Optional[str] = None,
) -> str:
    """
    构建标准化的输出文件名

    Args:
        base_name: 基础名称（如 skill_name）
        suffix: 后缀（如 scanner 名称）
        extension: 扩展名（如 "json", "html"）
        timestamp: 可选时间戳（格式 YYYY-MM-DD_HH-MM-SS）

    Returns:
        格式化后的文件名

    Example:
        build_output_filename("my_skill", "scan_cisco", "json")
        # → "my_skill_scan_cisco.json"

        build_output_filename("my_skill", "scan_cisco", "json", "2026-04-09_14-30-00")
        # → "my_skill_scan_cisco_2026-04-09_14-30-00.json"
    """
    parts = [base_name, suffix]

    if timestamp:
        parts.append(timestamp)

    return f"{'_'.join(parts)}.{extension}"


def parse_experiment_path(path: Path) -> Optional[dict]:
    """
    从实验结果路径解析出实验上下文信息

    Args:
        path: 实验结果文件路径

    Returns:
        包含 timestamp, model, dataset, module, output_type 的字典，
        如果路径不符合预期格式则返回 None

    Example:
        path = Path("results/2026-04-09_14-30-00/claude-3-5-sonnet/malicious_skills/unified/json/scan_result.json")
        parse_experiment_path(path)
        # → {"timestamp": "2026-04-09_14-30-00", "model": "claude-3-5-sonnet", "dataset": "malicious_skills",
        #     "module": "unified", "output_type": "json", "filename": "scan_result.json"}
    """
    try:
        parts = path.parts
        root_index = None

        # 找到 "results" 目录位置
        for i, part in enumerate(parts):
            if part == "results" or part.endswith("_results"):
                root_index = i
                break

        if root_index is None or len(parts) < root_index + 4:
            return None

        # 解析路径结构: results/{timestamp}/{model}/{dataset}/{module}/{output_type}/{filename}
        result = {
            "timestamp": parts[root_index + 1],
            "model": parts[root_index + 2],
            "dataset": parts[root_index + 3],
        }

        # 可选：解析 module 和 output_type
        if len(parts) > root_index + 4:
            result["module"] = parts[root_index + 4]
        if len(parts) > root_index + 5:
            result["output_type"] = parts[root_index + 5]
        if len(parts) > root_index + 6:
            result["filename"] = parts[root_index + 6]

        return result

    except Exception:
        return None
