"""
适配器注册表 - 管理所有可用的扫描器适配器
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseAdapter


class AdapterRegistry:
    """适配器注册表，管理所有可用的扫描器适配器"""

    def __init__(self):
        self._adapters: dict[str, "BaseAdapter"] = {}

    def register(self, name: str, adapter: "BaseAdapter") -> None:
        """注册适配器"""
        self._adapters[name] = adapter

    def get(self, name: str) -> "BaseAdapter | None":
        """获取适配器"""
        return self._adapters.get(name)

    def get_available(self) -> dict[str, "BaseAdapter"]:
        """获取所有可用的适配器"""
        return {
            name: adapter
            for name, adapter in self._adapters.items()
            if adapter.is_available()
        }

    def list_available(self) -> list[str]:
        """列出所有可用的适配器名称"""
        return [
            name for name, adapter in self._adapters.items() if adapter.is_available()
        ]


def create_default_registry() -> AdapterRegistry:
    """创建包含所有默认适配器的注册表

    当前标准扫描器（论文评估的 6 个 baseline + 本文方法 ExecScan）：
    - scan_cisco: Cisco AI Skill Scanner
    - scan_hss: LLM-based Security Scanner
    - scan_skill_auditor: ClawGuard Auditor (CG-A)
    - scan_skill_vetter: Skill Vetter (Claude Code)
    - scan_skillfortify: SkillFortify Scanner
    - scan_skill_slowmist: SlowMist Agent Security
    - scan_execscan: Execution-grounded multimodal scanner (ours)
    """
    from .scan_cisco import ScanCiscoAdapter
    from .scan_hss import ScanHssAdapter
    from .scan_skill_vetter import ScanSkillVetterAdapter
    from .scan_skill_auditor import ScanSkillAuditorAdapter
    from .scan_skillfortify import ScanSkillfortifyAdapter
    from .scan_skill_slowmist import ScanSkillSlowmistAdapter
    from .scan_execscan import ScanExecscanAdapter

    registry = AdapterRegistry()
    registry.register("scan_cisco", ScanCiscoAdapter())
    registry.register("scan_hss", ScanHssAdapter())
    registry.register("scan_skill_auditor", ScanSkillAuditorAdapter())
    registry.register("scan_skill_vetter", ScanSkillVetterAdapter())
    registry.register("scan_skillfortify", ScanSkillfortifyAdapter())
    registry.register("scan_skill_slowmist", ScanSkillSlowmistAdapter())
    registry.register("scan_execscan", ScanExecscanAdapter())
    return registry
