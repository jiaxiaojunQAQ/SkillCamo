"""
安全技能管理模块

记录和管理确认安全的技能。

使用 skill 目录内容的哈希值作为唯一ID，避免因目录移动导致ID变化。
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
from typing import Any

logger = logging.getLogger(__name__)


def _to_relative_path(skill_path: str | Path) -> str:
    """将 skill 路径转换为相对于项目根目录的相对路径。"""
    try:
        skill_path = Path(skill_path).resolve()
        from .paths import PROJECT_ROOT
        rel = skill_path.relative_to(PROJECT_ROOT)
        return str(rel)
    except (ValueError, OSError):
        return str(skill_path)


def compute_skill_hash(skill_path: str | Path) -> str:
    """
    计算 skill 目录的哈希值作为唯一ID

    递归读取目录下所有文件内容，计算 SHA256 哈希。
    与 MaliciousSkillsManager 保持一致。
    """
    import os

    skill_path = Path(skill_path)
    hasher = hashlib.sha256()

    skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", ".env"}

    for root, dirs, files in os.walk(skill_path):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(('.', '__'))]

        for filename in sorted(files):
            if filename.startswith(('.', '__')):
                continue

            file_path = Path(root) / filename
            relative_path = file_path.relative_to(skill_path)
            hasher.update(str(relative_path).encode("utf-8"))

            try:
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hasher.update(chunk)
            except OSError:
                pass

    return hasher.hexdigest()


class BenignSkillsManager:
    """
    安全技能管理器

    记录确认安全的技能，包括扫描摘要和验证信息。
    """

    VERSION = "2.0"

    def __init__(
        self,
        file_path: str | Path,
        *,
        _warn_deprecated: bool = True,
    ):
        if _warn_deprecated:
            warnings.warn(
                "直接传递 file_path 已废弃，请使用 from_path() 类方法",
                DeprecationWarning,
                stacklevel=2,
            )
        self.file_path = Path(file_path)
        self._lock = Lock()
        self._data: dict[str, Any] = {
            "version": self.VERSION,
            "created_at": None,
            "updated_at": None,
            "stats": {
                "total_benign": 0,
                "by_scanner": {},
            },
            "entries": {},
        }
        self._load()

    @classmethod
    def from_path(cls, file_path: str | Path) -> "BenignSkillsManager":
        """从文件路径创建实例"""
        instance = cls.__new__(cls)
        instance.file_path = Path(file_path)
        instance._lock = Lock()
        instance._data = {
            "version": cls.VERSION,
            "created_at": None,
            "updated_at": None,
            "stats": {
                "total_benign": 0,
                "by_scanner": {},
            },
            "entries": {},
        }
        instance._load()
        return instance

    def _load(self) -> None:
        """从文件加载安全记录"""
        if not self.file_path.exists():
            self._data["created_at"] = datetime.now().isoformat()
            self._data["updated_at"] = datetime.now().isoformat()
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._data = data
            logger.info(f"已加载安全记录: {len(self._data.get('entries', {}))} 条")
        except json.JSONDecodeError:
            logger.warning(f"安全记录文件损坏，将创建新文件")
            self._data = {
                "version": self.VERSION,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "stats": {"total_benign": 0, "by_scanner": {}},
                "entries": {},
            }

    def save(self) -> None:
        """保存安全记录（原子性写入）"""
        with self._lock:
            self._data["updated_at"] = datetime.now().isoformat()
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

            temp_path = self.file_path.with_suffix(f".tmp.{uuid.uuid4().hex[:8]}")
            try:
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2, ensure_ascii=False)
                temp_path.replace(self.file_path)
            except Exception as e:
                logger.error(f"保存安全记录失败: {e}")
                if temp_path.exists():
                    temp_path.unlink()
                raise

    def add_benign(
        self,
        skill_path: str | Path,
        scan_result: dict[str, Any],
        source: str = "unknown",
    ) -> None:
        """添加安全技能记录"""
        skill_path_obj = Path(skill_path)
        skill_hash = compute_skill_hash(skill_path)

        summary = scan_result.get("summary", {})
        findings = summary.get("findings_by_severity", {})

        entry = {
            "id": skill_hash,
            "name": skill_path_obj.name,
            "source": source,
            "original_path": _to_relative_path(skill_path),
            "verified_at": datetime.now().isoformat(),
            "findings_by_severity": findings,
            "total_findings": summary.get("total_findings", 0),
            "scanners_used": summary.get("scanners_used", []),
            "scanners_failed": summary.get("scanners_failed", []),
            "scan_summary": summary,
        }

        self._data.setdefault("entries", {})[skill_hash] = entry
        self._data["stats"]["total_benign"] = len(self._data["entries"])

        for scanner in summary.get("scanners_used", []):
            self._data["stats"]["by_scanner"][scanner] = (
                self._data["stats"]["by_scanner"].get(scanner, 0) + 1
            )

        logger.info(f"记录安全: {skill_path_obj.name} (C={findings.get('critical', 0)}, H={findings.get('high', 0)})")

    def is_benign(self, skill_path: str | Path) -> bool:
        """检查技能是否在安全列表中（通过内容哈希）"""
        with self._lock:
            skill_hash = compute_skill_hash(skill_path)
            return skill_hash in self._data.get("entries", {})

    def get_entry(self, skill_path: str | Path) -> dict | None:
        """获取技能的安全记录"""
        with self._lock:
            skill_hash = compute_skill_hash(skill_path)
            return self._data.get("entries", {}).get(skill_hash)

    def remove_skill(self, skill_path: str | Path) -> bool:
        """移除安全记录"""
        with self._lock:
            skill_hash = compute_skill_hash(skill_path)
            entries = self._data.get("entries", {})
            if skill_hash in entries:
                del entries[skill_hash]
                self._data["stats"]["total_benign"] = len(entries)
                return True
            return False

    def list_entries(self) -> list[tuple[str, dict]]:
        """列出所有安全记录"""
        with self._lock:
            entries = self._data.get("entries", {}).copy()
        return sorted(entries.items(), key=lambda x: x[1].get("verified_at", ""), reverse=True)

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return self._data.get("stats", {}).copy()

    def __len__(self) -> int:
        return len(self._data.get("entries", {}))

    def __contains__(self, skill_path: str | Path) -> bool:
        return self.is_benign(skill_path)
