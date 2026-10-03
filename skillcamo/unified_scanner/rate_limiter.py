"""
Rate Limiter Utility

Provides thread-safe rate limiting for API requests.
Uses a token bucket algorithm for smooth rate limiting.

The process-global shared limiter (for LLM endpoint throttling) is managed
as a class-level singleton on ``TokenBucketRateLimiter`` via
``TokenBucketRateLimiter.get_shared()``.  No module-level mutable state is
used; thread-safety of the lazy-init path is guaranteed by the class-level
``_shared_lock``.
"""

import logging
import os
import random
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Standalone jitter / backoff helper
# ---------------------------------------------------------------------------

def random_delay(attempt: int, *, base: float = 2.0, cap: float = 30.0, jitter: float = 1.0) -> float:
    """Compute exponential-backoff delay with uniform jitter.

    Intended for retry loops where concurrent callers must not retry in
    lock-step (which would amplify thundering-herd on rate-limited
    endpoints).

    Args:
        attempt: Zero-based attempt counter (0 = first retry).
        base:    Exponential base (default 2 → 1 s, 2 s, 4 s, …).
        cap:     Maximum delay in seconds.
        jitter:  Upper bound of the uniform jitter added to the
                 exponential component.

    Returns:
        Delay in seconds (always > 0).
    """
    return min(cap, (base ** attempt) + random.uniform(0.0, jitter))


