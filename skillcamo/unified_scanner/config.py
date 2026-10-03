"""
统一扫描器配置管理

支持 YAML 配置文件（含 include）、环境变量和 JSON 的分层配置。

9个扫描器，使用唯一 canonical scanner id。
"""

import functools
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# 支持作为包使用或直接运行
try:
    from .paths import (
        get_project_root,
        get_scanners_root,
        get_env_file_path,
        get_scanner_path,
    )
except ImportError:
    # 直接运行时的导入
    sys.path.insert(0, str(Path(__file__).parent))
    from paths import (
        get_project_root,
        get_scanners_root,
        get_env_file_path,
        get_scanner_path,
    )


@dataclass
class ScannerConfig:
    """单个扫描器的配置"""
    enabled: bool = True
    timeout: int | None = None
    priority: int = 0  # 优先级，数字越大越优先
    api_key: str | None = None
    base_url: str | None = None  # 自定义 API endpoint（从 base_url_env 解析）
    model: str | None = None  # LLM 模型名（如 gpt-5-mini, claude-sonnet-4-20250514）
    model_a: str | None = None  # scan_execscan / scan_fusion 第一阶段模型
    model_b: str | None = None  # scan_execscan / scan_fusion 第二阶段模型
    ablation_mode: str | None = None  # scan_fusion 消融模式（"static" / "slowmist" / "artifact" / "simulation" / None）
    k_value: int | None = None  # scan_fusion Phase II 上下文场景数（k 值调参）
    induction_mode: bool = False  # (deprecated, kept for config compat) 原 scan_execscan IAEP 开关
    ensemble: list | None = None  # scan_iaep 集成成员列表（每项 {model, api_key_env/api_key, base_url, temperature, persona, persona_prompt}）
    ccsw_provider: str | None = None  # ccsw provider id：为 Claude CLI scanner 注入该 provider 的 ANTHROPIC_* env（建议填 id，名称可能歧义）
    # scan_fsm 图片恢复(SkillCamo)的专用视觉端点：文本模型(如 MiniMax)可只做文本，
    # 图片交给视觉模型(如 Gemini)。从 vision_api_key_env / vision_base_url_env 解析。
    vision_api_key: str | None = None
    vision_base_url: str | None = None
    vision_model: str | None = None
    trusted_endpoint_origins: list[str] = field(default_factory=list)
    trusted_fetch_origins: list[str] | None = None


@dataclass
class LLMJudgementConfig:
    """LLM scanner-output judgement configuration."""

    enabled: bool = True
    provider: str = "openai"
    model: str = "gpt-5-mini"
    api_key: str | None = None
    base_url: str | None = None
    timeout: int = 120
    save_audit: bool = True


@dataclass
class SandboxConfig:
    """Docker 沙盒执行配置。

    enabled=True 时，扫描不再在宿主进程内跑，而是把 skill 挂进一次性容器、
    在容器内跑 scanner、把结果 JSON 读回宿主（scanner 逻辑零改动）。
    """

    enabled: bool = False
    backend: str = "docker"  # 目前仅支持 docker（直连 subprocess）
    # 单镜像回退（族/scanner 未在 images 里指定时用）。留空则用各 family 默认 tag。
    image: str = "skill-scanner:latest"
    # per-scanner 镜像映射：family 名(base/fsm/ml/cisco/claude)或 scanner 名 -> 镜像 tag。
    # 缺省用 images.DEFAULT_FAMILY_IMAGES。每个 scanner 按其环境族选镜像、各起一个容器。
    images: dict = field(default_factory=dict)
    # egress: bridge + iptables 白名单（仅放行 LLM 端点）；none: --network=none 纯离线
    network: str = "egress"
    # 允许出站的主机名（egress 模式下装 iptables 白名单）；为空时容器 entrypoint 会
    # 尝试从注入的 *_URL env 自动推导，见 docker/scanner/entrypoint.sh
    egress_allow: list[str] = field(default_factory=list)
    # 透传进容器的 env 变量名（API keys / base urls）
    env_passthrough: list[str] = field(default_factory=list)
    cpus: str = "4"
    memory: str = "8g"
    pids_limit: int = 512
    # 容器镜像里仓库根的挂载点（宿主项目根 → 容器路径）
    build_context: str = "."
    timeout: int = 1800  # 单个 skill 的整体容器超时（秒）
    # 非 root 运行：填容器内用户名/uid（如 "test"）时 `docker run --user <run_user>`，
    # 容器不以 root 起；entrypoint 检测到非 root 会跳过 iptables 并直接 exec（不 gosu）。
    # 留空则维持原行为（root 起 → iptables → gosu scanuser）。
    run_user: str | None = None
    # claude 族 scanner 账号登录：True 时把宿主 ~/.claude 账号登录凭证（净化后只读）
    # 挂进 claude 容器，并让 adapter 去掉 --bare 以读取 OAuth（否则 --bare 只认 API key）。
    claude_login: bool = False


