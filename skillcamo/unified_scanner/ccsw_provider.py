"""ccsw provider 环境变量解析。

为基于 Claude CLI 的 scanner 提供"按 ccsw provider 注入 ANTHROPIC_* env"的能力：
通过 `ccsw query claude <provider>` 读出指定 provider 的 settings_config.env，
注入到 claude 子进程，从而无需全局 `ccsw switch`（不污染 ~/.claude/settings.json，
可并发跑不同 provider）。

scanner 的 CLI 调用带 `--bare --setting-sources ""`，claude 不读 settings.json，
只认进程环境变量，故这是让 scanner 命中非官方后端（GLM/MiMo 等）的正确方式。

安全：返回值含明文 ANTHROPIC_AUTH_TOKEN，调用方不得写入日志/审计。
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from functools import lru_cache

logger = logging.getLogger(__name__)

# ccsw query 通常 <1s；给足余量但不无限等待
_QUERY_TIMEOUT_SECONDS = 30


class CcswProviderError(RuntimeError):
    """解析 ccsw provider 配置失败。"""


@lru_cache(maxsize=32)
def resolve_ccsw_provider_env(provider_ref: str) -> dict[str, str]:
    """解析指定 ccsw provider 的 ANTHROPIC_* 环境变量。

    Args:
        provider_ref: ccsw provider 的 **id**（名称可能有歧义，建议传 id）。

    Returns:
        settings_config.env 中的全部字符串键值对（ANTHROPIC_BASE_URL /
        ANTHROPIC_AUTH_TOKEN / ANTHROPIC_MODEL / ANTHROPIC_DEFAULT_*_MODEL 等）。

    Raises:
        CcswProviderError: ccsw 不在 PATH、调用失败、输出非 JSON（如 provider
            未找到或名称有歧义）、或 env 为空。
    """
    if shutil.which("ccsw") is None:
        raise CcswProviderError(
            "未找到 ccsw 命令（请确认 ccsw 已安装并在 PATH 中）"
        )

    try:
        result = subprocess.run(
            ["ccsw", "query", "claude", provider_ref],
            capture_output=True,
            text=True,
            timeout=_QUERY_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:  # PATH 竞态：which 通过但执行时消失
        raise CcswProviderError("未找到 ccsw 命令") from exc
    except subprocess.TimeoutExpired as exc:
        raise CcswProviderError(
            f"ccsw query 超时（provider={provider_ref!r}）"
        ) from exc

    if result.returncode != 0:
        raise CcswProviderError(
            f"ccsw query 失败（provider={provider_ref!r}, "
            f"exit={result.returncode}）: {result.stderr.strip() or result.stdout.strip()}"
        )

    # ccsw query 正常时输出单行 JSON；provider 未找到/歧义时输出中文错误文本
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise CcswProviderError(
            f"ccsw query 输出非 JSON（provider={provider_ref!r}）: "
            f"{result.stdout.strip() or result.stderr.strip()}"
        ) from exc

    settings = payload.get("settings_config") or {}
    env = settings.get("env") if isinstance(settings, dict) else None
    if not isinstance(env, dict) or not env:
        raise CcswProviderError(
            f"ccsw provider {provider_ref!r} 没有可用的 settings_config.env"
        )

    # 仅保留字符串键值（claude 子进程 env 要求 str）
    resolved = {str(k): str(v) for k, v in env.items() if isinstance(v, str)}

    # 安全：只记键名，不记值（含明文 token）
    logger.info(
        "Resolved ccsw provider %r env keys: %s",
        provider_ref,
        sorted(resolved.keys()),
    )
    return resolved
