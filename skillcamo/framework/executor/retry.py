"""
重试执行器 - 带重试机制的并行执行
"""

import sys
import time
from pathlib import Path

# 支持作为包使用或直接运行
try:
    from .parallel import ParallelExecutor
    from ..adapters import BaseAdapter
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from executor.parallel import ParallelExecutor
    from adapters import BaseAdapter


class RetryExecutor(ParallelExecutor):
    """
    带重试的并行执行器

    特性:
    - 对失败的扫描器进行重试
    - 指数退避
    - 可配置重试次数
    """

    def __init__(
        self,
        max_retries: int = 2,
        retry_backoff: float = 1.5,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff

    def _run_single_scan(
        self,
        adapter: BaseAdapter,
        skill_path: str,
        config: dict
    ) -> dict:
        """
        执行单个扫描，失败时重试

        Args:
            adapter: 扫描器适配器
            skill_path: 技能路径
            config: 扫描配置

        Returns:
            扫描结果字典
        """
        last_error = None
        wait_time = 1

        for attempt in range(self.max_retries + 1):
            try:
                return adapter.scan(skill_path, **config)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(wait_time)
                    wait_time *= self.retry_backoff

        # 所有重试都失败
        return {
            "findings": [],
            "error": f"After {self.max_retries} retries: {last_error}",
            "metadata": {
                "scanner": getattr(adapter, "scanner_name", "unknown"),
                "retries_attempted": self.max_retries
            }
        }
