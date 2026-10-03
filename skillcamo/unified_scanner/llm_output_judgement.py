"""LLM adjudication for scanner outputs."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

try:
    from unified_scanner.rate_limiter import random_delay, get_shared_limiter
    from unified_scanner.llm_audit import LLMAuditConfig, create_auditor_from_config
except ImportError:
    from rate_limiter import random_delay, get_shared_limiter
    from llm_audit import LLMAuditConfig, create_auditor_from_config

ALLOWED_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
ALLOWED_CONFIDENCE = {"low", "medium", "high"}


class LLMOutputAdjudicator:
    """Ask an LLM to classify scanner output using the unified four-level severity scale."""

    def __init__(
        self,
        *,
        provider: str = "openai",
        model: str = "gpt-5-mini",
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = 120,
        audit_config: LLMAuditConfig | dict | None = None,
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self._audit_config = audit_config
        self._auditor = create_auditor_from_config(audit_config, source="LLMOutputAdjudicator")

    def adjudicate(self, scanner_name: str, scanner_output: dict[str, Any]) -> dict[str, Any]:
        """Return a normalized judgement and full audit material for one scanner output."""
        prompt = self._build_prompt(scanner_name, scanner_output)
        started = time.time()
        raw_response = ""
        parsed: dict[str, Any] = {}

        try:
            self._require_non_empty_raw_output(scanner_output)
            raw_response = self._call_llm_with_retries(prompt)
            parsed = self._extract_json_object(raw_response)
            judgement = self._normalize_judgement(parsed)
            judgement["duration_ms"] = int((time.time() - started) * 1000)
            judgement["audit"] = self._build_audit(scanner_name, scanner_output, prompt, raw_response, judgement)
            return judgement
        except Exception as exc:
            failed = {
                "enabled": True,
                "status": "failed",
                "severity": None,
                "is_harmful": None,
                "confidence": None,
                "reason": "",
                "evidence": [],
                "provider": self.provider,
                "model": self.model,
                "duration_ms": int((time.time() - started) * 1000),
                "error": str(exc),
            }
            failed["audit"] = self._build_audit(scanner_name, scanner_output, prompt, raw_response, parsed or failed)
            return failed

    def _require_non_empty_raw_output(self, scanner_output: dict[str, Any]) -> None:
        raw_output = ""
        if isinstance(scanner_output, dict):
            raw_output = str(scanner_output.get("raw_output_text", ""))
        if raw_output.strip():
            return
        raise ValueError("Claude scanner returned empty raw output")

    def _build_prompt(self, scanner_name: str, scanner_output: dict[str, Any]) -> str:
        raw_output = ""
        if isinstance(scanner_output, dict):
            raw_output = str(scanner_output.get("raw_output_text", ""))
        metadata = scanner_output.get("metadata", {}) if isinstance(scanner_output, dict) else {}
        metadata_json = json.dumps(metadata, ensure_ascii=False, indent=2, default=str)
        return f"""You are adjudicating one Claude-based security scanner output for an AI agent skill.

Use ONLY the scanner output below. The original SKILL.md is unavailable unless quoted inside the agent output.

Return exactly one JSON object with these fields:
- severity: one of CRITICAL, HIGH, MEDIUM, LOW
- confidence: one of low, medium, high
- reason: concise explanation
- evidence: array of short evidence strings from scanner outputs

Severity rules:
- CRITICAL: clear malicious or high-impact behavior such as command injection, data exfiltration, malware, destructive actions, or confirmed malicious code.
- HIGH: important security issue such as privilege escalation, credential/funds/system modification risk, or clear social engineering.
- MEDIUM: suspicious pattern, policy violation, or incomplete evidence that needs human attention but is not clearly high-impact.
- LOW: low risk, informational, no material threat, or scanner output shows no substantive threat.

Scanner:
{scanner_name}

Metadata:
---METADATA_START---
{metadata_json}
---METADATA_END---

