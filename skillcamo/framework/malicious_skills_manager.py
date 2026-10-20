"""
有害技能管理模块

记录和管理确认有害的技能。

使用skill目录内容的哈希值作为唯一ID，避免因目录移动导致ID变化。

使用 OutputPathsConfig 的示例:
    from output_paths import OutputPathsConfig
    from unified_scanner.malicious_skills_manager import MaliciousSkillsManager

    config = OutputPathsConfig.create("claude-3-5-sonnet", "malicious_skills")
    manager = MaliciousSkillsManager.from_config(config, "unified", "json")
"""
from __future__ import annotations

import hashlib
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


def compute_skill_hash(skill_path: str | Path) -> str:
    """
    计算skill目录的哈希值作为唯一ID

    递归读取目录下所有文件内容，计算SHA256哈希。
    这样即使目录移动，只要内容不变，哈希值就不变。

    使用 os.walk() 并在遍历前剪枝排除目录，避免遍历 node_modules/.git 等大型目录。

    Args:
        skill_path: skill目录路径

    Returns:
        SHA256哈希值（十六进制字符串）
    """
    import os

    skill_path = Path(skill_path)
    hasher = hashlib.sha256()

    # 预编译排除模式用于快速查找
    skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", ".env"}

    for root, dirs, files in os.walk(skill_path):
        # 在遍历子目录前剪枝（关键优化）
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(('.', '__'))]

        # 对当前层文件排序确保哈希确定性
        for filename in sorted(files):
            if filename.startswith(('.', '__')):
                continue

            file_path = Path(root) / filename
            relative_path = file_path.relative_to(skill_path)
            hasher.update(str(relative_path).encode("utf-8"))

            try:
                with open(file_path, "rb") as f:
                    # 使用4096字节块大小与现有代码保持一致
                    for chunk in iter(lambda: f.read(4096), b""):
                        hasher.update(chunk)
            except OSError as e:
                logger.debug(f"无法读取文件 {file_path}: {e}")

    return hasher.hexdigest()


