"""Configuration-driven entrypoint for unified scanner runs."""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import click

# 加载项目根目录 .env 文件（如果存在）
try:
    from dotenv import load_dotenv
    _project_root = Path(__file__).resolve().parent.parent.parent
    _env_file = _project_root / ".env"
    if _env_file.exists():
        load_dotenv(_env_file, override=False)
except ImportError:
    pass  # python-dotenv 未安装，跳过

from .adapters.registry import create_default_registry
from .capabilities import ALL_SCANNER_NAMES, get_availability_report
from .config import (
    RunConfig,
    SafeCollectionConfig,
    UnifiedScannerConfig,
    get_adversarial_defaults,
    load_unified_config_from_yaml,
    load_yaml_config,
)
from .models import ScanSummary, ScannerSummary, Severity, UnifiedFinding, UnifiedScanResult
from .pipeline.batch_config import BatchConfig
from .pipeline.batch_orchestrator import BatchOrchestrator
from .pipeline.config import AdversarialConfig
from .phased_scanner import PhasedSkillScanner
from .safe_collector import SafeSkillCollector
from .scanner import UnifiedSkillScanner

DEFAULT_ACTION = "direct_scan"


def _make_progress_callback():
    """创建 scanner 进度回调，输出到控制台。"""
    def _callback(current: int, total: int, message: str) -> None:
        click.echo(f"  {message}")
    return _callback


# Generator 名直接作为 action，action 即 generator
# 动态从 GeneratorRegistry 取，自动覆盖所有已注册 generator
from .generators import GeneratorRegistry as _GeneratorRegistry
GENERATOR_ACTIONS = set(_GeneratorRegistry.list_all())

UTILITY_ACTIONS = {"status", "list-scanners", "list-generators", "validate-config"}

SUPPORTED_ACTIONS = {
    "collect-safe",
} | GENERATOR_ACTIONS | UTILITY_ACTIONS


def run_from_config(
    config_path: Path,
    target: Path | None = None,
    dry_run: bool = False,
    force_rerun: bool = False,
) -> None:
    """Run profiles from config.

    Reads `profiles` list from config and executes each in sequence.
    When CLI `target` is provided, creates a single ad-hoc profile for that target.
    """
    raw = load_yaml_config(config_path) if config_path.exists() else {}

    # CLI target → 单个临时 profile，跳过 profiles 列表
    if target is not None:
        _run_profile_generator(config_path, {"action": DEFAULT_ACTION, "skills": [str(target)]}, raw, dry_run, force_rerun=force_rerun)
        return

    profiles = raw.get("profiles", [])
    if not profiles:
        raise click.ClickException("No profiles configured. Add a `profiles` list to config.")

    # Pass 1: expand per_scanner profiles
    expanded_profiles: list[dict[str, Any]] = []
    for i, profile in enumerate(profiles):
        if profile.get("per_scanner"):
            sub_profiles = _expand_per_scanner(profile, raw)
            if not sub_profiles:
                continue
            action = profile.get("action", DEFAULT_ACTION)
            click.echo(
                f"--- Profile {i + 1}/{len(profiles)}: {action} "
                f"(per_scanner: expanded to {len(sub_profiles)} sub-profiles) ---"
            )
            expanded_profiles.extend(sub_profiles)
        else:
            expanded_profiles.append(profile)

    # Pass 2: dispatch each profile
    for i, profile in enumerate(expanded_profiles):
        action = profile.get("action", DEFAULT_ACTION)
        if action not in SUPPORTED_ACTIONS:
            raise click.ClickException(
                f"Unsupported action: {action}. Supported: {', '.join(sorted(SUPPORTED_ACTIONS))}"
            )

        if action in GENERATOR_ACTIONS:
            click.echo(f"--- Profile {i + 1}/{len(expanded_profiles)}: {action} ---")
            _run_profile_generator(config_path, profile, raw, dry_run, force_rerun=force_rerun)
        elif action == "collect-safe":
            _run_profile_collect_safe(config_path, profile, dry_run)
        elif action in UTILITY_ACTIONS:
            _run_profile_utility(config_path, action, raw)


