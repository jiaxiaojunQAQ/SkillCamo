# Copyright 2026
#
# Thread-safe API key pool for rotating keys across parallel requests.

"""
Thread-safe API key pool for distributing requests across multiple API keys.

Usage:
    # From environment variables (OPENAI_API_KEY_1, OPENAI_API_KEY_2, ...)
    pool = ApiKeyPool.from_env_pattern("openai", "OPENAI_API_KEY")

    # Each call returns the next key in rotation
    key = pool.get_next_key()
"""

import logging
import os
import threading
from typing import Optional

logger = logging.getLogger(__name__)


class ApiKeyPool:
    """Thread-safe rotating pool of API keys for a single provider."""

    def __init__(self, provider: str, keys: list[str]):
        if not keys:
            raise ValueError(f"No API keys provided for provider '{provider}'")
        self._provider = provider
        self._keys = keys
        self._index = 0
        self._lock = threading.Lock()
        logger.info(f"ApiKeyPool for {provider}: {len(keys)} key(s) loaded")

    @classmethod
    def from_env_pattern(cls, provider: str, env_var: str) -> "ApiKeyPool":
        """Load keys from numbered environment variables, with single-var fallback.

        Discovers {ENV_VAR}_1, {ENV_VAR}_2, ... in order.
        If no numbered variants exist, falls back to {ENV_VAR} alone.

        Args:
            provider: Provider name (e.g. "openai", "anthropic").
            env_var: Base environment variable name (e.g. "OPENAI_API_KEY").

        Returns:
            ApiKeyPool with discovered keys.

        Raises:
            ValueError: If no keys are found at all.
        """
        keys: list[str] = []

        # Try numbered variants: {ENV}_1, {ENV}_2, ...
        i = 1
        while True:
            key = os.environ.get(f"{env_var}_{i}")
            if key is None:
                break
            keys.append(key)
            i += 1

        # Fallback: single env var
        if not keys:
            single = os.environ.get(env_var)
            if single:
                keys.append(single)

        if not keys:
            raise ValueError(
                f"No API keys found for {provider} "
                f"(tried {env_var}_1..{env_var}_{i - 1} and {env_var})"
            )

        return cls(provider, keys)

    @classmethod
    def from_explicit_list(cls, provider: str, keys: list[str]) -> "ApiKeyPool":
        """Create pool from an explicit list of keys."""
        return cls(provider, keys)

    def get_next_key(self) -> str:
        """Atomically return the next key in round-robin rotation."""
        with self._lock:
            key = self._keys[self._index % len(self._keys)]
            self._index += 1
            return key

    @property
    def key_count(self) -> int:
        """Number of keys in the pool."""
        return len(self._keys)

    @property
    def provider(self) -> str:
        """Provider name this pool is for."""
        return self._provider

    def __repr__(self) -> str:
        return f"ApiKeyPool(provider={self._provider!r}, keys={self.key_count})"