class MaliciousSkillsManager:
    """
    有害技能管理器

    记录确认有害的技能，包括发现阶段和威胁级别。
    """

    VERSION = "1.0"

    def __init__(
        self,
        file_path: str | Path,
        *,
        _warn_deprecated: bool = True,
    ):
        """
        初始化有害技能管理器

        Args:
            file_path: 有害技能记录文件路径（不建议使用，请使用 from_config）
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
                "total_malicious": 0,
                "by_phase": {},
                "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0},
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
        filename: str = "malicious_skills.json",
    ) -> "MaliciousSkillsManager":
        """
        从 OutputPathsConfig 创建 MaliciousSkillsManager 实例

        Args:
            config: 输出路径配置
            module: 模块名称
            output_type: 输出类型
            filename: 文件名

        Returns:
            MaliciousSkillsManager 实例
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
                "total_malicious": 0,
                "by_phase": {},
                "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            },
            "entries": {},
        }
        instance._load()
        return instance

    def _load(self) -> None:
        """从文件加载有害记录"""
        if not self.file_path.exists():
            logger.debug(f"有害记录文件不存在，将创建新文件: {self.file_path}")
            self._data["created_at"] = datetime.now().isoformat()
            self._data["updated_at"] = datetime.now().isoformat()
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 验证版本
            if data.get("version") != self.VERSION:
                logger.warning(
                    f"有害记录版本不匹配: 预期 {self.VERSION}, 实际 {data.get('version')}"
                )

            self._data = data
            logger.info(
                f"已加载有害记录: {len(self._data.get('entries', {}))} 条"
            )

        except json.JSONDecodeError as e:
            logger.warning(f"有害记录文件损坏，将创建新文件: {e}")
            self._data = {
                "version": self.VERSION,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "stats": {
                    "total_malicious": 0,
                    "by_phase": {},
                    "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                },
                "entries": {},
            }
        except Exception as e:
            logger.warning(f"加载有害记录失败: {e}")
            self._data = {
                "version": self.VERSION,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "stats": {
                    "total_malicious": 0,
                    "by_phase": {},
                    "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                },
                "entries": {},
            }

    def save(self) -> None:
        """保存有害记录到文件（原子性写入，线程安全）"""
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

                logger.debug(f"有害记录已保存: {len(self._data['entries'])} 条记录")

            except Exception as e:
                logger.error(f"保存有害记录失败: {e}")
                # 清理临时文件
                if temp_path.exists():
                    temp_path.unlink()
                raise

    def add_malicious(
        self,
        skill_path: str | Path,
        scan_result: dict[str, Any],
        source: str = "unknown",
        relative_path: str | None = None,
    ) -> None:
        """
        添加有害记录

        使用skill目录内容的哈希值作为唯一ID。

        Args:
            skill_path: 技能路径
            scan_result: 扫描结果
            source: 来源
            relative_path: 相对路径
        """
        skill_path_obj = Path(skill_path)
        skill_hash = compute_skill_hash(skill_path)

        summary = scan_result.get("summary", {})
        early_stop = scan_result.get("early_stop", {})

        entry = {
            "id": skill_hash,
            "name": skill_path_obj.name,
            "source": source,
            "original_path": str(skill_path),
            "relative_path": relative_path or str(skill_path),
            "detected_at": datetime.now().isoformat(),
            "detected_phase": early_stop.get("phase", "all"),
            "detected_phase_name": early_stop.get("phase_name", "All phases"),
            "threat_level": self._get_threat_level(summary),
            "findings_by_severity": summary.get("findings_by_severity", {}),
            "total_findings": summary.get("total_findings", 0),
            "scanners_used": summary.get("scanners_used", []),
            "scan_summary": summary,
        }

        # 使用哈希作为key，相同内容的skill会被覆盖
        self._data.setdefault("entries", {})[skill_hash] = entry

        # 更新统计
        self._data["stats"]["total_malicious"] = len(self._data["entries"])

        # 按阶段统计
        phase = early_stop.get("phase", "all")
        self._data["stats"]["by_phase"][str(phase)] = (
            self._data["stats"]["by_phase"].get(str(phase), 0) + 1
        )

        # 按严重级别统计
        for severity, count in summary.get("findings_by_severity", {}).items():
            self._data["stats"]["by_severity"][severity] = (
                self._data["stats"]["by_severity"].get(severity, 0) + count
            )

        logger.info(
            f"记录有害: {skill_path_obj.name} (id: {skill_hash[:12]}...) "
            f"(阶段: {entry['detected_phase']}, "
            f"C={entry['findings_by_severity'].get('critical', 0)}, "
            f"H={entry['findings_by_severity'].get('high', 0)})"
        )

    def _get_threat_level(self, summary: dict) -> str:
        """根据扫描摘要确定威胁级别"""
        findings = summary.get("findings_by_severity", {})
        critical = findings.get("critical", 0)
        high = findings.get("high", 0)

        if critical > 0:
            return "CRITICAL"
        elif high > 0:
            return "HIGH"
        else:
            return "MEDIUM"

    def is_malicious(self, skill_path: str | Path) -> bool:
        """检查技能是否在有害列表中（通过内容哈希）"""
        with self._lock:
            skill_hash = compute_skill_hash(skill_path)
            return skill_hash in self._data.get("entries", {})

    def get_entry(self, skill_path: str | Path) -> dict | None:
        """获取技能的有害记录（通过内容哈希）"""
        with self._lock:
            skill_hash = compute_skill_hash(skill_path)
            return self._data.get("entries", {}).get(skill_hash)

    def remove_skill(self, skill_path: str | Path) -> bool:
        """
        移除有害记录（通过内容哈希）

        Args:
            skill_path: 技能路径

        Returns:
            是否成功移除
        """
        with self._lock:
            skill_hash = compute_skill_hash(skill_path)
            entries = self._data.get("entries", {})

            if skill_hash in entries:
                entry = entries.pop(skill_hash)
                self._data["stats"]["total_malicious"] = len(entries)
                logger.info(f"移除有害记录: {entry.get('name', skill_path)} (id: {skill_hash[:12]}...)")
                return True

            return False

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return self._data.get("stats", {}).copy()

    def list_entries(
        self,
        min_phase: int | None = None,
        threat_level: str | None = None,
    ) -> list[tuple[str, dict]]:
        """
        列出有害记录

        Args:
            min_phase: 最小阶段过滤
            threat_level: 威胁级别过滤

        Returns:
            (skill_path, entry) 元组列表
        """
        with self._lock:
            entries = self._data.get("entries", {}).copy()  # 复制以避免迭代时修改

        if min_phase is not None:
            entries = {
                k: v for k, v in entries.items()
                if v.get("detected_phase", "all") >= min_phase
            }

        if threat_level is not None:
            entries = {
                k: v for k, v in entries.items()
                if v.get("threat_level") == threat_level
            }

        # 按检测时间排序
        sorted_entries = sorted(
            entries.items(),
            key=lambda x: x[1].get("detected_at", ""),
            reverse=True,
        )

        return sorted_entries

    def clear(self) -> None:
        """清空所有有害记录"""
        self._data["entries"] = {}
        self._data["stats"] = {
            "total_malicious": 0,
            "by_phase": {},
            "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        }
        self._data["updated_at"] = datetime.now().isoformat()
        logger.info("已清空所有有害记录")

    def __len__(self) -> int:
        """返回有害技能的数量"""
        return len(self._data.get("entries", {}))

    def __contains__(self, skill_path: str | Path) -> bool:
        """支持 'in' 操作符"""
        return self.is_malicious(skill_path)


def create_malicious_manager(
    results_dir: str | Path | None = None,
    filename: str = "malicious_skills.json",
    config: "Optional[OutputPathsConfig]" = None,  # type: ignore[name-defined]
    module: str = "unified",
    output_type: str = "json",
) -> MaliciousSkillsManager:
    """
    创建有害技能管理器的便捷函数

    Args:
        results_dir: 结果目录路径（已废弃，请使用 config）
        filename: 文件名（当使用 config 时忽略）
        config: OutputPathsConfig 实例（推荐方式）
        module: 模块名称（当使用 config 时使用）
        output_type: 输出类型（当使用 config 时使用）

    Returns:
        MaliciousSkillsManager 实例
    """
    if config is not None:
        return MaliciousSkillsManager.from_config(config, module, output_type, filename)

    if results_dir is not None:
        warnings.warn(
            "传递 results_dir 已废弃，请使用 config 参数",
            DeprecationWarning,
            stacklevel=2,
        )
        results_dir = Path(results_dir)
        file_path = results_dir / filename
        return MaliciousSkillsManager(file_path, _warn_deprecated=False)

    return MaliciousSkillsManager(Path("results") / filename, _warn_deprecated=False)
