from __future__ import annotations

from typing import Any


def build_openai_chat_completion_kwargs(
    *,
    model: str,
    messages: list[dict[str, str]],
    **extra: Any,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        **extra,
    }
    return kwargs
