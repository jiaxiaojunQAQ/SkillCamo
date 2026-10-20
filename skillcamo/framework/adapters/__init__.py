"""
扫描器适配器模块

将各扫描器的输出转换为统一格式。

论文评估的 6 个 baseline + 本文方法 ExecScan。
"""

from .base import BaseAdapter
from .scan_cisco import ScanCiscoAdapter
from .scan_hss import ScanHssAdapter
from .scan_skill_vetter import ScanSkillVetterAdapter
from .scan_skill_auditor import ScanSkillAuditorAdapter
from .scan_skillfortify import ScanSkillfortifyAdapter
from .scan_skill_slowmist import ScanSkillSlowmistAdapter
from .scan_execscan import ScanExecscanAdapter
from .skill_scanner_base import SkillBasedScannerAdapter
from .registry import AdapterRegistry, create_default_registry

__all__ = [
    "BaseAdapter",
    "SkillBasedScannerAdapter",
    "ScanCiscoAdapter",
    "ScanHssAdapter",
    "ScanSkillVetterAdapter",
    "ScanSkillAuditorAdapter",
    "ScanSkillfortifyAdapter",
    "ScanSkillSlowmistAdapter",
    "ScanExecscanAdapter",
    "AdapterRegistry",
    "create_default_registry",
]
