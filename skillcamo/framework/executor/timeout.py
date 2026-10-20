"""
超时控制器 - 提供分层超时控制
"""

import queue
import threading
from typing import Any, Callable


class TimeoutController:
    """分层超时控制"""

    def __init__(
        self,
        global_timeout: int,      # 全局扫描超时
        scanner_timeout: int,     # 单个扫描器超时
        network_timeout: int,     # 网络请求超时
    ):
        self.global_timeout = global_timeout
        self.scanner_timeout = scanner_timeout
        self.network_timeout = network_timeout

    def run_with_timeout(
        self,
        func: Callable,
        timeout: int | None = None,
        default: Any = None
    ) -> Any:
        """
        带超时的函数执行

        Args:
            func: 要执行的函数
            timeout: 超时时间（秒），None 表示使用 scanner_timeout
            default: 超时时返回的默认值

        Returns:
            函数执行结果，或超时时的默认值
        """
        timeout = timeout or self.scanner_timeout
        result_queue: queue.Queue = queue.Queue()

        def worker():
            try:
                result_queue.put(("success", func()))
            except Exception as e:
                result_queue.put(("error", e))

        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            # 超时，线程仍在运行
            return default

        try:
            status, result = result_queue.get_nowait()
            if status == "error":
                raise result
            return result
        except queue.Empty:
            return default