def _load_full_config(
    config_path: Path,
) -> tuple[UnifiedScannerConfig, RunConfig, SafeCollectionConfig, dict[str, Any]]:
    if config_path.exists():
        return load_unified_config_from_yaml(config_path)

    scanner_config = UnifiedScannerConfig.from_env()
    return scanner_config, RunConfig(), SafeCollectionConfig(), {}


def _parse_config_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on")
    return bool(value)


def _apply_llm_judgement_overrides(
    scanner_config: UnifiedScannerConfig,
    profile: dict[str, Any] | None,
) -> None:
    """Apply per-profile LLM judgement overrides to scanner config."""
    if not profile:
        return
    section = profile.get("llm_judgement")
    if not isinstance(section, dict):
        return

    llm_config = scanner_config.llm_judgement
    if "enabled" in section:
        llm_config.enabled = _parse_config_bool(section["enabled"])
    if "provider" in section:
        llm_config.provider = str(section["provider"])
    if "model" in section:
        llm_config.model = str(section["model"])
    if "api_key_env" in section:
        llm_config.api_key = os.environ.get(str(section["api_key_env"]))
    if "base_url_env" in section:
        llm_config.base_url = os.environ.get(str(section["base_url_env"]))
    if "timeout" in section:
        llm_config.timeout = int(section["timeout"])
    if "save_audit" in section:
        llm_config.save_audit = _parse_config_bool(section["save_audit"])


def _run_profile_generator(config_path: Path, profile: dict[str, Any], raw: dict[str, Any], dry_run: bool, *, force_rerun: bool = False) -> None:
    """执行一个 generator 类型的 profile。"""
    if not config_path.exists():
        raise click.ClickException(f"Config file does not exist: {config_path}")

    action = profile.get("action", DEFAULT_ACTION)
    pipeline_defaults = get_adversarial_defaults(raw)

    # direct_scan uses scanners.enabled (public config), same as the old "scan" action
    if action == "direct_scan" and "enabled_scanners" not in profile:
        scanners_enabled = _resolve_enabled_scanners(None, raw, profile)
        if scanners_enabled:
            profile["enabled_scanners"] = scanners_enabled

    adv_config = AdversarialConfig.load(config_path)
    batch_config = BatchConfig.from_profile(profile, pipeline_defaults, config_path)
    batch_config.batch["generator"] = action

    # 加载完整 scanner config（含 timeout/priority/api_key 等），传递到 pipeline
    scanner_config, _, _, _ = _load_full_config(config_path)
    _apply_llm_judgement_overrides(scanner_config, profile)

    orchestrator = BatchOrchestrator(batch_config=batch_config, adv_config=adv_config, scanner_config=scanner_config)

    if force_rerun and orchestrator.state_path.exists():
        orchestrator.state_path.unlink()
        click.echo("Force rerun: 已删除 state.json")

    if dry_run:
        orchestrator.dry_run()
        return

    click.echo("开始批量对抗测试...")
    orchestrator.run(verbose=True)
    click.echo("\n批量测试完成")


def _run_profile_collect_safe(config_path: Path, profile: dict[str, Any], dry_run: bool) -> None:
    """执行一个 collect-safe 类型的 profile。"""
    from dataclasses import replace as dc_replace

    scanner_config, _, safe_config, raw = _load_full_config(config_path)
    _apply_llm_judgement_overrides(scanner_config, profile)
    target_str = profile.get("target")
    resolved_target = Path(target_str) if target_str else None
    enabled_scanners = _resolve_enabled_scanners(None, raw, profile)

    # 从 profile 读取 output_dir，覆盖 safe_config 的路径
    output_dir_str = profile.get("output_dir")
    if output_dir_str:
        output_dir = Path(output_dir_str)
        safe_config = dc_replace(
            safe_config,
            output_dir=output_dir,
            safe_dir=output_dir / "safe_skills",
            index_path=output_dir / "safe_skills.json",
            retry_path=output_dir / "safe_skills_retry.json",
            harmful_path=output_dir / "harmful_skills.json",
        )

    recursive = bool(profile.get("recursive", False))
    _run_collect_safe(scanner_config, safe_config, enabled_scanners, resolved_target, dry_run=dry_run, recursive=recursive)


