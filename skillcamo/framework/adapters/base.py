"""
适配器基类
"""

from abc import ABC
from pathlib import Path


class BaseAdapter(ABC):
    """适配器基类"""

    scanner_name: str = "base"
    scanner_display_name: str = "Base Scanner"

    def __init__(self):
        self._available = None

    def is_available(self) -> bool:
        """检查扫描器是否可用"""
        if self._available is None:
            self._available = self._check_availability()
        return self._available

    def _check_availability(self) -> bool:
        """子类实现：检查扫描器是否可用"""
        raise NotImplementedError

    def scan(self, skill_path: str | Path, **kwargs) -> dict:
        """
        扫描指定的技能路径

        Args:
            skill_path: 技能目录路径
            **kwargs: 额外扫描参数

        Returns:
            格式如下:
            {
                "findings": [...],  # UnifiedFinding 列表（转dict）
                "metadata": {...},  # 扫描器特定的元数据
                "raw": {...},       # 原始扫描结果（可选）
            }
        """
        raise NotImplementedError

    def _normalize_findings(self, findings: list) -> list[dict]:
        """将发现转换为统一格式"""
        return [f.to_dict() if hasattr(f, "to_dict") else f for f in findings]
