"""
失败技能管理模块

记录和管理扫描失败的技能，支持重试功能。

使用 OutputPathsConfig 的示例:
    from output_paths import OutputPathsConfig
    from unified_scanner.failed_skills_manager import FailedSkillsManager

    config = OutputPathsConfig.create("claude-3-5-sonnet", "malicious_skills")
    manager = FailedSkillsManager.from_config(config, "unified", "json")
"""
from __future__ import annotations

import json
import logging
import uuid
import warnings
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from output_paths import OutputPathsConfig

logger = logging.getLogger(__name__)


class FailedSkillsManager:
    """
    失败技能管理器

    记录扫描失败的技能，保存已成功的结果用于后续选择性重试。
    """

    VERSION = "1.0"

    def __init__(
        self,
        file_path: str | Path,
        *,
        _warn_deprecated: bool = True,
    ):
        """
        初始化失败技能管理器

        Args:
            file_path: 失败技能记录文件路径（不建议使用，请使用 from_config）
        """
        if _warn_deprecated:
            warnings.warn(
                "直接传递 file_path 已废弃，请使用 from_config() 方法",
                DeprecationWarning,
                stacklevel=2,
            )
        self.file_path = Path(file_path)
        self._lock = Lock()

        # 数据结构
        self._data: dict[str, Any] = {
            "version": self.VERSION,
            "created_at": None,
            "updated_at": None,
            "stats": {
                "total_failed": 0,
                "total_retried": 0,
                "total_succeeded": 0,
                "total_still_failed": 0,
            },
            "entries": {},  # skill_path -> entry
        }

        # 加载已有数据
        self._load()

    @classmethod
    def from_config(
        cls,
        config: "OutputPathsConfig",  # type: ignore[name-defined]
        module: str = "unified",
        output_type: str = "json",
        filename: str = "failed_skills.json",
    ) -> "FailedSkillsManager":
        """
        从 OutputPathsConfig 创建 FailedSkillsManager 实例

        Args:
            config: 输出路径配置
            module: 模块名称
            output_type: 输出类型
            filename: 文件名

        Returns:
            FailedSkillsManager 实例
        """
        try:
            from output_paths import OutputPathsConfig as Opc
            if not isinstance(config, Opc):
                raise TypeError("config must be OutputPathsConfig")
        except ImportError:
            raise RuntimeError(
                "output_paths 模块未安装，请运行: uv pip install output_paths"
            )

        file_path = config.get_output_path(module, output_type, filename)
        instance = cls.__new__(cls)
        instance.file_path = file_path
        instance._lock = Lock()
        instance._data = {
            "version": cls.VERSION,
            "created_at": None,
            "updated_at": None,
            "stats": {
                "total_failed": 0,
                "total_retried": 0,
                "total_succeeded": 0,
                "total_still_failed": 0,
            },
            "entries": {},
        }
        instance._load()
        return instance

    def _load(self) -> None:
        """从文件加载失败记录"""
        if not self.file_path.exists():
            logger.debug(f"失败记录文件不存在，将创建新文件: {self.file_path}")
            self._data["created_at"] = datetime.now().isoformat()
            self._data["updated_at"] = datetime.now().isoformat()
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 验证版本
            if data.get("version") != self.VERSION:
                logger.warning(
                    f"失败记录版本不匹配: 预期 {self.VERSION}, 实际 {data.get('version')}"
                )

            self._data = data
            logger.info(
                f"已加载失败记录: {len(self._data.get('entries', {}))} 条"
            )

        except json.JSONDecodeError as e:
            logger.warning(f"失败记录文件损坏，将创建新文件: {e}")
            self._data = {
                "version": self.VERSION,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "stats": {
                    "total_failed": 0,
                    "total_retried": 0,
                    "total_succeeded": 0,
                    "total_still_failed": 0,
                },
                "entries": {},
            }
        except Exception as e:
            logger.warning(f"加载失败记录失败: {e}")
            self._data = {
                "version": self.VERSION,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "stats": {
                    "total_failed": 0,
                    "total_retried": 0,
                    "total_succeeded": 0,
                    "total_still_failed": 0,
                },
                "entries": {},
            }

    def save(self) -> None:
        """保存失败记录到文件（原子性写入，线程安全）"""
        with self._lock:
            self._data["updated_at"] = datetime.now().isoformat()

            # 确保目录存在
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

            # 使用临时文件 + 重命名实现原子写入
            temp_path = self.file_path.with_suffix(
                f".tmp.{uuid.uuid4().hex[:8]}"
            )

            try:
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2, ensure_ascii=False)

                # 原子性重命名
                temp_path.replace(self.file_path)

                logger.debug(f"失败记录已保存: {len(self._data['entries'])} 条记录")

            except Exception as e:
                logger.error(f"保存失败记录失败: {e}")
                # 清理临时文件
                if temp_path.exists():
                    temp_path.unlink()
                raise

    def add_failure(
        self,
        skill_path: str | Path,
        scan_result: dict[str, Any],
        scanners_failed: list[str],
        source: str = "unknown",
        relative_path: str | None = None,
    ) -> None:
        """
        添加失败记录

        Args:
            skill_path: 技能路径
            scan_result: 完整的扫描结果
            scanners_failed: 失败的scanner列表
            source: 来源
            relative_path: 相对路径
        """
        normalized_path = self._normalize_path(skill_path)
        skill_path_obj = Path(skill_path)

        # 提取已成功的结果（用于重试时合并）
        successful_results = {}
        scanners_used = scan_result.get("summary", {}).get("scanners_used", [])

        for scanner_name in scanners_used:
            if scanner_name in scan_result and scanner_name not in scanners_failed:
                successful_results[scanner_name] = scan_result[scanner_name]

        # 提取错误摘要
        error_summary = {}
        for scanner_name in scanners_failed:
            if scanner_name in scan_result:
                scanner_result = scan_result[scanner_name]
                error_summary[scanner_name] = scanner_result.get("error_type", "Unknown")

        entry = {
            "name": skill_path_obj.name,
            "source": source,
            "original_path": str(skill_path),
            "relative_path": relative_path or str(skill_path),
            "first_failed_at": datetime.now().isoformat(),
            "last_retry_at": None,
            "retry_count": 0,
            "scanners_failed": scanners_failed,
            "scanners_used": scanners_used,
            "error_summary": error_summary,
            "successful_results": successful_results,
            "scan_summary": scan_result.get("summary", {}),
        }

        self._data.setdefault("entries", {})[normalized_path] = entry
        self._data["stats"]["total_failed"] = len(self._data["entries"])

        logger.info(
            f"记录失败: {skill_path_obj.name} "
            f"(失败: {scanners_failed}, 成功: {list(successful_results.keys())})"
        )

    def get_retryable_skills(self, max_retries: int = 3) -> dict[str, dict]:
        """
        获取可重试的技能

        Args:
            max_retries: 最大重试次数

        Returns:
            {skill_path: entry} 字典
        """
        with self._lock:
            entries = self._data.get("entries", {}).copy()  # 复制以避免迭代时修改

        retryable = {}
        for skill_path, entry in entries.items():
            if entry.get("retry_count", 0) < max_retries:
                retryable[skill_path] = entry

        return retryable

    def get_skill_for_retry(self, skill_path: str | Path) -> dict | None:
        """
        获取指定技能的失败记录（用于重试）

        Args:
            skill_path: 技能路径

        Returns:
            失败记录字典，如果不存在则返回 None
        """
        with self._lock:
            normalized = self._normalize_path(skill_path)
            return self._data.get("entries", {}).get(normalized)

    def update_retry_result(
        self,
        skill_path: str | Path,
        new_scan_result: dict[str, Any],
        increment_retry: bool = True,
    ) -> dict:
        """
        更新重试结果

        Args:
            skill_path: 技能路径
            new_scan_result: 新的扫描结果
            increment_retry: 是否增加重试计数

        Returns:
            更新后的entry
        """
        with self._lock:
            normalized = self._normalize_path(skill_path)
            entries = self._data.get("entries", {})

            if normalized not in entries:
                logger.warning(f"未找到失败记录: {skill_path}")
                return {}

            entry = entries[normalized]

            # 更新重试信息
            if increment_retry:
                entry["retry_count"] = entry.get("retry_count", 0) + 1
            entry["last_retry_at"] = datetime.now().isoformat()

            # 更新失败scanner和错误摘要
            new_summary = new_scan_result.get("summary", {})
            entry["scanners_failed"] = new_summary.get("scanners_failed", [])
            entry["scanners_used"] = new_summary.get("scanners_used", [])

            # 更新错误摘要
            error_summary = {}
            for scanner_name in entry["scanners_failed"]:
                if scanner_name in new_scan_result:
                    scanner_result = new_scan_result[scanner_name]
                    error_summary[scanner_name] = scanner_result.get("error_type", "Unknown")
            entry["error_summary"] = error_summary

            # 更新已成功的结果
            scanners_used = new_summary.get("scanners_used", [])
            for scanner_name in scanners_used:
                if scanner_name in new_scan_result:
                    entry["successful_results"][scanner_name] = new_scan_result[scanner_name]

            # 更新摘要
            entry["scan_summary"] = new_summary

            logger.info(
                f"更新重试结果: {Path(skill_path).name} "
                f"(重试次数: {entry['retry_count']}, "
                f"仍失败: {entry['scanners_failed']})"
            )

            return entry

    def remove_skill(self, skill_path: str | Path) -> bool:
        """
        移除失败记录（重试成功后调用）

        Args:
            skill_path: 技能路径

        Returns:
            是否成功移除
        """
        with self._lock:
            normalized = self._normalize_path(skill_path)
            entries = self._data.get("entries", {})

            if normalized in entries:
                del entries[normalized]
                self._data["stats"]["total_failed"] = len(entries)
                self._data["stats"]["total_succeeded"] = (
                    self._data["stats"].get("total_succeeded", 0) + 1
                )
                logger.info(f"移除失败记录: {Path(skill_path).name}")
                return True

            return False

    def move_to_malicious(self, skill_path: str | Path) -> dict:
        """
        移动到有害列表（重试后确认有害）

        Args:
            skill_path: 技能路径

        Returns:
            被移除的entry
        """
        with self._lock:
            normalized = self._normalize_path(skill_path)
            entries = self._data.get("entries", {})

            if normalized in entries:
                entry = entries.pop(normalized)
                self._data["stats"]["total_failed"] = len(entries)
                logger.info(f"从失败列表移至有害: {entry.get('name', skill_path)}")
                return entry

            return {}

    def is_failed(self, skill_path: str | Path) -> bool:
        """检查技能是否在失败列表中"""
        with self._lock:
            normalized = self._normalize_path(skill_path)
            return normalized in self._data.get("entries", {})

    def get_entry(self, skill_path: str | Path) -> dict | None:
        """获取技能的失败记录"""
        with self._lock:
            normalized = self._normalize_path(skill_path)
            return self._data.get("entries", {}).get(normalized)

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            entries = self._data.get("entries", {}).copy()  # 复制以避免迭代时修改

            # 统计各scanner失败次数
            scanner_failures = {}
            for entry in entries.values():
                for scanner in entry.get("scanners_failed", []):
                    scanner_failures[scanner] = scanner_failures.get(scanner, 0) + 1

            return {
                **self._data.get("stats", {}),
                "scanner_failures": scanner_failures,
                "created_at": self._data.get("created_at"),
                "updated_at": self._data.get("updated_at"),
            }

    def list_entries(
        self,
        max_retry_count: int | None = None,
    ) -> list[tuple[str, dict]]:
        """
        列出失败记录

        Args:
            max_retry_count: 可选的重试次数过滤

        Returns:
            (skill_path, entry) 元组列表
        """
        with self._lock:
            entries = self._data.get("entries", {}).copy()  # 复制以避免迭代时修改

        if max_retry_count is not None:
            entries = {
                k: v for k, v in entries.items()
                if v.get("retry_count", 0) < max_retry_count
            }

        # 按首次失败时间排序
        sorted_entries = sorted(
            entries.items(),
            key=lambda x: x[1].get("first_failed_at", ""),
        )

        return sorted_entries

    def clear(self) -> None:
        """清空所有失败记录"""
        self._data["entries"] = {}
        self._data["stats"]["total_failed"] = 0
        self._data["updated_at"] = datetime.now().isoformat()
        logger.info("已清空所有失败记录")

    def _normalize_path(self, path: str | Path) -> str:
        """
        规范化路径

        确保路径在不同运行之间保持一致。
        """
        p = Path(path)

        # 解析为绝对路径
        try:
            p = p.resolve()
        except (OSError, RuntimeError):
            p = Path(path).absolute()

        return str(p)

    def __len__(self) -> int:
        """返回失败技能的数量"""
        return len(self._data.get("entries", {}))

    def __contains__(self, skill_path: str | Path) -> bool:
        """支持 'in' 操作符"""
        return self.is_failed(skill_path)


def create_failed_manager(
    results_dir: str | Path | None = None,
    filename: str = "failed_skills.json",
    config: "Optional[OutputPathsConfig]" = None,  # type: ignore[name-defined]
    module: str = "unified",
    output_type: str = "json",
) -> FailedSkillsManager:
    """
    创建失败技能管理器的便捷函数

    Args:
        results_dir: 结果目录路径（已废弃，请使用 config）
        filename: 文件名（当使用 config 时忽略）
        config: OutputPathsConfig 实例（推荐方式）
        module: 模块名称（当使用 config 时使用）
        output_type: 输出类型（当使用 config 时使用）

    Returns:
        FailedSkillsManager 实例
    """
    if config is not None:
        return FailedSkillsManager.from_config(config, module, output_type, filename)

    if results_dir is not None:
        warnings.warn(
            "传递 results_dir 已废弃，请使用 config 参数",
            DeprecationWarning,
            stacklevel=2,
        )
        results_dir = Path(results_dir)
        file_path = results_dir / filename
        return FailedSkillsManager(file_path, _warn_deprecated=False)

    return FailedSkillsManager(Path("results") / filename, _warn_deprecated=False)