def _run_profile_utility(config_path: Path, action: str, raw: dict[str, Any]) -> None:
    """执行一个 utility 类型的 profile。"""
    scanner_config, _, _, _ = _load_full_config(config_path)

    if action == "status":
        _run_status(scanner_config)
    elif action == "list-scanners":
        _run_list_scanners()
    elif action == "list-generators":
        _run_list_generators(raw)
    elif action == "validate-config":
        _run_validate_config(config_path)


def _resolve_enabled_scanners(
    scanners_arg: str | None,
    raw_config: dict[str, Any],
    profile: dict[str, Any] | None = None,
) -> list[str] | None:
    if scanners_arg:
        names = [item.strip() for item in scanners_arg.split(",") if item.strip()]
        return names or None

    if profile:
        enabled = profile.get("enabled_scanners")
        if isinstance(enabled, list):
            names = [str(item).strip() for item in enabled if str(item).strip()]
            if names:
                return names

    # 公开配置只认 scanners.enabled
    scanners_section = raw_config.get("scanners", {})
    enabled = scanners_section.get("enabled")
    if isinstance(enabled, list):
        names = [str(item).strip() for item in enabled if str(item).strip()]
        return names or None

    return None


def _expand_per_scanner(
    profile: dict[str, Any],
    raw_config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Expand a profile with per_scanner: true into N sub-profiles.

    Each sub-profile runs with exactly one enabled scanner and an
    output_dir adjusted to include the scanner name.

    Args:
        profile: The original profile dict (must have per_scanner=True).
        raw_config: The full raw config dict (for resolving enabled scanners).

    Returns:
        List of shallow-copied profile dicts, one per scanner.
    """
    enabled_scanners = _resolve_enabled_scanners(None, raw_config, profile)

    if enabled_scanners:
        candidate_scanners = enabled_scanners
    else:
        candidate_scanners = sorted(ALL_SCANNER_NAMES)

    valid_scanners = [s for s in candidate_scanners if s in ALL_SCANNER_NAMES]

    if not valid_scanners:
        click.echo("Warning: per_scanner expansion found no valid scanners, skipping profile.")
        return []

    original_output_dir = profile.get("output_dir", ".")
    expanded = []

    for scanner_name in valid_scanners:
        sub_profile = dict(profile)  # shallow copy
        sub_profile["enabled_scanners"] = [scanner_name]
        sub_profile["output_dir"] = str(Path(original_output_dir) / scanner_name)
        sub_profile.pop("per_scanner", None)  # prevent re-expansion
        expanded.append(sub_profile)

    return expanded


def _load_retry_skill_dirs(retry_path: Path) -> list[Path]:
    """从 retry JSON 文件读取待重试的 skill 路径列表。"""
    import json
    with open(retry_path, encoding="utf-8") as f:
        data = json.load(f)
    paths = [Path(entry["source_path"]) for entry in data.get("skills", [])]
    return [p for p in paths if p.exists()]


def _run_collect_safe(
    scanner_config: UnifiedScannerConfig,
    safe_config: SafeCollectionConfig,
    enabled_scanners: list[str] | None,
    target: Path | None,
    dry_run: bool,
    recursive: bool = False,
    skip_known: bool = True,
    pre_load_registry: bool = True,
    benign_registry_path: Path | None = None,
    malicious_registry_path: Path | None = None,
    failed_registry_path: Path | None = None,
) -> None:
    pattern = "SKILL.md"
    excluded_scanners = _resolve_collect_safe_excluded_scanners(enabled_scanners)

    # 无 target 时，从 retry 文件读取待重试列表
    if target is None:
        if not safe_config.retry_path.exists():
            click.echo(f"未指定 target，且 retry 文件不存在: {safe_config.retry_path}")
            return
        skill_dirs = _load_retry_skill_dirs(safe_config.retry_path)
        click.echo(f"从 retry 文件加载 {len(skill_dirs)} 个技能: {safe_config.retry_path}")
    else:
        skill_dirs = _find_skill_dirs(str(target), pattern, recursive)

    if not skill_dirs:
        click.echo("未发现任何技能目录")
        return

    click.echo(f"发现 {len(skill_dirs)} 个技能，开始扫描...")
    collector = SafeSkillCollector(
        safe_dir=safe_config.safe_dir,
        index_path=safe_config.index_path,
        retry_path=safe_config.retry_path,
        harmful_path=safe_config.harmful_path,
    )

    # 设置注册表路径（finalize 时自动追加）
    registry_paths_set = False
    if pre_load_registry:
        try:
            from .registry import SkillRegistry
            registry = SkillRegistry(
                benign_path=benign_registry_path or safe_config.__dict__.get("benign_registry_path"),
                malicious_path=malicious_registry_path or safe_config.__dict__.get("malicious_registry_path"),
                failed_path=failed_registry_path or safe_config.__dict__.get("failed_registry_path"),
            )
            preloaded = collector.load_from_registry(registry)
            click.echo(f"从注册表预加载: {preloaded['safe']} 安全 / {preloaded['harmful']} 有害 / {preloaded['failed']} 失败")

            # 设置注册表路径用于 finalize 时追加
            if hasattr(safe_config, "benign_registry_path") and safe_config.benign_registry_path:
                collector.set_registry_paths(
                    benign_path=safe_config.benign_registry_path,
                    malicious_path=safe_config.malicious_registry_path,
                    failed_path=safe_config.failed_registry_path,
                )
                registry_paths_set = True
        except Exception as e:
            click.echo(f"注册表预加载失败: {e}，继续扫描...")

    if registry_paths_set and not dry_run:
        click.echo(f"扫描后自动更新注册表: benign={safe_config.benign_registry_path}")

    scan_errors = 0
    skipped_known = 0
    buckets: dict[str, int] = {"safe": 0, "harmful": 0, "retry": 0}

    # 初始化已预加载的桶计数
    buckets["safe"] = len(collector._safe)
    buckets["harmful"] = len(collector._harmful)
    buckets["retry"] = len(collector._retry)

    pending_skills: list[tuple[int, Path]] = []
    for index, skill_dir in enumerate(skill_dirs, 1):
        # 跳过已知 skill
        if skip_known:
            known = collector.is_already_known(skill_dir)
            if known is not None:
                click.echo(f"  [{index}/{len(skill_dirs)}] {skill_dir.name}... 跳过 (已在 {known} 注册表)")
                skipped_known += 1
                continue
        pending_skills.append((index, skill_dir))

    def _scan_one(skill_dir: Path) -> tuple[Path, UnifiedScanResult]:
        if getattr(getattr(scanner_config, "sandbox", None), "enabled", False):
            raise RuntimeError(
                "Docker sandboxed scanning is not included in this distribution; "
                "disable the sandbox: section in your config."
            )
        scanner = PhasedSkillScanner(
            config=scanner_config,
            exclude_scanners=excluded_scanners,
        )
        result_dict = scanner.scan_phased(skill_dir)
        return skill_dir, _to_unified_scan_result(result_dict, skill_dir)

    max_skill_workers = max(1, scanner_config.max_skill_workers)
    all_scan_results: list[UnifiedScanResult] = []  # 收集扫描结果用于总结报告
    with ThreadPoolExecutor(max_workers=max_skill_workers) as executor:
        future_to_skill = {
            executor.submit(_scan_one, skill_dir): (index, skill_dir)
            for index, skill_dir in pending_skills
        }

        for future in as_completed(future_to_skill):
            index, skill_dir = future_to_skill[future]
            click.echo(f"  [{index}/{len(skill_dirs)}] {skill_dir.name}...", nl=False)
            try:
                _, scan_result = future.result()
                all_scan_results.append(scan_result)
                if dry_run:
                    from .safe_collector import classify
                    click.echo(f" [{classify(scan_result)}]")
                else:
                    bucket = collector.ingest(skill_dir, scan_result)
                    buckets[bucket] += 1
                    click.echo(f" {bucket}")
            except Exception as exc:  # pragma: no cover - defensive reporting
                scan_errors += 1
                click.echo(f" error: {exc}")

    if dry_run:
        click.echo("\nDry run 完成")
        return

    collector.finalize()
    click.echo(
        f"\n扫描完成: {buckets['safe']} 安全 / {buckets['harmful']} 有害 / "
        f"{buckets['retry']} 待重试 / {scan_errors} 异常 / {skipped_known} 跳过"
    )
    click.echo(f"  safe:    {safe_config.index_path}")
    click.echo(f"  harmful: {safe_config.harmful_path}")
    if buckets["retry"]:
        click.echo(f"  retry:   {safe_config.retry_path}")

    # 生成总结报告（Markdown + Rich Console）
    if all_scan_results:
        try:
            from .summary_report import SummaryReportGenerator
            output_dir = safe_config.index_path.parent
            summary_gen = SummaryReportGenerator(title="Collect-Safe Batch Summary")
            summary_gen.render(
                all_scan_results,
                output_path=output_dir / "summary_report.md",
                show_console=True,
            )
        except Exception as e:
            click.echo(f"  总结报告生成失败: {e}")


def _find_skill_dirs(directory: str, pattern: str, recursive: bool) -> list[Path]:
    dir_path = Path(directory)
    if (dir_path / pattern).exists():
        return [dir_path]
    if recursive:
        return [skill_file.parent for skill_file in dir_path.rglob(pattern)]
    return [
        child for child in sorted(dir_path.iterdir())
        if child.is_dir() and (child / pattern).exists()
    ]


def _resolve_collect_safe_excluded_scanners(enabled_scanners: list[str] | None) -> list[str] | None:
    """将 collect-safe 的 enabled_scanners 转为 phased scanner 的 exclude_scanners。"""
    if not enabled_scanners:
        return None

    phased_scanners = {
        scanner_name
        for phase in PhasedSkillScanner.PHASES.values()
        for scanner_name in phase.get("scanners", [])
    }
    enabled = {name for name in enabled_scanners if name in phased_scanners}
    return sorted(phased_scanners - enabled)


def _run_status(scanner_config: UnifiedScannerConfig) -> None:
    scanner = UnifiedSkillScanner(enabled_scanners=[], config=scanner_config)
    report = get_availability_report(scanner._availability)

    click.echo("扫描器状态:")
    click.echo("=" * 60)
    for name, info in report.items():
        if info["available"]:
            click.echo(f"  [OK] {name}")
        else:
            click.echo(f"  [--] {name}")
            if info.get("reason"):
                click.echo(f"       原因: {info['reason']}")

    click.echo("\nAPI Keys:")
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        click.echo(f"  {key}: {'已设置' if os.environ.get(key) else '未设置'}")


def _run_list_scanners() -> None:
    registry = create_default_registry()
    click.echo("已注册扫描器:")
    for name in sorted(registry._adapters.keys()):
        adapter = registry._adapters[name]
        available = adapter.is_available()
        status = click.style("可用", fg="green") if available else click.style("不可用", fg="red")
        click.echo(f"  {name}: {status}")


def _run_list_generators(raw: dict[str, Any]) -> None:
    generators = raw.get("generators", {})
    names = sorted(generators) if isinstance(generators, dict) else []
    if not names:
        click.echo("无已配置生成器")
        return

    click.echo("已配置生成器:")
    for name in names:
        click.echo(f"  {name}")


def _run_validate_config(config_path: Path) -> None:
    if not config_path.exists():
        click.echo(f"配置文件不存在: {config_path}", err=True)
        sys.exit(1)

    try:
        raw = load_yaml_config(config_path)
    except Exception as exc:
        click.echo(f"配置加载失败: {exc}", err=True)
        sys.exit(1)

    errors: list[str] = []
    valid_names = {
        "scan_skill_auditor",
        "scan_cisco",
        "scan_hss",
        "scan_skill_vetter",
        "scan_skillfortify",
        "scan_skill_slowmist",
        "scan_execscan",
    }

    scanners = raw.get("scanners", {})
    for name in scanners:
        if name == "enabled":
            continue
        if name not in valid_names:
            errors.append(f"未知 scanner: {name}")

    generators = raw.get("generators", {})
    for gen_name, gen_cfg in generators.items():
        if "class" not in gen_cfg:
            errors.append(f"generator '{gen_name}' 缺少 class 字段")

    scanners_section = raw.get("scanners", {})
    enabled_list = scanners_section.get("enabled", [])
    for scanner_name in enabled_list:
        if scanner_name not in valid_names:
            errors.append(f"scanners.enabled 中未知 scanner: {scanner_name}")
        elif not isinstance(scanners_section.get(scanner_name), dict) or "timeout" not in scanners_section.get(scanner_name, {}):
            errors.append(f"enabled scanner 缺少 timeout 配置: {scanner_name}")

    if errors:
        click.echo("配置校验失败:")
        for error in errors:
            click.echo(f"  - {error}")
        sys.exit(1)

    click.echo(f"配置校验通过: {len(scanners)} scanners, {len(generators)} generators")
    click.echo(f"文件: {config_path}")
    includes = raw.get("includes", [])
    if includes:
        click.echo(f"Include: {', '.join(includes)}")


def _output_result(result: dict | Any, fmt: str, output: str | None, verbose: bool = False) -> None:
    if isinstance(result, UnifiedScanResult):
        result_dict = result.to_dict()
    elif isinstance(result, dict):
        result_dict = result
    else:
        result_dict = {"raw": str(result)}

    if fmt == "json":
        text = json.dumps(result_dict, indent=2, ensure_ascii=False, default=str)
    elif fmt == "sarif":
        text = _convert_to_sarif(result_dict)
    else:
        text = _format_console(result_dict, verbose)

    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(text, encoding="utf-8")
        click.echo(f"结果已保存到: {output}")
    else:
        click.echo(text)


def _convert_to_sarif(result: dict[str, Any]) -> str:
    sarif = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [{
            "tool": {"driver": {"name": result.get("scanner_name", "unified_skill_scanner"), "version": "1.0.0"}},
            "results": [],
        }],
    }
    for finding in result.get("findings", []):
        sarif["runs"][0]["results"].append({
            "ruleId": finding.get("id", "unknown"),
            "level": {"CRITICAL": "error", "HIGH": "error", "MEDIUM": "warning"}.get(
                finding.get("severity"), "note"
            ),
            "message": {"text": finding.get("description", finding.get("title", ""))},
            "locations": [{"physicalLocation": {
                "artifactLocation": {"uri": finding.get("file_path", "")},
                "region": {"startLine": finding.get("line_number", 1)},
            }}],
        })
    return json.dumps(sarif, indent=2)


def _format_console(result: dict[str, Any], verbose: bool = False) -> str:
    del verbose
    lines = [
        "=" * 60,
        f"扫描结果: {result.get('skill_path', 'unknown')}",
        "=" * 60,
    ]
    summary = result.get("summary", {})
    is_safe = summary.get("is_safe", True)
    total = summary.get("total_findings", 0)

    if is_safe:
        lines.append(click.style("状态: 安全", fg="green", bold=True))
    else:
        lines.append(click.style(f"状态: 发现 {total} 个安全问题", fg="red", bold=True))

    lines.append(f"扫描时间: {summary.get('scan_duration_ms', 0)} ms")
    lines.append(f"使用的扫描器: {', '.join(summary.get('scanners_used', []))}")
    if summary.get("scanners_failed"):
        lines.append(click.style(f"失败的扫描器: {', '.join(summary.get('scanners_failed', []))}", fg="red"))

    lines.append("")
    for scanner_summary in summary.get("scanner_summaries", []):
        name = scanner_summary.get("scanner_name", "?")
        status = scanner_summary.get("status", "unknown")
        duration_ms = scanner_summary.get("duration_ms")
        count = scanner_summary.get("total_findings", 0)
        severity = scanner_summary.get("findings_by_severity", {})

        if duration_ms is not None:
            timing_str = f"{duration_ms}ms"
        elif status == "skipped":
            timing_str = "跳过"
        else:
            timing_str = "N/A"

        if status == "failed":
            lines.append(f"  {name}: {click.style('失败', fg='red')} ({timing_str})")
            continue
        if status == "skipped":
            lines.append(f"  {name}: {click.style('跳过', fg='yellow')} ({timing_str})")
            continue

        if count == 0:
            lines.append(f"  {name}: 无发现 ({timing_str})")
            continue

        parts = []
        for key in ("critical", "high", "medium", "low", "info"):
            if severity.get(key, 0) > 0:
                parts.append(f"{severity[key]} {key.upper()}")
        lines.append(f"  {name}: {count} 发现 ({', '.join(parts)}) [{timing_str}]")

    return "\n".join(lines)


def _to_unified_scan_result(result_dict: dict[str, Any], skill_dir: Path) -> UnifiedScanResult:
    findings: list[UnifiedFinding] = []
    for finding in result_dict.get("findings", []):
        if not isinstance(finding, dict):
            continue

        try:
            severity = Severity(finding.get("severity", "INFO"))
        except ValueError:
            severity = Severity.INFO

        findings.append(
            UnifiedFinding(
                id=finding.get("id", ""),
                source_scanner=finding.get("source_scanner", "unified"),
                severity=severity,
                category=finding.get("category", "other"),
                title=finding.get("title", ""),
                description=finding.get("description", ""),
                file_path=finding.get("file_path"),
                line_number=finding.get("line_number"),
                snippet=finding.get("snippet"),
                remediation=finding.get("remediation"),
                metadata=finding.get("metadata", {}),
            )
        )

    summary_data = result_dict.get("summary", {})
    if not isinstance(summary_data, dict):
        summary_data = {}
    by_severity = summary_data.get("findings_by_severity", {})
    scanner_summaries_data = summary_data.get("scanner_summaries", [])
    scanner_summaries: list[ScannerSummary] = []
    for item in scanner_summaries_data:
        if not isinstance(item, dict):
            continue
        per_severity = item.get("findings_by_severity", {})
        scanner_summaries.append(
            ScannerSummary(
                scanner_name=item.get("scanner_name", ""),
                display_name=item.get("display_name", ""),
                total_findings=item.get("total_findings", 0),
                critical=per_severity.get("critical", 0),
                high=per_severity.get("high", 0),
                medium=per_severity.get("medium", 0),
                low=per_severity.get("low", 0),
                info=per_severity.get("info", 0),
                is_safe=item.get("is_safe"),
                status=item.get("status", "unknown"),
            )
        )

    scan_summary = ScanSummary(
        total_findings=summary_data.get("total_findings", len(findings)),
        critical=by_severity.get("critical", 0),
        high=by_severity.get("high", 0),
        medium=by_severity.get("medium", 0),
        low=by_severity.get("low", 0),
        info=by_severity.get("info", 0),
        is_safe=summary_data.get("is_safe", False),
        scan_duration_ms=summary_data.get("scan_duration_ms", 0),
        scanners_used=summary_data.get("scanners_used", []),
        scanners_failed=summary_data.get("scanners_failed", []),
        scanner_summaries=scanner_summaries,
    )

    return UnifiedScanResult(
        skill_path=str(skill_dir),
        findings=findings,
        summary=scan_summary,
        scanner_results=result_dict.get("scanner_results", {}),
    )


