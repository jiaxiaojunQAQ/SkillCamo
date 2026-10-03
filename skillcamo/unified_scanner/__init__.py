"""
统一技能扫描器 (Unified Skill Scanner)

整合多个技能安全扫描器，提供一致的输入输出接口。
包含扫描管线、对抗生成器和安全 skill 收集功能。

支持的扫描器 (名字与底层脚本文件名一致):
- scan_skill_auditor: ClawGuard Auditor (CG-A)
- scan_cisco: Cisco AI Skill Scanner
- scan_hss: LLM-based Security Scanner
- scan_skill_vetter: Skill Vetter (Claude Code)
- scan_skillfortify: SkillFortify 静态分析
- scan_skill_slowmist: SlowMist Agent Security
- scan_execscan: Execution-grounded multimodal scanner

基本用法:
    from unified_scanner import UnifiedSkillScanner, quick_scan

    # 快速扫描
    result = quick_scan("/path/to/skill")
    print(result['summary']['is_safe'])

    # 高级用法
    scanner = UnifiedSkillScanner(enabled_scanners=['scan_cisco'])
    result = scanner.scan("/path/to/skill")

    # 分阶段扫描
    from unified_scanner import PhasedSkillScanner
    phased_scanner = PhasedSkillScanner()
    result = phased_scanner.scan_phased("/path/to/skill")

特性:
    - 统一的JSON输出格式
    - 并行执行多个扫描器
    - 超时控制和错误隔离
    - 支持启用/禁用特定扫描器
    - 分阶段扫描，发现有害立即停止
    - 失败技能管理和重试
    - 对抗测试生成器（bash_script_drop, SkillCamo）
    - 安全 skill 收集（通过 run.action: collect-safe）
"""

from .models import (
    BatchScanResult,
    BatchScanSummary,
    ScanSummary,
    Severity,
    SourceScanner,
    ThreatCategory,
    UnifiedFinding,
    UnifiedScanResult,
)
from .scanner import UnifiedSkillScanner, create_scanner, quick_scan
from .config import UnifiedScannerConfig, ScannerConfig
from .phased_scanner import PhasedSkillScanner, create_phased_scanner, quick_phased_scan
from .failed_skills_manager import FailedSkillsManager, create_failed_manager
from .malicious_skills_manager import MaliciousSkillsManager, create_malicious_manager
from .scan_history import ScanHistory, create_history_manager
from .adapters.registry import create_default_registry

# Pipeline (from adversarial)
from .pipeline import (
    PipelineOrchestrator,
    PipelineResult,
    PipelineAttempt,
    AdversarialConfig,
)

# Generators (from adversarial)
from .generators import (
    BaseGenerator,
    GeneratorConfig,
    GeneratorRegistry,
    load_generator_from_config,
    create_generator,
)

# Scanner wrappers
from .pipeline.scanner_wrapper import (
    ScannerWrapper,
    UnifiedScannerWrapper,
)

__version__ = "1.0.0"
__all__ = [
    # 主类
    "UnifiedSkillScanner",
    "PhasedSkillScanner",
    # 便捷函数
    "create_scanner",
    "quick_scan",
    "create_phased_scanner",
    "quick_phased_scan",
    # 数据模型
    "UnifiedScanResult",
    "BatchScanResult",
    "UnifiedFinding",
    "ScanSummary",
    "BatchScanSummary",
    "Severity",
    "ThreatCategory",
    "SourceScanner",
    # 配置
    "UnifiedScannerConfig",
    "ScannerConfig",
    # 管理器
    "FailedSkillsManager",
    "create_failed_manager",
    "MaliciousSkillsManager",
    "create_malicious_manager",
    "ScanHistory",
    "create_history_manager",
    "create_default_registry",
    # Pipeline
    "PipelineOrchestrator",
    "PipelineResult",
    "PipelineAttempt",
    "AdversarialConfig",
    # Generators
    "BaseGenerator",
    "GeneratorConfig",
    "GeneratorRegistry",
    "load_generator_from_config",
    "create_generator",
    # Scanner wrappers
    "ScannerWrapper",
    "UnifiedScannerWrapper",
]