@dataclass
class LLMAuditConfig:
    """LLM 调用审计配置 — 保存所有 LLM 输入输出。"""

    enabled: bool = False
    output_dir: Path = field(default_factory=lambda: Path("output/llm_audit"))
    include_full_prompt: bool = True
    include_full_response: bool = True


@dataclass
class UnifiedScannerConfig:
    """统一扫描器的完整配置

    扫描器：
    - scan_skill_auditor: ClawGuard Auditor (CG-A)
    - scan_cisco: Cisco AI Skill Scanner
    - scan_hss: LLM-based Security Scanner
    - scan_skill_vetter: Skill Vetter (Claude Code)
    - scan_skillfortify: SkillFortify 静态分析 (22+ 框架)
    - scan_skill_slowmist: SlowMist Agent Security (知识库安全模式检测)
    - scan_execscan: Execution-grounded multimodal scanner (本文方法)
    """

    # 项目路径配置
    project_root: Path = field(default_factory=get_project_root)
    scanners_root: Path = field(default_factory=get_scanners_root)
    env_file: Path = field(default_factory=get_env_file_path)

    # 全局设置
    max_workers: int = 5  # 单 skill 内 scanner 级并行度
    max_skill_workers: int = 3  # 多 skill 批量并行度
    enable_retry: bool = True
    max_retries: int = 3
    retry_backoff: float = 1.5

    # Claude CLI 并发控制
    max_claude_concurrent: int = 3  # 同时调用 Claude CLI 的最大数量（auditor/vetter/skill_slowmist 三个 scanner）

    # 输出设置
    save_raw_results: bool = True
    output_format: str = "json"  # json, sarif, console
    llm_judgement: LLMJudgementConfig = field(default_factory=LLMJudgementConfig)
    llm_audit: LLMAuditConfig = field(default_factory=LLMAuditConfig)
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)

    # 各扫描器配置
    scan_skill_auditor: ScannerConfig = field(
        default_factory=lambda: ScannerConfig(enabled=True)
    )
    scan_cisco: ScannerConfig = field(default_factory=ScannerConfig)
    scan_hss: ScannerConfig = field(
        default_factory=lambda: ScannerConfig(enabled=True)
    )
    scan_skill_vetter: ScannerConfig = field(
        default_factory=lambda: ScannerConfig(enabled=True)
    )
    scan_skillfortify: ScannerConfig = field(
        default_factory=lambda: ScannerConfig(enabled=True)
    )
    scan_skill_slowmist: ScannerConfig = field(
        default_factory=lambda: ScannerConfig(enabled=True)
    )
    scan_execscan: ScannerConfig = field(
        default_factory=lambda: ScannerConfig(enabled=True)
    )
    scanner_order: list[str] = field(
        default_factory=lambda: [
            "scan_skill_auditor",
            "scan_cisco",
            "scan_hss",
            "scan_skill_vetter",
            "scan_skillfortify",
            "scan_skill_slowmist",
            "scan_execscan",
        ]
    )

    @classmethod
    def from_env(cls) -> "UnifiedScannerConfig":
        """从环境变量加载配置

        自动从项目根目录的 .env 文件加载配置，然后从环境变量读取。
        """
        config = cls()

        # 首先加载 .env 文件（统一入口）
        config._load_env_file()

        # 记录原始环境变量值（用于调试）
        _logger = logging.getLogger(__name__)

        # 环境变量映射
        env_mappings = [
            ("UNIFIED_MAX_WORKERS", "max_workers", int),
            ("UNIFIED_MAX_SKILL_WORKERS", "max_skill_workers", int),
            ("UNIFIED_ENABLE_RETRY", "enable_retry", lambda x: x.lower() == "true"),
            ("UNIFIED_MAX_RETRIES", "max_retries", int),
            ("UNIFIED_RETRY_BACKOFF", "retry_backoff", float),
            ("CLAUDE_CLI_MAX_CONCURRENT", "max_claude_concurrent", int),

            # LLM Scanner
            ("ANTHROPIC_API_KEY", "scan_hss.api_key", str),
            ("OPENAI_API_KEY", "scan_hss.api_key", str),
            ("ENABLE_SCAN_HSS", "scan_hss.enabled", _parse_bool),

            # Skill Vetter
            ("ENABLE_SCAN_SKILL_VETTER", "scan_skill_vetter.enabled", _parse_bool),

            # ClawGuard Auditor
            ("ENABLE_SCAN_SKILL_AUDITOR", "scan_skill_auditor.enabled", _parse_bool),

            # Cisco Scanner
            ("ENABLE_SCAN_CISCO", "scan_cisco.enabled", _parse_bool),

            # SkillFortify
            ("ENABLE_SCAN_SKILLFORTIFY", "scan_skillfortify.enabled", _parse_bool),

            # SlowMist
            ("ENABLE_SCAN_SKILL_SLOWMIST", "scan_skill_slowmist.enabled", _parse_bool),
            ("ENABLE_SCAN_EXECSCAN", "scan_execscan.enabled", _parse_bool),
            ("ENABLE_LLM_JUDGEMENT", "llm_judgement.enabled", _parse_bool),
            ("LLM_JUDGEMENT_MODEL", "llm_judgement.model", str),
            ("LLM_JUDGEMENT_TIMEOUT", "llm_judgement.timeout", int),
        ]

        for env_key, attr_path, converter in env_mappings:
            value = os.getenv(env_key)
            if value is not None:
                _set_nested_attr(config, attr_path, converter(value))

        # 输出关键配置值（用于验证配置是否正确加载）
        _logger.info(
            f"Config loaded: max_workers={config.max_workers}, "
            f"max_claude_concurrent={config.max_claude_concurrent}"
        )

        return config

    @classmethod
    def from_file(cls, path: str | Path) -> "UnifiedScannerConfig":
        """从 JSON 配置文件加载"""
        import json

        path = Path(path)
        if not path.exists():
            return cls()

        with open(path) as f:
            data = json.load(f)

        return _from_dict(cls, data)

    @classmethod
    def from_env_file(cls, env_path: str | Path) -> "UnifiedScannerConfig":
        """从 .env 文件加载配置"""
        env_path = Path(env_path)
        if not env_path.exists():
            return cls()

        # 临时加载环境变量
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                # 去掉引号
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                # 不覆盖已显式导出的环境变量：.env 仅提供默认值，进程环境优先。
                # 与 entry.py 的 load_dotenv(override=False) 语义一致，保证
                # "export OPENAI_*/HSS_*/... 指向自定义端点" 的工作流不被根 .env 清掉。
                os.environ.setdefault(key, value)

        return cls.from_env()

    def to_file(self, path: str | Path) -> None:
        """保存到 JSON 配置文件"""
        import json
        from dataclasses import asdict

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)

    def get_scanner_config(self, scanner_name: str) -> ScannerConfig:
        """获取指定扫描器的配置"""
        if not hasattr(self, scanner_name):
            raise KeyError(f"Unknown scanner config: {scanner_name}")
        return getattr(self, scanner_name)

    def get_scanner_timeout(self, scanner_name: str) -> int:
        """获取指定扫描器的超时配置；未配置时直接报错。"""
        scanner_config = self.get_scanner_config(scanner_name)
        if scanner_config.timeout is None:
            raise ValueError(f"Missing timeout configuration for scanner: {scanner_name}")
        return scanner_config.timeout

    def _load_env_file(self) -> None:
        """从 .env 文件加载环境变量（内部方法）"""
        env_file = self.env_file
        if not env_file.exists():
            return

        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                # 去掉引号
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                # 只设置未设置的环境变量（环境变量优先级更高）
                if key not in os.environ:
                    os.environ[key] = value

    def get_scanner_path(self, scanner_name: str) -> Path:
        """
        获取指定扫描器的路径

        Args:
            scanner_name: 扫描器名称（如 "scan_cisco"）

        Returns:
            扫描器的绝对路径
        """
        return get_scanner_path(scanner_name)