Agent output:
---AGENT_OUTPUT_START---
{raw_output}
---AGENT_OUTPUT_END---
"""

    def _call_llm_with_retries(self, prompt: str, max_attempts: int = 4) -> str:
        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            try:
                return self._call_llm(prompt)
            except Exception as exc:
                last_exc = exc
                if attempt < max_attempts - 1:
                    # Exponential backoff with jitter via shared utility.
                    # Backing off lets rate-limited endpoints (e.g. MiMo 429)
                    # recover; jitter spreads concurrent workers so they
                    # don't retry in lockstep.
                    delay = random_delay(attempt)
                    time.sleep(delay)
        if last_exc is None:
            raise RuntimeError("LLM judgement failed without an exception")
        raise last_exc

    def _call_llm(self, prompt: str) -> str:
        if self.provider != "openai":
            raise ValueError(f"Unsupported LLM judgement provider: {self.provider}")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError("openai package not installed") from exc

        api_key = self.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("API key not set for LLM judgement provider 'openai'")

        base_url = self.base_url or os.environ.get("OPENAI_BASE_URL")

        # 记录请求审计
        if self._auditor and self._auditor.enabled:
            self._auditor.log_request(
                provider=self.provider,
                model=self.model,
                prompt=prompt,
                system_prompt="You classify scanner outputs. Return valid JSON only.",
                source="LLMOutputAdjudicator",
            )

        # Proactive throttle: keep aggregate QPS across worker threads under the
        # provider limit (no-op unless LLM_MAX_RPM is set). max_retries lets the
        # OpenAI SDK itself back off on 429/5xx honoring any Retry-After header.
        limiter = get_shared_limiter()
        if limiter is not None:
            limiter.acquire()

        client = OpenAI(api_key=api_key, base_url=base_url, timeout=self.timeout, max_retries=6)
        messages = [
            {
                "role": "system",
                "content": "You classify scanner outputs. Return valid JSON only.",
            },
            {"role": "user", "content": prompt},
        ]
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        if not getattr(response, "choices", None):
            # 记录错误审计
            if self._auditor and self._auditor.enabled:
                self._auditor.log_response(raw_response=str(response), error="API response missing choices")
                self._auditor.save()
            raise ValueError("API response missing choices")
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            # 记录错误审计
            if self._auditor and self._auditor.enabled:
                self._auditor.log_response(raw_response=content, error="Empty judgement response")
                self._auditor.save()
            raise ValueError("LLM returned empty judgement response")

        # 记录成功响应审计
        if self._auditor and self._auditor.enabled:
            self._auditor.log_response(raw_response=content)
            self._auditor.save()
            self._auditor.append_to_index()

        return content

    def _extract_json_object(self, raw_response: str) -> dict[str, Any]:
        text = raw_response.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            text = fenced.group(1).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("LLM judgement response did not contain a JSON object")
        payload = json.loads(text[start:end + 1])
        if not isinstance(payload, dict):
            raise ValueError("LLM judgement response must be a JSON object")
        return payload

    def _normalize_judgement(self, parsed: dict[str, Any]) -> dict[str, Any]:
        severity = str(parsed.get("severity", "")).upper()
        if severity not in ALLOWED_SEVERITIES:
            raise ValueError(
                f"Invalid LLM severity {severity!r}; expected one of {', '.join(sorted(ALLOWED_SEVERITIES))}"
            )

        confidence = str(parsed.get("confidence", "low")).lower()
        if confidence not in ALLOWED_CONFIDENCE:
            confidence = "low"

        evidence = parsed.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = [str(evidence)]

        return {
            "enabled": True,
            "status": "success",
            "severity": severity,
            "is_harmful": severity in {"CRITICAL", "HIGH"},
            "confidence": confidence,
            "reason": str(parsed.get("reason", "")),
            "evidence": [str(item) for item in evidence],
            "provider": self.provider,
            "model": self.model,
            "error": None,
        }

    def _build_audit(
        self,
        scanner_name: str,
        scanner_output: dict[str, Any],
        prompt: str,
        raw_response: str,
        parsed_judgement: dict[str, Any],
    ) -> dict[str, Any]:
        audit_input = self._build_judge_input_snapshot(scanner_output)
        return {
            "scanner_outputs": {scanner_name: audit_input},
            "prompt": prompt,
            "raw_response": raw_response,
            "parsed_judgement": _public_judgement(parsed_judgement),
        }

    def _build_judge_input_snapshot(self, scanner_output: dict[str, Any]) -> dict[str, Any]:
        """Return the exact scanner payload shape exposed to the judge.

        Judge input should be limited to parsed agent output plus lightweight metadata,
        not raw CLI stdout/stderr audit material.
        """
        if not isinstance(scanner_output, dict):
            return {}

        metadata = scanner_output.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        return {
            "findings": scanner_output.get("findings", []),
            "metadata": metadata,
            "raw_output_text": str(scanner_output.get("raw_output_text", "")),
        }


def _public_judgement(judgement: dict[str, Any]) -> dict[str, Any]:
    """Drop bulky audit material from a judgement dict."""
    return {key: value for key, value in judgement.items() if key != "audit"}


def compact_llm_judgement(judgement: dict[str, Any]) -> dict[str, Any]:
    """Return the scan_result.json representation without full audit material."""
    return _public_judgement(judgement)
