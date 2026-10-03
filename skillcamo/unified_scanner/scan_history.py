"""
扫描历史记录管理模块

记录所有已扫描的技能，支持断点续传和跳过已扫描的技能。

特性:
- 记录所有扫描的技能（无论安全与否）
- 基于路径匹配判断是否已扫描
- 原子性写入确保数据完整性
- 支持统计和历史查询
- 支持 OutputPathsConfig 统一路径管理

使用示例:
    # 旧方式（已废弃）
    history = ScanHistory("/path/to/scan_history.json")

    # 新方式 - 使用 OutputPathsConfig
    from output_paths import OutputPathsConfig
    config = OutputPathsConfig.create("claude-3-5-sonnet", "malicious_skills")
    history = ScanHistory.from_config(config, "unified", "json")

    # 检查是否已扫描
    if history.is_scanned("/path/to/skill"):
        print("已扫描，跳过")
        continue

    # 执行扫描...
    result = scanner.scan(skill_path)

    # 记录扫描结果
    history.record_scan(str(skill_path), result["summary"])
    history.save()
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


class ScanHistory:
    """
    扫描历史记录管理器

    记录所有已扫描的技能路径和结果摘要，支持断点续传。
    """

    VERSION = "1.0"

    def __init__(
        self,
        history_path: str | Path,
        *,
        _warn_deprecated: bool = True,
    ):
        """
        初始化扫描历史记录管理器

        Args:
            history_path: 历史记录文件路径（不建议使用，请使用 from_config）
        """
        if _warn_deprecated:
            warnings.warn(
                "直接传递 history_path 已废弃，请使用 from_config() 方法",
                DeprecationWarning,
                stacklevel=2,
            )
        self.history_path = Path(history_path)
        self._lock = Lock()

        # 数据结构
        self._data: dict[str, Any] = {
            "version": self.VERSION,
            "created_at": None,
            "updated_at": None,
            "entries": {},  # skill_path -> scan_entry
        }

        # 加载已有历史
        self._load()

    @classmethod
    def from_config(
        cls,
        config: "OutputPathsConfig",  # type: ignore[name-defined]
        module: str = "unified",
        output_type: str = "json",
        filename: str = "scan_history.json",
    ) -> "ScanHistory":
        """
        从 OutputPathsConfig 创建 ScanHistory 实例

        Args:
            config: 输出路径配置
            module: 模块名称
            output_type: 输出类型
            filename: 文件名

        Returns:
            ScanHistory 实例
        """
        try:
            from output_paths import OutputPathsConfig as Opc
            if not isinstance(config, Opc):
                raise TypeError("config must be OutputPathsConfig")
        except ImportError:
            raise RuntimeError(
                "output_paths 模块未安装，请运行: uv pip install output_paths"
            )

        history_path = config.get_output_path(module, output_type, filename)
        instance = cls.__new__(cls)
        instance.history_path = history_path
        instance._lock = Lock()
        instance._data = {
            "version": cls.VERSION,
            "created_at": None,
            "updated_at": None,
            "entries": {},
        }
        instance._load()
        return instance

    def _load(self) -> None:
        """从文件加载历史记录"""
        if not self.history_path.exists():
            logger.debug(f"历史记录文件不存在，将创建新文件: {self.history_path}")
            self._data["created_at"] = datetime.now().isoformat()
            self._data["updated_at"] = datetime.now().isoformat()
            return

        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 验证版本
            if data.get("version") != self.VERSION:
                logger.warning(
                    f"历史记录版本不匹配: 预期 {self.VERSION}, 实际 {data.get('version')}"
                )

            self._data = data
            logger.info(
                f"已加载扫描历史: {len(self._data.get('entries', {}))} 条记录"
            )

        except json.JSONDecodeError as e:
            logger.warning(f"历史记录文件损坏，将创建新文件: {e}")
            self._data = {
                "version": self.VERSION,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "entries": {},
            }
        except Exception as e:
            logger.warning(f"加载历史记录失败: {e}")
            self._data = {
                "version": self.VERSION,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "entries": {},
            }

    def save(self) -> None:
        """保存历史记录到文件（原子性写入，线程安全）"""
        with self._lock:
            self._data["updated_at"] = datetime.now().isoformat()

            # 确保目录存在
            self.history_path.parent.mkdir(parents=True, exist_ok=True)

            # 使用临时文件 + 重命名实现原子写入
            temp_path = self.history_path.with_suffix(
                f".tmp.{uuid.uuid4().hex[:8]}"
            )

            try:
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2, ensure_ascii=False)

                # 原子性重命名
                temp_path.replace(self.history_path)

                logger.debug(f"历史记录已保存: {len(self._data['entries'])} 条记录")

            except Exception as e:
                logger.error(f"保存历史记录失败: {e}")
                # 清理临时文件
                if temp_path.exists():
                    temp_path.unlink()
                raise

    def is_scanned(self, skill_path: str | Path) -> bool:
        """
        检查技能是否已扫描

        Args:
            skill_path: 技能路径

        Returns:
            是否已扫描
        """
        with self._lock:
            # 规范化路径
            normalized = self._normalize_path(skill_path)
            return normalized in self._data.get("entries", {})

    def get_entry(self, skill_path: str | Path) -> dict[str, Any] | None:
        """
        获取技能的扫描记录

        Args:
            skill_path: 技能路径

        Returns:
            扫描记录字典，如果不存在则返回 None
        """
        with self._lock:
            normalized = self._normalize_path(skill_path)
            return self._data.get("entries", {}).get(normalized)

    def record_scan(
        self,
        skill_path: str | Path,
        summary: dict[str, Any],
    ) -> None:
        """
        记录扫描结果

        Args:
            skill_path: 技能路径
            summary: 扫描摘要（来自 scanner result 的 summary 字段）
        """
        with self._lock:
            normalized = self._normalize_path(skill_path)

            entry = {
                "scanned_at": datetime.now().isoformat(),
                "is_safe": summary.get("is_safe", False),
                "total_findings": summary.get("total_findings", 0),
                "findings_by_severity": summary.get("findings_by_severity", {}),
                "scanners_used": summary.get("scanners_used", []),
                "scanners_failed": summary.get("scanners_failed", []),
            }

            self._data.setdefault("entries", {})[normalized] = entry

            logger.debug(
                f"记录扫描: {Path(skill_path).name} "
                f"(safe={entry['is_safe']}, findings={entry['total_findings']})"
            )

    def remove(self, skill_path: str | Path) -> bool:
        """
        移除技能的扫描记录

        Args:
            skill_path: 技能路径

        Returns:
            是否成功移除（如果记录不存在则返回 False）
        """
        with self._lock:
            normalized = self._normalize_path(skill_path)
            entries = self._data.get("entries", {})

            if normalized in entries:
                del entries[normalized]
                logger.debug(f"移除扫描记录: {skill_path}")
                return True

            return False

    def clear(self) -> None:
        """清空所有扫描记录"""
        with self._lock:
            self._data["entries"] = {}
            self._data["updated_at"] = datetime.now().isoformat()
            logger.info("已清空所有扫描记录")

    def get_stats(self) -> dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        with self._lock:
            entries = self._data.get("entries", {}).copy()  # 复制以避免迭代时修改

        safe_count = sum(1 for e in entries.values() if e.get("is_safe", False))
        unsafe_count = len(entries) - safe_count

        # 统计各级别问题数量
        total_critical = 0
        total_high = 0
        total_medium = 0
        total_low = 0

        for entry in entries.values():
            severity = entry.get("findings_by_severity", {})
            total_critical += severity.get("critical", 0)
            total_high += severity.get("high", 0)
            total_medium += severity.get("medium", 0)
            total_low += severity.get("low", 0)

        return {
            "total_scanned": len(entries),
            "safe_count": safe_count,
            "unsafe_count": unsafe_count,
            "total_findings": sum(e.get("total_findings", 0) for e in entries.values()),
            "severity_summary": {
                "critical": total_critical,
                "high": total_high,
                "medium": total_medium,
                "low": total_low,
            },
            "created_at": self._data.get("created_at"),
            "updated_at": self._data.get("updated_at"),
        }

    def list_entries(
        self,
        filter_safe: bool | None = None,
    ) -> list[tuple[str, dict[str, Any]]]:
        """
        列出扫描记录

        Args:
            filter_safe: 可选的安全过滤
                - None: 返回所有记录
                - True: 只返回安全的记录
                - False: 只返回不安全的记录

        Returns:
            (skill_path, entry) 元组列表，按扫描时间倒序排列
        """
        with self._lock:
            entries = self._data.get("entries", {}).copy()  # 复制以避免迭代时修改

        if filter_safe is not None:
            entries = {
                k: v for k, v in entries.items()
                if v.get("is_safe", False) == filter_safe
            }

        # 按扫描时间倒序排序
        sorted_entries = sorted(
            entries.items(),
            key=lambda x: x[1].get("scanned_at", ""),
            reverse=True,
        )

        return sorted_entries

    def _normalize_path(self, path: str | Path) -> str:
        """
        规范化路径

        确保路径在不同运行之间保持一致。

        Args:
            path: 原始路径

        Returns:
            规范化后的路径字符串
        """
        # 转换为 Path 对象
        p = Path(path)

        # 解析为绝对路径
        try:
            p = p.resolve()
        except (OSError, RuntimeError):
            # 如果路径不存在或无法解析，使用绝对路径
            p = Path(path).absolute()

        # 返回字符串形式
        return str(p)

    def __len__(self) -> int:
        """返回已扫描技能的数量"""
        return len(self._data.get("entries", {}))

    def __contains__(self, skill_path: str | Path) -> bool:
        """支持 'in' 操作符"""
        return self.is_scanned(skill_path)


def create_history_manager(
    results_dir: str | Path | None = None,
    filename: str = "scan_history.json",
    config: "Optional[OutputPathsConfig]" = None,  # type: ignore[name-defined]
    module: str = "unified",
    output_type: str = "json",
) -> ScanHistory:
    """
    创建扫描历史管理器的便捷函数

    Args:
        results_dir: 结果目录路径（已废弃，请使用 config）
        filename: 历史文件名（当使用 config 时忽略）
        config: OutputPathsConfig 实例（推荐方式）
        module: 模块名称（当使用 config 时使用）
        output_type: 输出类型（当使用 config 时使用）

    Returns:
        ScanHistory 实例
    """
    if config is not None:
        return ScanHistory.from_config(config, module, output_type, filename)

    if results_dir is not None:
        warnings.warn(
            "传递 results_dir 已废弃，请使用 config 参数",
            DeprecationWarning,
            stacklevel=2,
        )
        results_dir = Path(results_dir)
        history_path = results_dir / filename
        return ScanHistory(history_path, _warn_deprecated=False)

    # 使用默认路径
    from ..output_paths import get_default_output_root
    return ScanHistory(get_default_output_root() / filename, _warn_deprecated=False)