def _parse_bool(value: str) -> bool:
    """解析布尔值字符串"""
    return value.lower() in ("true", "1", "yes", "on")


def _set_nested_attr(obj: Any, attr_path: str, value: Any) -> None:
    """设置嵌套属性"""
    parts = attr_path.split(".")
    target = obj
    for part in parts[:-1]:
        target = getattr(target, part)
    setattr(target, parts[-1], value)


def _from_dict(cls: type, data: dict[str, Any]) -> Any:
    """从字典创建数据类实例"""
    if not data:
        return cls()

    # 处理嵌套的 ScannerConfig
    field_types = {f.name: f.type for f in cls.__dataclass_fields__.values()}

    kwargs = {}
    for key, value in data.items():
        if key in field_types:
            field_type = field_types[key]
            if field_type == ScannerConfig or (hasattr(field_type, "__origin__") and field_type.__origin__ is field and field_type.__args__[0] == ScannerConfig):
                kwargs[key] = ScannerConfig(**value) if isinstance(value, dict) else value
            else:
                kwargs[key] = value

    return cls(**kwargs)


# ============================================================
# YAML 配置加载（支持 include）
# ============================================================

def deep_merge(base: dict, override: dict) -> dict:
    """递归合并两个字典，override 中的值优先。

    对于嵌套 dict，递归合并而非覆盖。
    对于其他类型（list、str、int 等），override 覆盖 base。
    """
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def get_adversarial_defaults(raw: dict) -> dict:
    """Return public adversarial defaults from `defaults.adversarial`."""

    defaults = raw.get("defaults", {})
    adversarial = defaults.get("adversarial", {}) if isinstance(defaults, dict) else {}

    if not isinstance(adversarial, dict):
        adversarial = {}

    return dict(adversarial)


