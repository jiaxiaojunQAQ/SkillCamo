"""
路径配置模块 - 集中管理所有扫描器路径

使用相对路径计算，避免硬编码绝对路径。支持通过环境变量覆盖默认路径。

路径基准说明:
    - UNIFIED_SCANNER_ROOT: 本文件所在目录 (unified_scanner/)
    - SCANNERS_ROOT: skillcamo/ 目录
    - PROJECT_ROOT: 项目根目录
"""

import os
from pathlib import Path


# 目录基准
UNIFIED_SCANNER_ROOT = Path(__file__).parent
SCANNERS_ROOT = UNIFIED_SCANNER_ROOT.parent
PROJECT_ROOT = SCANNERS_ROOT.parent


# 默认扫描器路径配置（使用相对路径）
# 攻击/防御重构后：baseline 防御归入 defenses/baselines/，ExecScan 在 defenses/execscan/
BASELINES_ROOT = SCANNERS_ROOT / "defenses" / "baselines"
DEFAULT_SCANNER_PATHS = {
    # baseline 防御（归入 defenses/baselines/ 下）
    "scan_skill_auditor": BASELINES_ROOT / "scan_skill_auditor",
    "scan_cisco": BASELINES_ROOT / "scan_cisco",
    "scan_hss": BASELINES_ROOT / "scan_hss",
    "scan_skill_vetter": BASELINES_ROOT / "scan_skill_vetter",
    "scan_skillfortify": BASELINES_ROOT / "scan_skillfortify",
    "scan_skill_slowmist": BASELINES_ROOT / "scan_skill_slowmist",
    # 本文防御 ExecScan
    "scan_execscan": SCANNERS_ROOT / "defenses" / "execscan",
}


# 环境变量到路径的映射（允许用户通过环境变量覆盖）
PATH_ENV_VARS = {
    "SCAN_SKILL_AUDITOR_PATH": "scan_skill_auditor",
    "SCAN_CISCO_PATH": "scan_cisco",
    "SCAN_HSS_PATH": "scan_hss",
    "SCAN_SKILL_VETTER_PATH": "scan_skill_vetter",
    "SCAN_SKILLFORTIFY_PATH": "scan_skillfortify",
    "SCAN_SKILL_SLOWMIST_PATH": "scan_skill_slowmist",
    "SCAN_EXECSCAN_PATH": "scan_execscan",
}


def get_scanner_path(scanner_name: str) -> Path:
    """
    获取指定扫描器的路径

    优先级:
        1. 环境变量（如果设置了对应的环境变量）
        2. 默认路径

    Args:
        scanner_name: 扫描器名称（如 "scan_cisco"）

    Returns:
        扫描器的绝对路径
    """
    # 检查是否有环境变量覆盖
    for env_var, name in PATH_ENV_VARS.items():
        if name == scanner_name:
            env_path = os.environ.get(env_var)
            if env_path:
                return Path(env_path)

    # 使用默认路径
    return DEFAULT_SCANNER_PATHS.get(scanner_name, Path())


def get_project_root() -> Path:
    """获取项目根目录"""
    return PROJECT_ROOT


def get_scanners_root() -> Path:
    """获取扫描器根目录 (skillcamo/)"""
    return SCANNERS_ROOT


def get_env_file_path() -> Path:
    """
    获取统一的环境变量文件路径

    优先级:
        1. 项目根目录的 .env
        2. unified_scanner 目录的 .env
    """
    project_env = PROJECT_ROOT / ".env"
    if project_env.exists():
        return project_env

    return UNIFIED_SCANNER_ROOT / ".env"


def verify_scanner_path(scanner_name: str) -> tuple[bool, str | None]:
    """
    验证扫描器路径是否存在

    Args:
        scanner_name: 扫描器名称

    Returns:
        (exists, error_message)
    """
    path = get_scanner_path(scanner_name)

    if not path.exists():
        return False, f"路径不存在: {path}"

    return True, None


# 额外的特定路径获取函数（向后兼容）
def get_scan_cisco_path() -> Path:
    """获取 scan_cisco 路径"""
    return get_scanner_path("scan_cisco")


def get_scan_hss_path() -> Path:
    """获取 scan_hss 路径"""
    return get_scanner_path("scan_hss")


def get_agent_skills_scanner_path() -> Path:
    """获取 AgentSkillsScanner 路径"""
    return Path()


def get_skill_vetter_skill_path() -> Path:
    """获取 Skill Vetter SKILL.md 路径"""
    return get_scanner_path("scan_skill_vetter") / "SKILL.md"


def get_auditor_skill_path() -> Path:
    """获取 Auditor SKILL.md 路径"""
    return get_scanner_path("scan_skill_auditor") / "SKILL.md"


def get_slowmist_skill_path() -> Path:
    """获取 SlowMist SKILL.md 路径"""
    return get_scanner_path("scan_skill_slowmist") / "SKILL.md"