class TokenBucketRateLimiter:
    """
    Token Bucket Rate Limiter for controlling request rates.

    This implementation uses a token bucket algorithm which allows for
    smooth rate limiting while handling burst traffic gracefully.

    Example:
        # Allow 4 requests per minute
        limiter = TokenBucketRateLimiter(rate=4.0, period=60.0)

        # Wait until a token is available
        limiter.acquire()

        # Or check wait time without blocking
        wait_time = limiter.get_wait_time()
        if wait_time > 0:
            time.sleep(wait_time)

    The class also exposes a process-global *shared* limiter for
    OpenAI-compatible endpoints (e.g. Xiaomi MiMo) via the
    ``get_shared()`` classmethod.  This replaces the previous
    module-level ``_shared_limiter`` / ``_shared_limiter_lock`` /
    ``_shared_limiter_resolved`` globals.
    """

    # ---- class-level singleton state (replaces former module globals) ----
    _shared: Optional["TokenBucketRateLimiter"] = None
    _shared_lock: threading.Lock = threading.Lock()
    _shared_resolved: bool = False

    def __init__(
        self,
        rate: float = 4.0,
        period: float = 60.0,
        burst: int = 1,
    ):
        """
        Initialize the rate limiter.

        Args:
            rate: Number of requests allowed per period (default: 4.0)
            period: Time period in seconds (default: 60.0)
            burst: Maximum burst size (default: 1)
        """
        self.rate = rate
        self.period = period
        self.burst = burst

        # Token bucket state
        self.tokens = float(burst)
        self.last_update = time.time()

        # Thread safety (per-instance lock — no global _SRW_LOCK)
        self._lock = threading.Lock()

        # Calculate refill interval
        self._refill_interval = period / rate if rate > 0 else 0

        logger.debug(
            f"RateLimiter initialized: rate={rate}/{period}s, burst={burst}"
        )

    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update

        if elapsed > 0:
            # Calculate tokens to add
            tokens_to_add = elapsed * self.rate / self.period

            with self._lock:
                self.tokens = min(
                    self.burst,
                    self.tokens + tokens_to_add
                )
                self.last_update = now

    def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire a token, blocking until one is available.

        Args:
            timeout: Maximum time to wait in seconds. None means wait forever.

        Returns:
            True if token was acquired, False if timeout occurred.
        """
        start_time = time.time()

        while True:
            self._refill_tokens()

            with self._lock:
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    logger.debug(f"Token acquired, remaining: {self.tokens:.2f}")
                    return True

            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    logger.warning(f"Rate limiter timeout after {timeout}s")
                    return False

            # Wait a bit before retrying
            wait_time = min(0.1, self._refill_interval)
            time.sleep(wait_time)

    def get_wait_time(self) -> float:
        """
        Get the time to wait before the next token is available.

        Returns:
            Wait time in seconds (0 if token is available now).
        """
        self._refill_tokens()

        with self._lock:
            if self.tokens >= 1.0:
                return 0.0

            # Calculate time until next token
            deficit = 1.0 - self.tokens
            wait_seconds = deficit * self.period / self.rate

            return max(0.0, wait_seconds)

    def acquire_or_wait(self) -> None:
        """
        Acquire a token, waiting the required time.

        This is a convenience method that calls get_wait_time() and sleeps
        before acquiring, logging the wait time.
        """
        wait_time = self.get_wait_time()

        if wait_time > 0:
            logger.info(f"Rate limit: waiting {wait_time:.1f}s before request")
            time.sleep(wait_time)

        self.acquire()

    def reset(self) -> None:
        """Reset the rate limiter to initial state."""
        with self._lock:
            self.tokens = float(self.burst)
            self.last_update = time.time()
        logger.debug("Rate limiter reset")

    def get_status(self) -> dict:
        """Get current rate limiter status."""
        self._refill_tokens()

        # NOTE: get_wait_time() internally re-acquires self._lock (via
        # _refill_tokens), so it must be called OUTSIDE the lock below — calling
        # it while holding self._lock self-deadlocks (threading.Lock is not
        # reentrant). Snapshot the locked fields first, then compute wait time.
        with self._lock:
            rate = self.rate
            period = self.period
            burst = self.burst
            tokens = self.tokens

        return {
            "rate": rate,
            "period": period,
            "burst": burst,
            "tokens_available": tokens,
            "wait_time_seconds": self.get_wait_time(),
        }

    # ------------------------------------------------------------------
    # Process-global shared limiter (class-level singleton).
    #
    # Opt-in via env: every OpenAI-path call site (judgement / generator
    # advisor) calls ``TokenBucketRateLimiter.get_shared().acquire()``
    # before hitting the endpoint so the AGGREGATE request rate across all
    # worker threads stays under the provider's limit.  Returns ``None``
    # (no throttling) when ``LLM_MAX_RPM`` is unset / <= 0, so existing
    # runs behave exactly as before unless the user explicitly enables it.
    #
    #   LLM_MAX_RPM   — requests/minute ceiling (float). e.g. 120
    #   LLM_MAX_BURST — token bucket burst size (int, default 1)
    # ------------------------------------------------------------------

    @classmethod
    def get_shared(cls) -> Optional["TokenBucketRateLimiter"]:
        """Return the process-global OpenAI-path limiter, or ``None`` if disabled.

        Thread-safe lazy initialisation using a class-level lock.  The
        result is cached — subsequent calls return the same instance
        (or ``None``) without re-reading the environment.
        """
        if cls._shared_resolved:
            return cls._shared
        with cls._shared_lock:
            if cls._shared_resolved:
                return cls._shared
            rpm_raw = os.environ.get("LLM_MAX_RPM")
            if rpm_raw:
                try:
                    rpm = float(rpm_raw)
                except ValueError:
                    logger.warning("Invalid LLM_MAX_RPM=%r — rate limiting disabled", rpm_raw)
                    rpm = 0.0
                if rpm > 0:
                    try:
                        burst = max(1, int(os.environ.get("LLM_MAX_BURST", "1") or "1"))
                    except ValueError:
                        burst = 1
                    cls._shared = cls(rate=rpm, period=60.0, burst=burst)
                    logger.info(
                        "Shared LLM rate limiter ACTIVE: %.0f req/min (burst=%d)", rpm, burst
                    )
            cls._shared_resolved = True
        return cls._shared


# ---------------------------------------------------------------------------
# Backward-compatible module-level helper (thin wrapper around classmethod).
# Existing callers that do ``from rate_limiter import get_shared_limiter``
# continue to work without modification.
# ---------------------------------------------------------------------------

def get_shared_limiter() -> Optional[TokenBucketRateLimiter]:
    """Return the process-global OpenAI-path limiter, or ``None`` if disabled.

    .. deprecated::
        Prefer ``TokenBucketRateLimiter.get_shared()`` directly.
    """
    return TokenBucketRateLimiter.get_shared()