def _load_yaml_config_impl(path: Path) -> dict:
    """加载 YAML 配置文件的内部实现（无缓存）。

    解析流程：
    1. 读取主 YAML 文件为 dict
    2. 如果存在 includes: [...]，按顺序加载每个子文件
    3. 用 deep_merge 合并：子文件提供默认值，主文件覆盖
    """
    import yaml

    if not path.exists():
        return {}

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    includes = data.pop("includes", None)
    if not includes:
        return data

    base_dir = path.parent
    merged: dict = {}
    for inc_path in includes:
        inc_file = base_dir / inc_path
        if inc_file.exists():
            with open(inc_file) as f:
                inc_data = yaml.safe_load(f) or {}
            merged = deep_merge(merged, inc_data)

    # 主文件的值优先于 include 文件
    merged = deep_merge(merged, data)
    return merged


@functools.lru_cache(maxsize=32)
def _load_yaml_config_cached(path_str: str) -> dict:
    """内部缓存实现，接收字符串路径以支持 lru_cache。"""
    return _load_yaml_config_impl(Path(path_str))


def load_yaml_config(path: Path) -> dict:
    """加载 YAML 配置文件，支持 includes 字段和缓存。

    解析流程：
    1. 读取主 YAML 文件为 dict
    2. 如果存在 includes: [...]，按顺序加载每个子文件
    3. 用 deep_merge 合并：子文件提供默认值，主文件覆盖

    Args:
        path: 主 YAML 配置文件路径

    Returns:
        合并后的配置字典
    """
    return _load_yaml_config_cached(str(path.resolve()))


def _safe_output_path(name: str) -> Path:
    try:
        from ..output_paths import get_default_output_root
    except ImportError:
        from skillcamo.output_paths import get_default_output_root
    return get_default_output_root() / "safe_collection" / name


