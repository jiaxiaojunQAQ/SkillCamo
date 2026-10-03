"""扫描执行器。"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError, wait, FIRST_COMPLETED
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

try:
    from .models import Severity
    from .scanner_status import extract_findings_from_scanner
except ImportError:
    from models import Severity  # type: ignore[import-not-found,no-redef]
    from scanner_status import extract_findings_from_scanner  # type: ignore[import-not-found,no-redef]


class ScanRunner:
    """执行可用 scanner，并负责进度、超时、重试和错误隔离。"""

    def __init__(
        self,
        *,
        enabled_scanners: list[str],
        is_available: Callable[[str], bool],
        normalize_name: Callable[[str], str],
        get_scan_method: Callable[[str], Callable[[Path], dict]],
        get_timeout: Callable[[str], int],
        max_workers: int,
        global_timeout: int,
        max_retries: int = 3,
        skill_name: str = "",
        progress_callback: Callable[[int, int, str], None] | None = None,
    ):
        self.enabled_scanners = enabled_scanners
        self.is_available = is_available
        self.normalize_name = normalize_name
        self.get_scan_method = get_scan_method
        self.get_timeout = get_timeout
        self.max_workers = max_workers
        self.global_timeout = global_timeout
        self.max_retries = max_retries
        self.skill_name = skill_name
        self.progress_callback = progress_callback

    def run_parallel(self, skill_path: Path) -> dict[str, Any]:
        """并行执行扫描，支持超时后自动重试。"""
        results: dict[str, Any] = {}
        start_time = time.time()
        retry_counts: dict[str, int] = {}

        # 初始化任务列表
        tasks: dict[str, Callable[[Path], dict]] = {}
        for scanner_name in self.enabled_scanners:
            if self.is_available(scanner_name):
                normalized_name = self.normalize_name(scanner_name)
                scan_method = self.get_scan_method(normalized_name)
                tasks[scanner_name] = scan_method
            else:
                # 不可用 scanner 记录 error result（而非静默跳过）
                results[scanner_name] = {
                    "findings": [],
                    "error": "Scanner not available",
                    "error_type": "ScannerUnavailable",
                    "metadata": {"scanner": scanner_name},
                }

        if not tasks:
            results["_duration_ms"] = 0
            return results

        total_tasks = len(tasks)
        completed_count = 0

        executor = ThreadPoolExecutor(max_workers=self.max_workers)
        future_to_scanner: dict[Any, str] = {}
        future_deadlines: dict[Any, float] = {}
        pending_futures: set[Any] = set()

        def submit(scanner_name: str) -> None:
            scan_method = tasks[scanner_name]
            future = executor.submit(scan_method, skill_path)
            future_to_scanner[future] = scanner_name
            timeout = max(0.0, float(self.get_timeout(scanner_name) or self.global_timeout))
            future_deadlines[future] = time.time() + timeout
            pending_futures.add(future)

        def finish_failure(
            scanner_name: str,
            error: str,
            error_type: str,
            *,
            timed_out: bool,
        ) -> str:
            retries = retry_counts.get(scanner_name, 0)
            if retries < self.max_retries:
                retry_counts[scanner_name] = retries + 1
                logger.warning(
                    "Scanner %s failed (attempt %d/%d), retrying: %s",
                    scanner_name, retries + 1, self.max_retries, error,
                )
                submit(scanner_name)
                return f"重试({retries + 1}/{self.max_retries})"

            results[scanner_name] = {
                "findings": [],
                "error": error,
                "error_type": error_type,
                "timed_out": timed_out,
                "retries_attempted": retries,
                "metadata": {"scanner": scanner_name},
            }
            logger.error(
                "Scanner %s failed after %d retries: %s",
                scanner_name, retries, error,
            )
            return "超时(重试耗尽)" if timed_out else "失败(重试耗尽)"

        try:
            for scanner_name in tasks:
                submit(scanner_name)

            while pending_futures:
                elapsed = time.time() - start_time
                remaining_time = self.global_timeout - elapsed
                if remaining_time <= 0:
                    now = time.time()
                    for future in list(pending_futures):
                        scanner_name = future_to_scanner[future]
                        if scanner_name in results:
                            pending_futures.discard(future)
                            future.cancel()
                            continue
                        scanner_deadline_expired = (
                            future_deadlines[future] <= now
                            or abs(future_deadlines[future] - (start_time + self.global_timeout)) < 0.01
                        )
                        status = finish_failure(
                            scanner_name,
                            (
                                f"Scanner timeout ({self.get_timeout(scanner_name)}s) exceeded"
                                if scanner_deadline_expired
                                else f"Global timeout ({self.global_timeout}s) exceeded"
                            ),
                            "ScannerTimeout" if scanner_deadline_expired else "GlobalTimeout",
                            timed_out=True,
                        )
                        pending_futures.discard(future)
                        future.cancel()
                        if not status.startswith("重试"):
                            completed_count += 1
                            self._report_progress(
                                completed_count, total_tasks, scanner_name, status,
                                sorted(s for s in tasks if s not in results),
                            )
                    break

                next_deadline = min(future_deadlines[f] for f in pending_futures)
                wait_timeout = max(0.0, min(remaining_time, next_deadline - time.time()))
                done, _ = wait(
                    pending_futures,
                    timeout=wait_timeout,
                    return_when=FIRST_COMPLETED,
                )

                if not done:
                    now = time.time()
                    done = {f for f in pending_futures if future_deadlines[f] <= now}
                    if not done:
                        continue

                for future in done:
                    if future not in pending_futures:
                        continue
                    pending_futures.discard(future)
                    scanner_name = future_to_scanner[future]
                    if scanner_name in results:
                        future.cancel()
                        continue

                    status = "完成"
                    if future.done():
                        try:
                            results[scanner_name] = future.result()
                        except TimeoutError:
                            status = finish_failure(
                                scanner_name,
                                "Scanner timeout",
                                "ScannerTimeout",
                                timed_out=True,
                            )
                        except Exception as e:
                            status = finish_failure(
                                scanner_name,
                                str(e),
                                type(e).__name__,
                                timed_out=False,
                            )
                    else:
                        future.cancel()
                        status = finish_failure(
                            scanner_name,
                            f"Scanner timeout ({self.get_timeout(scanner_name)}s) exceeded",
                            "ScannerTimeout",
                            timed_out=True,
                        )

                    if status.startswith("完成") or status.startswith("超时") or status.startswith("失败"):
                        completed_count += 1
                        self._report_progress(
                            completed_count, total_tasks, scanner_name, status,
                            sorted(s for s in tasks if s not in results),
                        )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        results["_duration_ms"] = int((time.time() - start_time) * 1000)
        return results

    def run_fast_fail(self, skill_path: Path) -> dict[str, Any]:
        """串行执行扫描，发现 CRITICAL/HIGH 后跳过剩余 scanner，支持重试。"""
        results: dict[str, Any] = {}
        start_time = time.time()
        completed_count = 0
        retry_counts: dict[str, int] = {}

        runnable = [s for s in self.enabled_scanners if self.is_available(s)]
        pending_set = set(runnable)

        for scanner_name in self.enabled_scanners:
            if not self.is_available(scanner_name):
                # 不可用 scanner 记录 error result（与 run_parallel 保持一致）
                results[scanner_name] = {
                    "findings": [],
                    "error": "Scanner not available",
                    "error_type": "ScannerUnavailable",
                    "metadata": {"scanner": scanner_name},
                }
                continue

            normalized_name = self.normalize_name(scanner_name)
            scan_method = self.get_scan_method(normalized_name)

            # 带重试的执行
            max_attempts = self.max_retries + 1
            result = None
            for attempt in range(max_attempts):
                try:
                    result = scan_method(skill_path)
                    break
                except Exception as e:
                    if attempt < self.max_retries:
                        retry_counts[scanner_name] = retry_counts.get(scanner_name, 0) + 1
                        logger.warning(
                            "Scanner %s failed (attempt %d/%d), retrying: %s",
                            scanner_name, attempt + 1, self.max_retries, e,
                        )
                        continue
                    else:
                        result = {
                            "findings": [],
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "timed_out": isinstance(e, TimeoutError),
                            "retries_attempted": self.max_retries,
                        }
                        logger.error(
                            "Scanner %s failed after %d retries: %s",
                            scanner_name, self.max_retries, e,
                        )

            if result is None:
                continue

            results[scanner_name] = result

            findings = extract_findings_from_scanner(scanner_name, result)
            critical = sum(1 for f in findings if f.severity == Severity.CRITICAL)
            high = sum(1 for f in findings if f.severity == Severity.HIGH)

            completed_count += 1
            pending_set.discard(scanner_name)
            status = "found_critical" if (critical > 0 or high > 0) else "完成"
            self._report_progress(
                completed_count, len(runnable), scanner_name, status,
                sorted(pending_set) if pending_set else None,
            )

            if critical > 0 or high > 0:
                remaining = [
                    s for s in self.enabled_scanners
                    if s not in results and self.is_available(s)
                ]
                for skipped in remaining:
                    results[skipped] = {
                        "findings": [],
                        "skipped": True,
                        "skip_reason": f"Previous scanner found critical={critical}, high={high}",
                        "metadata": {"scanner": skipped},
                    }
                break

        results["_duration_ms"] = int((time.time() - start_time) * 1000)
        return results

    def _report_progress(
        self,
        current: int,
        total: int,
        scanner_name: str,
        status: str,
        pending_scanners: list[str] | None = None,
    ) -> None:
        if not self.progress_callback:
            return
        parts = []
        if self.skill_name:
            parts.append(f"[{self.skill_name}]")
        parts.append(f"{scanner_name}: {status}")
        if pending_scanners:
            parts.append(f"| pending: [{', '.join(pending_scanners)}]")
        message = " ".join(parts)
        self.progress_callback(current, total, message)
