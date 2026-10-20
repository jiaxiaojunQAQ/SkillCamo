"""底层 scanner 调用函数。"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Callable

try:
    from .paths import get_scanner_path
except ImportError:
    from paths import get_scanner_path  # type: ignore[import-not-found,no-redef]


def load_adapter_class(module_name: str, class_name: str):
    """按包模式优先加载适配器类，回退到脚本模式导入。"""
    try:
        module = importlib.import_module(f"unified_scanner.adapters.{module_name}")
    except ImportError:
        module = importlib.import_module(f"adapters.{module_name}")
    return getattr(module, class_name)


def scan_with_adapter(
    skill_path: Path,
    *,
    scanner_name: str,
    module_name: str,
    class_name: str,
    timeout: int,
    adapter_kwargs: dict[str, Any] | None = None,
    loader: Callable[[str, str], Any] = load_adapter_class,
) -> dict[str, Any]:
    """使用统一适配器调用路径执行扫描。"""
    adapter_cls = loader(module_name, class_name)
    adapter = adapter_cls(**(adapter_kwargs or {}))
    return adapter.scan(skill_path, timeout=timeout)


def scan_cisco(
    skill_path: Path,
    *,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """调用 Cisco AI Skill Scanner。"""
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

    def _do_scan() -> dict[str, Any]:
        scan_cisco_path = get_scanner_path("scan_cisco")
        if str(scan_cisco_path) not in sys.path:
            sys.path.insert(0, str(scan_cisco_path))

        from scan_cisco.core.analyzer_factory import build_analyzers  # type: ignore[import-not-found]
        from scan_cisco.core.scan_policy import ScanPolicy  # type: ignore[import-found]
        from scan_cisco.core.scanner import SkillScanner  # type: ignore[import-not-found]

        # 有 model 配置时启用 LLM 分析器
        if model:
            analyzers = build_analyzers(
                policy=ScanPolicy.from_preset("balanced"),
                use_llm=True,
                llm_model=model,
                llm_base_url=base_url,
                llm_api_key=api_key,
            )
        else:
            from scan_cisco.core.analyzer_factory import build_core_analyzers  # type: ignore[import-not-found]
            analyzers = build_core_analyzers(policy=ScanPolicy.default())

        scanner = SkillScanner(analyzers=analyzers)
        result = scanner.scan_skill(skill_path, lenient=True)
        return result.to_dict()

    try:
        if timeout:
            ex = ThreadPoolExecutor(max_workers=1)
            future = ex.submit(_do_scan)
            try:
                return future.result(timeout=timeout)
            except FuturesTimeoutError:
                future.cancel()
                ex.shutdown(wait=False, cancel_futures=True)
                raise TimeoutError(f"scan_cisco exceeded {timeout}s timeout")
        else:
            return _do_scan()
    except TimeoutError:
        raise  # 让 run_parallel 的重试逻辑处理
    except Exception as e:
        return {
            "error": str(e),
            "error_type": type(e).__name__,
            "scanner": "scan_cisco",
        }