@dataclass
class SafeCollectionConfig:
    """安全 skill 收集配置"""
    output_dir: Path = field(default_factory=lambda: _safe_output_path(""))
    safe_dir: Path = field(default_factory=lambda: _safe_output_path("safe_skills"))
    index_path: Path = field(default_factory=lambda: _safe_output_path("safe_skills.json"))
    retry_path: Path = field(default_factory=lambda: _safe_output_path("safe_skills_retry.json"))
    harmful_path: Path = field(default_factory=lambda: _safe_output_path("harmful_skills.json"))
    default_generator: str = "direct_scan"
    # Registry 路径配置
    benign_registry_path: Path = field(default_factory=lambda: Path("data/benign_skills.json"))
    malicious_registry_path: Path = field(default_factory=lambda: Path("data/malicious_skills.json"))
    failed_registry_path: Path = field(default_factory=lambda: Path("data/failed_skills.json"))


@dataclass
class RunConfig:
    """全局运行参数"""
    action: str = "adversarial"  # adversarial, scan, scan-dir, collect-safe, status, list-*, validate-config
    target: Path | None = None
    max_workers: int = 5


def _resolve_api_key(api_key_env: str | None) -> str | None:
    """从环境变量名解析实际 API key 值。"""
    if not api_key_env:
        return None
    return os.environ.get(api_key_env)


def _resolve_base_url(base_url_env: str | None) -> str | None:
    """从环境变量名解析自定义 base URL 值。"""
    if not base_url_env:
        return None
    return os.environ.get(base_url_env)


