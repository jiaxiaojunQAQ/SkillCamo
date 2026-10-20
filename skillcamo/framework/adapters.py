"""
兼容转发层。

历史上 `unified_scanner/adapters.py` 同时承载过旧适配器实现与注册表，
现在统一转发到 `unified_scanner/adapters/` 包，避免继续维护两套实现。
"""

from .adapters import (
    AdapterRegistry,
    BaseAdapter,
    ScanSkillAuditorAdapter,
    ScanCiscoAdapter,
    ScanHssAdapter,
    ScanSkillfortifyAdapter,
    ScanSkillSlowmistAdapter,
    ScanSkillVetterAdapter,
    SkillBasedScannerAdapter,
    create_default_registry,
)

__all__ = [
    "AdapterRegistry",
    "BaseAdapter",
    "SkillBasedScannerAdapter",
    "ScanCiscoAdapter",
    "ScanHssAdapter",
    "ScanSkillVetterAdapter",
    "ScanSkillAuditorAdapter",
    "ScanSkillfortifyAdapter",
    "ScanSkillSlowmistAdapter",
    "create_default_registry",
]
