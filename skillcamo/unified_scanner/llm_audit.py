"""LLM 调用审计模块 - 记录所有 LLM 输入输出。

提供统一的 LLM 调用审计接口，用于保存：
- 请求信息：provider, model, prompt, system_prompt, parameters
- 响应信息：raw_response, parsed_response, duration_ms
- 元数据：source, timestamp, call_id, context info
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

# 全局锁用于保护 index.jsonl 的并发写入
_INDEX_LOCK = Lock()


class LLMCallAuditor:
    """LLM 调用审计器 - 记录完整的 LLM 请求和响应。

    使用方式：
        auditor = LLMCallAuditor(output_dir="output/llm_audit")
        auditor.log_request(provider="openai", model="gpt-4o-mini", prompt="...", system_prompt="...")
        # ... LLM 调用 ...
        auditor.log_response(raw_response="...", parsed={"result": ...}, duration_ms=1234)
        auditor.save()
    """

    def __init__(
        self,
        *,
        output_dir: str | Path = "output/llm_audit",
        enabled: bool = True,
        include_full_prompt: bool = True,
        include_full_response: bool = True,
    ):
        """初始化 LLM 审计器。

        Args:
            output_dir: 审计文件输出目录
            enabled: 是否启用审计（支持全局开关）
            include_full_prompt: 是否保存完整 prompt（可能很大）
            include_full_response: 是否保存完整 response（可能很大）
        """
        self.output_dir = Path(output_dir)
        self.enabled = enabled
        self.include_full_prompt = include_full_prompt
        self.include_full_response = include_full_response

        self._call_id = str(uuid.uuid4())[:12]
        self._start_time: float | None = None
        self._data: dict[str, Any] = {}

        if self.enabled:
            self.output_dir.mkdir(parents=True, exist_ok=True)

    def log_request(
        self,
        *,
        provider: str,
        model: str,
        prompt: str,
        system_prompt: str = "",
        parameters: dict[str, Any] | None = None,
        source: str = "unknown",
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """记录 LLM 请求信息。

        Args:
            provider: LLM 提供商 (openai, anthropic, etc.)
            model: 模型名称
            prompt: 用户 prompt
            system_prompt: 系统 prompt
            parameters: 额外参数 (temperature, max_tokens, etc.)
            source: 调用来源标识 (LLMAdvisor, LLMOutputAdjudicator, etc.)
            session_id: 会话ID，用于关联同一次任务/实验的多个LLM调用
            metadata: 额外的元数据 (scanner_name, skill_path, iteration, etc.)
        """
        if not self.enabled:
            return

        self._start_time = time.time()
        self._data = {
            "call_id": self._call_id,
            "session_id": session_id or self._call_id,  # 默认使用 call_id 作为 session_id
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "provider": provider,
            "model": model,
            "request": {
                "prompt": self._maybe_truncate(prompt) if self.include_full_prompt else self._truncate(prompt, 500),
                "system_prompt": self._maybe_truncate(system_prompt) if self.include_full_prompt else self._truncate(system_prompt, 500),
                "parameters": parameters or {},
            },
            "response": None,
            "duration_ms": None,
            "metadata": metadata or {},
        }
        logger.debug(f"[LLM Audit] Request logged: {source}/{provider}/{model} (call_id={self._call_id}, session_id={self._data['session_id']})")

    def log_response(
        self,
        *,
        raw_response: str,
        parsed_response: Any = None,
        error: str | None = None,
        duration_ms: int | None = None,
        usage: dict[str, int] | None = None,
    ) -> None:
        """记录 LLM 响应信息。

        Args:
            raw_response: 原始响应文本
            parsed_response: 解析后的响应（可能是 dict 或其他结构）
            error: 错误信息（仅在失败时）
            duration_ms: 调用耗时（毫秒）
            usage: Token 使用统计，包含 prompt_tokens, completion_tokens, total_tokens
        """
        if not self.enabled:
            return

        if self._start_time is None and duration_ms is None:
            logger.warning("[LLM Audit] log_response called without log_request")
            return

        # 如果没有提供 duration_ms，计算它
        if duration_ms is None and self._start_time is not None:
            duration_ms = int((time.time() - self._start_time) * 1000)

        self._data["duration_ms"] = duration_ms
        response_data = {
            "raw": self._maybe_truncate(raw_response) if self.include_full_response else self._truncate(raw_response, 1000),
            "parsed": parsed_response if self.include_full_response else self._compact_json(parsed_response),
            "error": error,
        }
        # 添加 token 使用统计（如果提供）
        if usage:
            response_data["usage"] = usage

        self._data["response"] = response_data
        logger.debug(f"[LLM Audit] Response logged: duration={duration_ms}ms (call_id={self._call_id})")

    def save(self) -> Path | None:
        """保存审计记录到文件。

        Returns:
            保存的文件路径，如果审计未启用则返回 None
        """
        if not self.enabled:
            return None

        if not self._data:
            logger.warning("[LLM Audit] No data to save")
            return None

        # 生成文件名：{timestamp}_{source}_{call_id}.json
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        source = self._data.get("source", "unknown").replace("/", "_")
        filename = f"{timestamp}_{source}_{self._call_id}.json"
        output_path = self.output_dir / filename

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            logger.info(f"[LLM Audit] Saved to {output_path}")
            return output_path
        except Exception as exc:
            logger.error(f"[LLM Audit] Failed to save: {exc}")
            return None

    def append_to_index(self) -> None:
        """将本次调用追加到索引文件 (index.jsonl)。

        使用全局锁保护并发写入，确保多线程环境下的数据完整性。
        """
        if not self.enabled or not self._data:
            return

        index_path = self.output_dir / "index.jsonl"
        try:
            # 创建精简的索引记录
            response_data = self._data.get("response", {}) or {}
            index_record = {
                "call_id": self._data.get("call_id"),
                "session_id": self._data.get("session_id"),
                "timestamp": self._data.get("timestamp"),
                "source": self._data.get("source"),
                "provider": self._data.get("provider"),
                "model": self._data.get("model"),
                "duration_ms": self._data.get("duration_ms"),
                "error": response_data.get("error"),
                "usage": response_data.get("usage"),  # Token 统计
                "metadata": self._data.get("metadata", {}),
            }
            # 使用全局锁保护并发写入
            with _INDEX_LOCK:
                with open(index_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(index_record, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.error(f"[LLM Audit] Failed to append to index: {exc}")

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        """截断文本到指定长度。"""
        if not isinstance(text, str):
            text = str(text)
        if len(text) <= max_len:
            return text
        return text[:max_len] + "...[truncated]"

    @staticmethod
    def _maybe_truncate(text: str, max_len: int = 10000) -> str:
        """仅在文本超过最大长度时截断。"""
        if not isinstance(text, str):
            text = str(text)
        if len(text) <= max_len:
            return text
        return text[:max_len] + f"...[truncated {len(text)-max_len} chars]"

    @staticmethod
    def _compact_json(data: Any, max_len: int = 1000) -> Any:
        """压缩 JSON 数据用于保存。"""
        if isinstance(data, dict):
            compact = {}
            for k, v in data.items():
                compact[k] = LLMCallAuditor._compact_json(v, max_len)
            return compact
        elif isinstance(data, list):
            return [LLMCallAuditor._compact_json(item, max_len) for item in data[:10]]  # 最多 10 项
        elif isinstance(data, str):
            return LLMCallAuditor._truncate(data, max_len)
        else:
            return data


class LLMAuditConfig:
    """LLM 审计配置。

    从配置文件加载审计设置：
    ```yaml
    llm_audit:
      enabled: true
      output_dir: "output/llm_audit"
      include_full_prompt: true
      include_full_response: true
    ```
    """

    def __init__(
        self,
        *,
        enabled: bool = False,
        output_dir: str | Path = "output/llm_audit",
        include_full_prompt: bool = True,
        include_full_response: bool = True,
    ):
        self.enabled = enabled
        self.output_dir = Path(output_dir)
        self.include_full_prompt = include_full_prompt
        self.include_full_response = include_full_response

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "LLMAuditConfig":
        """从字典创建配置。"""
        return cls(
            enabled=config_dict.get("enabled", False),
            output_dir=config_dict.get("output_dir", "output/llm_audit"),
            include_full_prompt=config_dict.get("include_full_prompt", True),
            include_full_response=config_dict.get("include_full_response", True),
        )

    @classmethod
    def from_yaml_config(cls, raw_config: dict) -> "LLMAuditConfig":
        """从 YAML 配置加载（支持嵌套的 llm_audit 字段）。"""
        llm_audit_config = raw_config.get("llm_audit", {})
        if not isinstance(llm_audit_config, dict):
            llm_audit_config = {}
        return cls.from_dict(llm_audit_config)

    def create_auditor(self, source: str = "unknown") -> LLMCallAuditor:
        """创建配置好的审计器实例。"""
        return LLMCallAuditor(
            output_dir=self.output_dir,
            enabled=self.enabled,
            include_full_prompt=self.include_full_prompt,
            include_full_response=self.include_full_response,
        )


def create_auditor_from_config(config: LLMAuditConfig | dict | None, source: str = "unknown") -> LLMCallAuditor:
    """便捷函数：从配置创建审计器。

    Args:
        config: 审计配置（LLMAuditConfig 实例或字典）
        source: 调用来源标识
    """
    if config is None:
        return LLMCallAuditor(enabled=False)

    if isinstance(config, dict):
        config = LLMAuditConfig.from_dict(config)

    auditor = config.create_auditor(source=source)
    return auditor