def load_unified_config_from_yaml(path: str | Path) -> tuple[UnifiedScannerConfig, RunConfig, SafeCollectionConfig, dict]:
    """从 YAML 配置文件加载完整配置。

    Returns:
        (scanner_config, run_config, safe_collection_config, raw_dict)
        raw_dict 包含 adversarial 部分（generators/generator/defaults.adversarial）供 pipeline 使用。
    """
    raw = load_yaml_config(Path(path))

    # 构建 scanner config
    scanner_config = UnifiedScannerConfig.from_env()

    # 从 YAML 的 scanners: 段覆盖 scanner 配置
    scanners_section = raw.get("scanners", {})
    for scanner_name, scanner_cfg in scanners_section.items():
        if hasattr(scanner_config, scanner_name) and isinstance(scanner_cfg, dict):
            existing: ScannerConfig = getattr(scanner_config, scanner_name)
            if "timeout" in scanner_cfg:
                existing.timeout = scanner_cfg["timeout"]
            if "priority" in scanner_cfg:
                existing.priority = scanner_cfg["priority"]
            if "api_key_env" in scanner_cfg:
                existing.api_key = _resolve_api_key(scanner_cfg["api_key_env"])
            if "base_url_env" in scanner_cfg:
                existing.base_url = _resolve_base_url(scanner_cfg["base_url_env"])
            if "vision_api_key_env" in scanner_cfg:
                existing.vision_api_key = _resolve_api_key(scanner_cfg["vision_api_key_env"])
            if "vision_base_url_env" in scanner_cfg:
                existing.vision_base_url = _resolve_base_url(scanner_cfg["vision_base_url_env"])
            if "trusted_fetch_origins" in scanner_cfg:
                existing.trusted_fetch_origins = scanner_cfg["trusted_fetch_origins"]
            if "trusted_endpoint_origins" in scanner_cfg:
                existing.trusted_endpoint_origins = scanner_cfg["trusted_endpoint_origins"]
            if "vision_model" in scanner_cfg:
                existing.vision_model = scanner_cfg["vision_model"]
            if "model" in scanner_cfg:
                existing.model = scanner_cfg["model"]
            if "model_a" in scanner_cfg:
                existing.model_a = scanner_cfg["model_a"]
            if "model_b" in scanner_cfg:
                existing.model_b = scanner_cfg["model_b"]
            if "ablation_mode" in scanner_cfg:
                existing.ablation_mode = scanner_cfg["ablation_mode"]
            if "k_value" in scanner_cfg:
                existing.k_value = int(scanner_cfg["k_value"])
            if "induction_mode" in scanner_cfg:
                existing.induction_mode = bool(scanner_cfg["induction_mode"])
            if "ensemble" in scanner_cfg and isinstance(scanner_cfg["ensemble"], list):
                resolved_members = []
                for member in scanner_cfg["ensemble"]:
                    if not isinstance(member, dict):
                        continue
                    m = dict(member)
                    if "api_key_env" in m:
                        m["api_key"] = _resolve_api_key(m.pop("api_key_env"))
                    if "base_url_env" in m:
                        m["base_url"] = _resolve_base_url(m.pop("base_url_env"))
                    resolved_members.append(m)
                existing.ensemble = resolved_members
            if "ccsw_provider" in scanner_cfg:
                existing.ccsw_provider = scanner_cfg["ccsw_provider"]

    llm_judgement_section = raw.get("llm_judgement", {})
    if isinstance(llm_judgement_section, dict):
        if "enabled" in llm_judgement_section:
            enabled_value = llm_judgement_section["enabled"]
            scanner_config.llm_judgement.enabled = (
                _parse_bool(enabled_value) if isinstance(enabled_value, str) else bool(enabled_value)
            )
        if "provider" in llm_judgement_section:
            scanner_config.llm_judgement.provider = str(llm_judgement_section["provider"])
        if "model" in llm_judgement_section:
            scanner_config.llm_judgement.model = str(llm_judgement_section["model"])
        if "api_key_env" in llm_judgement_section:
            scanner_config.llm_judgement.api_key = _resolve_api_key(llm_judgement_section["api_key_env"])
        if "base_url_env" in llm_judgement_section:
            scanner_config.llm_judgement.base_url = _resolve_base_url(llm_judgement_section["base_url_env"])
        if "timeout" in llm_judgement_section:
            scanner_config.llm_judgement.timeout = int(llm_judgement_section["timeout"])
        if "save_audit" in llm_judgement_section:
            save_audit_value = llm_judgement_section["save_audit"]
            scanner_config.llm_judgement.save_audit = (
                _parse_bool(save_audit_value) if isinstance(save_audit_value, str) else bool(save_audit_value)
            )

    # 从 llm_audit: 段加载 LLM 审计配置
    llm_audit_section = raw.get("llm_audit", {})
    if isinstance(llm_audit_section, dict):
        if "enabled" in llm_audit_section:
            enabled_value = llm_audit_section["enabled"]
            scanner_config.llm_audit.enabled = (
                _parse_bool(enabled_value) if isinstance(enabled_value, str) else bool(enabled_value)
            )
        if "output_dir" in llm_audit_section:
            scanner_config.llm_audit.output_dir = Path(llm_audit_section["output_dir"])
        if "include_full_prompt" in llm_audit_section:
            include_prompt_value = llm_audit_section["include_full_prompt"]
            scanner_config.llm_audit.include_full_prompt = (
                _parse_bool(include_prompt_value) if isinstance(include_prompt_value, str) else bool(include_prompt_value)
            )
        if "include_full_response" in llm_audit_section:
            include_response_value = llm_audit_section["include_full_response"]
            scanner_config.llm_audit.include_full_response = (
                _parse_bool(include_response_value) if isinstance(include_response_value, str) else bool(include_response_value)
            )

    # 从 sandbox: 段加载 Docker 沙盒执行配置
    sandbox_section = raw.get("sandbox", {})
    if isinstance(sandbox_section, dict):
        sb = scanner_config.sandbox
        if "enabled" in sandbox_section:
            enabled_value = sandbox_section["enabled"]
            sb.enabled = _parse_bool(enabled_value) if isinstance(enabled_value, str) else bool(enabled_value)
        if "backend" in sandbox_section:
            sb.backend = str(sandbox_section["backend"])
        if "image" in sandbox_section:
            sb.image = str(sandbox_section["image"])
        if isinstance(sandbox_section.get("images"), dict):
            sb.images = {str(k): str(v) for k, v in sandbox_section["images"].items()}
        if "network" in sandbox_section:
            sb.network = str(sandbox_section["network"])
        if isinstance(sandbox_section.get("egress_allow"), list):
            sb.egress_allow = [str(h) for h in sandbox_section["egress_allow"]]
        if isinstance(sandbox_section.get("env_passthrough"), list):
            sb.env_passthrough = [str(k) for k in sandbox_section["env_passthrough"]]
        if "cpus" in sandbox_section:
            sb.cpus = str(sandbox_section["cpus"])
        if "memory" in sandbox_section:
            sb.memory = str(sandbox_section["memory"])
        if "pids_limit" in sandbox_section:
            sb.pids_limit = int(sandbox_section["pids_limit"])
        if "build_context" in sandbox_section:
            sb.build_context = str(sandbox_section["build_context"])
        if "timeout" in sandbox_section:
            sb.timeout = int(sandbox_section["timeout"])
        if "run_user" in sandbox_section:
            ru = sandbox_section["run_user"]
            sb.run_user = str(ru) if ru else None
        if "claude_login" in sandbox_section:
            sb.claude_login = bool(sandbox_section["claude_login"])

    # 从 run: 段构建 RunConfig
    run_section = raw.get("run", {})
    run_config = RunConfig(
        action=run_section.get("action", "adversarial"),
        target=Path(run_section["target"]) if run_section.get("target") else None,
        max_workers=run_section.get("max_workers", 2),
    )
    scanner_config.max_workers = run_config.max_workers
    scanner_config.max_skill_workers = run_section.get(
        "max_skill_workers",
        scanner_config.max_skill_workers,
    )
    if "retries" in run_section:
        scanner_config.max_retries = run_section["retries"]
    _validate_enabled_scanner_timeouts(raw, scanner_config)

    # 从 safe_collection: 段构建 SafeCollectionConfig
    safe_section = raw.get("safe_collection", {})
    safe_defaults = SafeCollectionConfig()

    # 如果指定了 output_dir，用它计算子路径；否则用默认值
    output_dir = Path(safe_section["output_dir"]) if safe_section.get("output_dir") else safe_defaults.output_dir

    safe_config = SafeCollectionConfig(
        output_dir=output_dir,
        safe_dir=Path(safe_section["safe_dir"]) if safe_section.get("safe_dir") else output_dir / "safe_skills",
        index_path=Path(safe_section["index_path"]) if safe_section.get("index_path") else output_dir / "safe_skills.json",
        retry_path=Path(safe_section["retry_path"]) if safe_section.get("retry_path") else output_dir / "safe_skills_retry.json",
        harmful_path=Path(safe_section["harmful_path"]) if safe_section.get("harmful_path") else output_dir / "harmful_skills.json",
        default_generator=safe_section.get("default_generator", "direct_scan"),
        benign_registry_path=Path(safe_section["benign_registry_path"]) if safe_section.get("benign_registry_path") else safe_defaults.benign_registry_path,
        malicious_registry_path=Path(safe_section["malicious_registry_path"]) if safe_section.get("malicious_registry_path") else safe_defaults.malicious_registry_path,
        failed_registry_path=Path(safe_section["failed_registry_path"]) if safe_section.get("failed_registry_path") else safe_defaults.failed_registry_path,
    )

    # 记录配置来源 YAML 路径，供 Docker 沙盒后端把 config 目录挂进容器（含 includes）。
    try:
        scanner_config._source_yaml_path = Path(path).resolve()  # type: ignore[attr-defined]
    except OSError:
        scanner_config._source_yaml_path = None  # type: ignore[attr-defined]

    return scanner_config, run_config, safe_config, raw


def _validate_enabled_scanner_timeouts(raw: dict[str, Any], scanner_config: UnifiedScannerConfig) -> None:
    enabled_list = raw.get("scanners", {}).get("enabled", [])
    missing: list[str] = []
    for scanner_name in enabled_list:
        try:
            scanner_config.get_scanner_timeout(scanner_name)
        except (KeyError, ValueError):
            missing.append(scanner_name)
    if missing:
        raise ValueError(f"Missing timeout configuration for enabled scanners: {', '.join(sorted(missing))}")
