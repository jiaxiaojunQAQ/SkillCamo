"""
统一 Skill Registry 查询层

封装 MaliciousSkillsManager、BenignSkillsManager、FailedSkillsManager，
提供统一的查询接口供其他组件使用。

设计原则：
- 只读查询，不修改底层 manager 的写入行为
- 支持按 name / path / hash 快速查询
- 自动发现并加载默认注册表文件
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SkillRecord:
    """统一的 skill 记录格式"""
    name: str
    skill_hash: str
    source_path: str
    classification: str  # "safe" | "harmful" | "failed"
    verified_at: str
    findings: dict[str, int]
    total_findings: int
    scanners_used: list[str]
    scanners_failed: list[str]
    threat_level: str | None = None  # 仅 harmful 有
    metadata: dict[str, Any] | None = None

    @classmethod
    def from_malicious_entry(cls, entry: dict[str, Any], skill_hash: str) -> "SkillRecord":
        return cls(
            name=entry.get("name", ""),
            skill_hash=skill_hash,
            source_path=entry.get("original_path", ""),
            classification="harmful",
            verified_at=entry.get("detected_at", ""),
            findings=entry.get("findings_by_severity", {}),
            total_findings=entry.get("total_findings", 0),
            scanners_used=entry.get("scanners_used", []),
            scanners_failed=entry.get("scanners_failed", []),
            threat_level=entry.get("threat_level"),
            metadata={"source": entry.get("source"), "phase": entry.get("detected_phase")},
        )

    @classmethod
    def from_benign_entry(cls, entry: dict[str, Any], skill_hash: str) -> "SkillRecord":
        return cls(
            name=entry.get("name", ""),
            skill_hash=skill_hash,
            source_path=entry.get("original_path", ""),
            classification="safe",
            verified_at=entry.get("verified_at", ""),
            findings=entry.get("findings_by_severity", {}),
            total_findings=entry.get("total_findings", 0),
            scanners_used=entry.get("scanners_used", []),
            scanners_failed=entry.get("scanners_failed", []),
            metadata={"source": entry.get("source")},
        )

    @classmethod
    def from_failed_entry(cls, entry: dict[str, Any], skill_hash: str) -> "SkillRecord":
        return cls(
            name=entry.get("name", ""),
            skill_hash=skill_hash,
            source_path=entry.get("original_path", ""),
            classification="failed",
            verified_at=entry.get("first_failed_at", ""),
            findings={},
            total_findings=0,
            scanners_used=entry.get("scanners_used", []),
            scanners_failed=entry.get("scanners_failed", []),
            metadata={"retry_count": entry.get("retry_count", 0)},
        )

    def to_dict(self) -> dict[str, Any]:
        result = {
            "name": self.name,
            "skill_hash": self.skill_hash,
            "source_path": self.source_path,
            "classification": self.classification,
            "verified_at": self.verified_at,
            "findings": self.findings,
            "total_findings": self.total_findings,
            "scanners_used": self.scanners_used,
            "scanners_failed": self.scanners_failed,
        }
        if self.threat_level:
            result["threat_level"] = self.threat_level
        if self.metadata:
            result["metadata"] = self.metadata
        return result


class SkillRegistry:
    """
    统一注册表查询接口

    提供只读查询封装，底层调用已有的 manager 实例。
    默认注册表路径：
      - benign:  data/benign_skills.json
      - malicious: data/malicious_skills.json
      - failed:   data/failed_skills.json
    """

    # v1.0 注册表路径（默认）
    DEFAULT_REGISTRIES = {
        "benign": Path("data/benign_skills.json"),
        "malicious": Path("data/malicious_skills.json"),
        "failed": Path("data/failed_skills.json"),
    }

    # v2.0 注册表路径（迁移后）
    V2_REGISTRIES = {
        "benign": Path("data/registry/benign.json"),
        "malicious": Path("data/registry/malicious.json"),
        "failed": Path("data/registry/failed.json"),
    }

    def __init__(
        self,
        benign_path: Path | None = None,
        malicious_path: Path | None = None,
        failed_path: Path | None = None,
        use_v2: bool = False,
    ):
        """
        初始化注册表查询器

        Args:
            benign_path: 安全 skill 注册表路径
            malicious_path: 有害 skill 注册表路径
            failed_path: 失败 skill 注册表路径
            use_v2: 是否使用 v2.0 格式注册表
        """
        base = self.V2_REGISTRIES if use_v2 else self.DEFAULT_REGISTRIES
        self.benign_path = benign_path or base["benign"]
        self.malicious_path = malicious_path or base["malicious"]
        self.failed_path = failed_path or base["failed"]

        self._malicious_entries: dict[str, dict] = {}
        self._benign_entries: dict[str, dict] = {}
        self._failed_entries: dict[str, dict] = {}
        self._name_to_hash: dict[str, str] = {}  # name -> hash for reverse lookup

        self._load_all()

    def _load_all(self) -> None:
        """加载所有注册表"""
        self._malicious_entries = self._load_json(self.malicious_path)
        self._benign_entries = self._load_benign_json(self.benign_path)
        self._failed_entries = self._load_failed_json(self.failed_path)

        # 构建 name -> hash 索引
        for h, e in list(self._malicious_entries.items()) + list(self._benign_entries.items()) + list(self._failed_entries.items()):
            name = e.get("name", "")
            if name and h not in self._name_to_hash:
                self._name_to_hash[name] = h

    def _load_json(self, path: Path) -> dict[str, dict]:
        """加载 entries 格式的 JSON (malicious/failed)"""
        if not path.exists():
            logger.debug(f"注册表不存在: {path}")
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            entries = data.get("entries", {})
            logger.info(f"加载 {path.name}: {len(entries)} 条")
            return entries
        except json.JSONDecodeError as e:
            logger.warning(f"注册表损坏 {path}: {e}")
            return {}

    def _load_benign_json(self, path: Path) -> dict[str, dict]:
        """加载 benign_skills.json (兼容 v1.0 skills 数组和 v2.0 entries 字典)"""
        if not path.exists():
            logger.debug(f"注册表不存在: {path}")
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            # v2.0 格式: entries dict
            if "entries" in data:
                entries = data.get("entries", {})
                logger.info(f"加载 {path.name} (v2.0): {len(entries)} 条")
                return entries
            # v1.0 格式: skills 数组
            skills = data.get("skills", [])
            entries = {}
            for skill in skills:
                name = skill.get("name", "")
                original_path = skill.get("original_path", "")
                entries[original_path] = skill
            logger.info(f"加载 {path.name} (v1.0): {len(entries)} 条")
            return entries
        except json.JSONDecodeError as e:
            logger.warning(f"注册表损坏 {path}: {e}")
            return {}

    def _load_failed_json(self, path: Path) -> dict[str, dict]:
        """加载 failed_skills.json"""
        return self._load_json(path)

    # ─────────────────────────────────────────────────────────────
    # 核心查询接口
    # ─────────────────────────────────────────────────────────────

    def is_known(self, skill_name_or_path: str | Path) -> bool:
        """检查 skill 是否在任何注册表中"""
        return (
            self.get_classification(skill_name_or_path) is not None
        )

    def get_classification(self, skill_name_or_path: str | Path) -> str | None:
        """
        获取 skill 的分类

        Returns:
            "safe" | "harmful" | "failed" | None
        """
        key = str(skill_name_or_path)

        # 精确路径匹配
        for entries in [self._malicious_entries, self._benign_entries, self._failed_entries]:
            if key in entries:
                if entries is self._malicious_entries:
                    return "harmful"
                elif entries is self._benign_entries:
                    return "safe"
                else:
                    return "failed"

        # 名称匹配（通过索引）
        name = Path(key).name
        if name in self._name_to_hash:
            h = self._name_to_hash[name]
            if h in self._malicious_entries:
                return "harmful"
            if h in self._benign_entries:
                return "safe"
            if h in self._failed_entries:
                return "failed"

        return None

    def get_record(self, skill_name_or_path: str | Path) -> SkillRecord | None:
        """获取 skill 的完整记录"""
        key = str(skill_name_or_path)

        # 精确路径匹配
        for entries, cls in [
            (self._malicious_entries, "harmful"),
            (self._benign_entries, "safe"),
            (self._failed_entries, "failed"),
        ]:
            if key in entries:
                entry = entries[key]
                return self._entry_to_record(entry, cls)

        # 名称匹配
        name = Path(key).name
        if name in self._name_to_hash:
            h = self._name_to_hash[name]
            for entries, cls in [
                (self._malicious_entries, "harmful"),
                (self._benign_entries, "safe"),
                (self._failed_entries, "failed"),
            ]:
                if h in entries:
                    return self._entry_to_record(entries[h], cls)

        return None

    def _entry_to_record(self, entry: dict[str, Any], classification: str) -> SkillRecord:
        if classification == "harmful":
            return SkillRecord.from_malicious_entry(entry, entry.get("id", ""))
        elif classification == "safe":
            return SkillRecord.from_benign_entry(entry, entry.get("id", ""))
        else:
            return SkillRecord.from_failed_entry(entry, entry.get("id", ""))

    def get_harmful_names(self) -> list[str]:
        """获取所有已知有害 skill 的名称列表"""
        return [e.get("name", "") for e in self._malicious_entries.values()]

    def get_safe_names(self) -> list[str]:
        """获取所有已知安全 skill 的名称列表"""
        return [e.get("name", "") for e in self._benign_entries.values()]

    def get_failed_names(self) -> list[str]:
        """获取所有失败 skill 的名称列表"""
        return [e.get("name", "") for e in self._failed_entries.values()]

    def get_stats(self) -> dict[str, int]:
        """获取各注册表统计"""
        return {
            "harmful": len(self._malicious_entries),
            "safe": len(self._benign_entries),
            "failed": len(self._failed_entries),
            "total": len(self._malicious_entries) + len(self._benign_entries) + len(self._failed_entries),
        }

    def should_skip_harmful(self, skill_name_or_path: str | Path) -> bool:
        """判断是否应跳过（已知有害）"""
        return self.get_classification(skill_name_or_path) == "harmful"

    def is_safe(self, skill_name_or_path: str | Path) -> bool:
        """判断是否已知安全"""
        return self.get_classification(skill_name_or_path) == "safe"


# 全局默认注册表实例（延迟初始化）
_default_registry: SkillRegistry | None = None


def get_default_registry() -> SkillRegistry:
    """获取全局默认注册表（线程安全单例）"""
    global _default_registry
    if _default_registry is None:
        _default_registry = SkillRegistry()
    return _default_registry
