"""
并行执行器 - 并行运行多个扫描器
"""

import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from pathlib import Path

logger = logging.getLogger(__name__)

# 支持作为包使用或直接运行
try:
    from ..adapters import BaseAdapter
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from adapters import BaseAdapter


class ParallelExecutor:
    """
    并行执行多个扫描器

    特性:
    - 超时控制
    - 错误隔离
    - 部分成功返回
    """

    def __init__(
        self,
        max_workers: int,
        scanner_timeout: int,
        global_timeout: int,
    ):
        self.max_workers = max_workers
        self.scanner_timeout = scanner_timeout
        self.global_timeout = global_timeout

    def execute_scans(
        self,
        adapters: list[BaseAdapter],
        skill_path: str,
        scan_config: dict | None = None
    ) -> dict[str, dict]:
        """
        并行执行扫描，返回所有结果（成功和失败的）

        Args:
            adapters: 适配器列表
            skill_path: 技能路径
            scan_config: 扫描配置

        Returns:
            扫描器名称到结果的字典
        """
        scan_config = scan_config or {}
        results = {}
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有扫描任务
            future_to_adapter = {}
            for adapter in adapters:
                future = executor.submit(
                    self._run_single_scan,
                    adapter,
                    skill_path,
                    scan_config
                )
                future_to_adapter[future] = adapter

            # 收集结果（带全局超时）
            remaining_time = self.global_timeout - (time.time() - start_time)
            if remaining_time <= 0:
                remaining_time = 1

            try:
                for future in as_completed(future_to_adapter, timeout=remaining_time):
                    adapter = future_to_adapter[future]
                    try:
                        result = future.result(timeout=self.scanner_timeout)
                        results[adapter.scanner_name] = result
                    except TimeoutError:
                        results[adapter.scanner_name] = {
                            "findings": [],
                            "error": "Scanner timeout",
                            "metadata": {"scanner": adapter.scanner_name}
                        }
                    except Exception as e:
                        results[adapter.scanner_name] = {
                            "findings": [],
                            "error": str(e),
                            "metadata": {"scanner": adapter.scanner_name}
                        }
            except TimeoutError:
                unfinished = [
                    adapter.scanner_name
                    for f, adapter in future_to_adapter.items()
                    if adapter.scanner_name not in results
                ]
                logger.error(
                    "Parallel scan timed out (%ds), unfinished scanners: %s",
                    remaining_time,
                    ", ".join(sorted(unfinished)),
                )

            # 处理剩余 futures（超时后或正常完成后）
            for future in future_to_adapter:
                adapter = future_to_adapter[future]
                if adapter.scanner_name in results:
                    future.cancel()
                    continue
                try:
                    result = future.result(timeout=5)
                    results[adapter.scanner_name] = result
                except TimeoutError:
                    results[adapter.scanner_name] = {
                        "findings": [],
                        "error": f"Scanner timed out (global timeout {remaining_time}s exceeded)",
                        "error_type": "GlobalTimeoutError",
                        "metadata": {"scanner": adapter.scanner_name}
                    }
                except Exception as e:
                    results[adapter.scanner_name] = {
                        "findings": [],
                        "error": str(e),
                        "metadata": {"scanner": adapter.scanner_name}
                    }
                finally:
                    future.cancel()

        # 记录总耗时
        duration_ms = int((time.time() - start_time) * 1000)
        results["_duration_ms"] = duration_ms
        results["_start_time"] = start_time

        return results

    def _run_single_scan(
        self,
        adapter: BaseAdapter,
        skill_path: str,
        config: dict
    ) -> dict:
        """执行单个扫描（可被子类重写以添加重试逻辑）"""
        return adapter.scan(skill_path, **config)
