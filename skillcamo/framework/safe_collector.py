"""
安全 Skill 收集器

扫描完成后将每个 skill 归入三个互斥桶：

  safe    — 所有 scanner 成功 + critical/high == 0
  harmful — 所有 scanner 成功 + critical 或 high > 0
  retry   — 有 scanner 失败（结果不完整，不做安全判定）

retry 中的 skill 重跑成功后再归入 safe 或 harmful。

支持与 SkillRegistry 集成：
  - load_from_registry(): 从已有注册表预加载已知 skill
  - set_registry_paths(): 设置注册表路径，finalize() 时自动追加
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .models import UnifiedScanResult

if TYPE_CHECKING:
    from .registry import SkillRegistry

logger = logging.getLogger(__name__)


def classify(result: UnifiedScanResult) -> str:
    """将扫描结果归类为 'safe' / 'harmful' / 'retry'。

    - retry:   有任意 scanner 失败（结果不完整）
    - safe:    全部 scanner 成功 + critical == 0 且 high == 0
    - harmful: 全部 scanner 成功 + critical > 0 或 high > 0
    """
    s = result.summary
    if s is None:
        return "retry"
    if s.scanners_failed:
        return "retry"
    return "safe" if (s.critical == 0 and s.high == 0) else "harmful"


def is_fully_safe(result: UnifiedScanResult) -> bool:
    """便捷函数：是否归类为 safe。"""
    return classify(result) == "safe"


def _skill_entry(skill_path: Path, result: UnifiedScanResult) -> dict[str, Any]:
    """构建索引条目（safe / harmful 共用）。"""
    s = result.summary
    return {
        "name": skill_path.name,
        "source_path": str(skill_path.resolve()),
        "scan_timestamp": result.scan_timestamp.isoformat(),
        "findings": {
            "critical": s.critical,
            "high": s.high,
            "medium": s.medium,
            "low": s.low,
            "info": s.info,
        },
        "scanners_used": s.scanners_used,
        "scanners_failed": s.scanners_failed,
        "scanner_summaries": [summary.to_dict() for summary in s.scanner_summaries],
    }


@dataclass
class SafeSkillCollector:
    """三桶式 skill 收集器。

    调用 ingest() 处理每个 skill，最后调用 finalize() 写出三个 JSON：
      index_path   — 安全 skill 列表（附带 safe_path 复制路径）
      harmful_path — 有害 skill 列表
      retry_path   — 有 scanner 失败、待重试的 skill 列表

    支持与 SkillRegistry 集成：load_from_registry() 预加载已知条目，
    set_registry_paths() 设置路径后 finalize() 自动追加到注册表。
    """

    safe_dir: Path
    index_path: Path
    retry_path: Path
    harmful_path: Path
    _safe: list[dict[str, Any]] = field(default_factory=list)
    _harmful: list[dict[str, Any]] = field(default_factory=list)
    _retry: list[dict[str, Any]] = field(default_factory=list)
    # O(1) 查找索引: source_path → bucket
    _path_index: dict[str, str] = field(default_factory=dict)
    _registry_benign_path: Path | None = field(default=None, repr=False)
    _registry_malicious_path: Path | None = field(default=None, repr=False)
    _registry_failed_path: Path | None = field(default=None, repr=False)
    _preloaded_safe_count: int = field(default=0, repr=False)
    _preloaded_harmful_count: int = field(default=0, repr=False)
    _preloaded_retry_count: int = field(default=0, repr=False)

    def ingest(self, skill_path: Path, result: UnifiedScanResult) -> str:
        """处理单个 skill，归入对应桶。

        Returns:
            分类结果：'safe' / 'harmful' / 'retry'
        """
        bucket = classify(result)

        if bucket == "retry":
            s = result.summary
            resolved_path = str(skill_path.resolve())
            self._retry.append({
                "name": skill_path.name,
                "source_path": resolved_path,
                "failed_scanners": s.scanners_failed if s else [],
                "scan_timestamp": result.scan_timestamp.isoformat(),
                "findings": {
                    "critical": s.critical if s else 0,
                    "high": s.high if s else 0,
                    "medium": s.medium if s else 0,
                    "low": s.low if s else 0,
                    "info": s.info if s else 0,
                },
                "scanners_used": s.scanners_used if s else [],
                "scanner_summaries": [summary.to_dict() for summary in s.scanner_summaries] if s else [],
            })
            self._path_index[resolved_path] = "failed"
            logger.info(f"retry: {skill_path.name} — failed scanners: {s.scanners_failed if s else '?'}")

        elif bucket == "safe":
            dest = self.safe_dir / skill_path.name
            resolved_path = str(skill_path.resolve())
            try:
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(skill_path, dest)
            except Exception as e:
                logger.error(f"Failed to copy safe skill {skill_path.name}: {e}")
                s = result.summary
                self._retry.append({
                    "name": skill_path.name,
                    "source_path": resolved_path,
                    "failed_scanners": ["copy_failed"],
                    "scan_timestamp": result.scan_timestamp.isoformat(),
                    "findings": {
                        "critical": s.critical if s else 0,
                        "high": s.high if s else 0,
                        "medium": s.medium if s else 0,
                        "low": s.low if s else 0,
                        "info": s.info if s else 0,
                    },
                    "scanners_used": s.scanners_used if s else [],
                    "scanner_summaries": [summary.to_dict() for summary in s.scanner_summaries] if s else [],
                    "error": str(e),
                })
                self._path_index[resolved_path] = "failed"
                return "retry"
            entry = _skill_entry(skill_path, result)
            entry["safe_path"] = str(dest)
            self._safe.append(entry)
            self._path_index[resolved_path] = "safe"
            logger.info(f"safe: {skill_path.name} -> {dest}")

        else:  # harmful
            resolved_path = str(skill_path.resolve())
            self._harmful.append(_skill_entry(skill_path, result))
            self._path_index[resolved_path] = "harmful"
            logger.info(f"harmful: {skill_path.name}")

        return bucket

    def finalize(self) -> dict[str, Any]:
        """写出三个 JSON 文件，返回各桶数量汇总。"""
        self.safe_dir.mkdir(parents=True, exist_ok=True)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.harmful_path.parent.mkdir(parents=True, exist_ok=True)
        self.retry_path.parent.mkdir(parents=True, exist_ok=True)

        def _write(path: Path, items: list) -> None:
            """原子写入：先写临时文件，再 rename 替换，避免中断导致文件损坏。"""
            data = json.dumps({"total": len(items), "skills": items}, indent=2, ensure_ascii=False)
            # 使用目标路径的父目录作为临时目录，避免跨文件系统移动
            temp_dir = path.parent
            fd, tmp = tempfile.mkstemp(dir=temp_dir, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(data)
                os.replace(tmp, path)
            except BaseException:
                # BaseException 捕获 KeyboardInterrupt，确保临时文件被清理
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise

        _write(self.index_path, self._safe)
        _write(self.harmful_path, self._harmful)
        _write(self.retry_path, self._retry)
        self._append_to_registries()

        summary = {
            "safe": len(self._safe),
            "harmful": len(self._harmful),
            "retry": len(self._retry),
        }
        logger.info(f"Collection finalized: {summary}")
        return summary

    # ─────────────────────────────────────────────────────────────
    # Registry 集成
    # ─────────────────────────────────────────────────────────────

    def load_from_registry(self, registry: "SkillRegistry") -> dict[str, int]:
        """从 SkillRegistry 预加载已知条目到对应桶。

        Args:
            registry: SkillRegistry 查询接口

        Returns:
            {"safe": n, "harmful": m, "failed": k} 预加载数量
        """
        counts: dict[str, int] = {"safe": 0, "harmful": 0, "failed": 0}

        # 加载已知安全
        for name in registry.get_safe_names():
            record = registry.get_record(name)
            if record:
                self._safe.append({
                    "name": record.name,
                    "source_path": record.source_path,
                    "scan_timestamp": record.verified_at,
                    "findings": record.findings,
                    "scanners_used": record.scanners_used,
                    "scanners_failed": record.scanners_failed,
                    "scanner_summaries": record.metadata.get("scanner_summaries", []) if record.metadata else [],
                })
                if record.source_path:
                    self._path_index[record.source_path] = "safe"
                counts["safe"] += 1

        # 加载已知有害
        for name in registry.get_harmful_names():
            record = registry.get_record(name)
            if record:
                self._harmful.append({
                    "name": record.name,
                    "source_path": record.source_path,
                    "scan_timestamp": record.verified_at,
                    "findings": record.findings,
                    "scanners_used": record.scanners_used,
                    "scanners_failed": record.scanners_failed,
                    "scanner_summaries": record.metadata.get("scanner_summaries", []) if record.metadata else [],
                })
                if record.source_path:
                    self._path_index[record.source_path] = "harmful"
                counts["harmful"] += 1

        # 加载已知失败
        for name in registry.get_failed_names():
            record = registry.get_record(name)
            if record:
                self._retry.append({
                    "name": record.name,
                    "source_path": record.source_path,
                    "failed_scanners": record.scanners_failed,
                    "scan_timestamp": record.verified_at,
                    "findings": record.findings,
                    "scanners_used": record.scanners_used,
                    "scanner_summaries": record.metadata.get("scanner_summaries", []) if record.metadata else [],
                })
                if record.source_path:
                    self._path_index[record.source_path] = "failed"
                counts["failed"] += 1

        self._preloaded_safe_count = len(self._safe)
        self._preloaded_harmful_count = len(self._harmful)
        self._preloaded_retry_count = len(self._retry)
        logger.info(f"从注册表预加载: safe={counts['safe']}, harmful={counts['harmful']}, failed={counts['failed']}")
        return counts

    def is_already_known(self, skill_name_or_path: str | Path) -> str | None:
        """检查 skill 是否已在任意桶中。

        Returns:
            "safe" | "harmful" | "failed" | None
        """
        key = str(skill_name_or_path)
        # O(1) 查找：优先用 source_path 精确匹配
        if key in self._path_index:
            return self._path_index[key]
        # 备用：按 name 匹配（遍历索引的 name）
        name = Path(key).name
        for entry in self._safe:
            if entry.get("name") == name:
                return "safe"
        for entry in self._harmful:
            if entry.get("name") == name:
                return "harmful"
        for entry in self._retry:
            if entry.get("name") == name:
                return "failed"
        return None

    def set_registry_paths(
        self,
        benign_path: Path | None = None,
        malicious_path: Path | None = None,
        failed_path: Path | None = None,
    ) -> None:
        """设置注册表路径，finalize() 后自动追加条目到对应注册表。"""
        self._registry_benign_path = benign_path
        self._registry_malicious_path = malicious_path
        self._registry_failed_path = failed_path

    def _append_to_registries(self) -> None:
        """将本次收集的条目追加到对应注册表文件。"""
        from .benign_skills_manager import BenignSkillsManager
        from .failed_skills_manager import FailedSkillsManager
        from .malicious_skills_manager import MaliciousSkillsManager

        new_safe = self._safe[self._preloaded_safe_count:]
        new_harmful = self._harmful[self._preloaded_harmful_count:]
        new_retry = self._retry[self._preloaded_retry_count:]

        # 追加安全条目
        if self._registry_benign_path:
            manager = BenignSkillsManager.from_path(self._registry_benign_path)
            for entry in new_safe:
                # 构造兼容 scan_result 格式
                scan_result = {
                    "summary": {
                        "findings_by_severity": entry.get("findings", {}),
                        "total_findings": sum(entry.get("findings", {}).values()),
                        "scanners_used": entry.get("scanners_used", []),
                        "scanners_failed": entry.get("scanners_failed", []),
                    }
                }
                manager.add_benign(
                    Path(entry["source_path"]),
                    scan_result,
                    source="safe_collector",
                )
            manager.save()
            logger.info(f"追加 {len(new_safe)} 条安全记录到 {self._registry_benign_path}")

        # 追加有害条目
        if self._registry_malicious_path:
            try:
                manager = MaliciousSkillsManager(self._registry_malicious_path, _warn_deprecated=False)
                for entry in new_harmful:
                    scan_result = {
                        "summary": {
                            "findings_by_severity": entry.get("findings", {}),
                            "total_findings": sum(entry.get("findings", {}).values()),
                            "scanners_used": entry.get("scanners_used", []),
                            "scanners_failed": entry.get("scanners_failed", []),
                        }
                    }
                    manager.add_malicious(
                        Path(entry["source_path"]),
                        scan_result,
                        source="safe_collector",
                    )
                manager.save()
                logger.info(f"追加 {len(new_harmful)} 条有害记录到 {self._registry_malicious_path}")
            except Exception as e:
                logger.warning(f"追加有害记录失败: {e}")

        # 追加失败条目
        if self._registry_failed_path:
            try:
                manager = FailedSkillsManager(self._registry_failed_path, _warn_deprecated=False)
                for entry in new_retry:
                    manager.add_failure(
                        Path(entry["source_path"]),
                        {
                            "summary": {
                                "scanners_used": entry.get("scanners_used", []),
                                "scanners_failed": entry.get("failed_scanners", []),
                            }
                        },
                        scanners_failed=entry.get("failed_scanners", []),
                        source="safe_collector",
                    )
                manager.save()
                logger.info(f"追加 {len(new_retry)} 条失败记录到 {self._registry_failed_path}")
            except Exception as e:
                logger.warning(f"追加失败记录失败: {e}")
