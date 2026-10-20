from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from skillcamo.defenses.execscan import execscan


class ScanExecscanOpenAIClientTests(unittest.TestCase):
    def test_make_client_uses_openai_env_vars(self) -> None:
        previous_key = os.environ.get("OPENAI_API_KEY")
        previous_base = os.environ.get("OPENAI_BASE_URL")
        previous_timeout = os.environ.pop("LLM_REQUEST_TIMEOUT", None)  # ensure default 180
        os.environ["OPENAI_API_KEY"] = "openai-key"
        os.environ["OPENAI_BASE_URL"] = "https://openai.example/v1"
        try:
            with patch("openai.OpenAI") as mock_openai:
                execscan.make_client()
        finally:
            if previous_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = previous_key
            if previous_base is None:
                os.environ.pop("OPENAI_BASE_URL", None)
            else:
                os.environ["OPENAI_BASE_URL"] = previous_base
            if previous_timeout is not None:
                os.environ["LLM_REQUEST_TIMEOUT"] = previous_timeout

        mock_openai.assert_called_once_with(
            api_key="openai-key", base_url="https://openai.example/v1",
            timeout=180.0, max_retries=6,
        )

    def test_make_client_requires_openai_api_key(self) -> None:
        previous_key = os.environ.pop("OPENAI_API_KEY", None)
        previous_base = os.environ.pop("OPENAI_BASE_URL", None)
        try:
            with self.assertRaises(RuntimeError) as exc:
                execscan.make_client()
        finally:
            if previous_key is not None:
                os.environ["OPENAI_API_KEY"] = previous_key
            if previous_base is not None:
                os.environ["OPENAI_BASE_URL"] = previous_base

        self.assertIn("OPENAI_API_KEY", str(exc.exception))

    def test_call_model_uses_openai_chat_completions(self) -> None:
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))]
        )
        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kwargs: response
                )
            )
        )

        result = execscan.call_model(
            client=client,
            model="gpt-5-mini",
            system_prompt="system",
            content_blocks=[{"type": "text", "text": "hello"}],
            max_tokens=123,
        )

        self.assertEqual(result, {"ok": True})

    def test_image_block_uses_openai_data_url_shape(self) -> None:
        with patch("pathlib.Path.read_bytes", return_value=b"png-bytes"), patch(
            "mimetypes.guess_type", return_value=("image/png", None)
        ):
            block = execscan.image_block_from_path(execscan.Path("command.png"))

        self.assertEqual(block["type"], "image_url")
        self.assertTrue(block["image_url"]["url"].startswith("data:image/png;base64,"))


class RobustJsonParseReasoningModelTests(unittest.TestCase):
    """Reasoning models (e.g. MiniMax-M3) wrap JSON in <think>...</think>; the think
    prose can carry braces that contaminate outermost-{...} extraction. robust_json_parse
    must strip think blocks before parsing."""

    def test_strips_think_block_with_json_fence(self) -> None:
        raw = '<think>reasoning, no braces here</think>\n\n```json\n{"verdict": "UNSAFE"}\n```'
        self.assertEqual(execscan.robust_json_parse(raw), {"verdict": "UNSAFE"})

    def test_strips_think_block_with_brace_contamination(self) -> None:
        # think prose contains {...} that would otherwise be grabbed by find("{")
        raw = '<think>the schema is {"k": v} and code func(){ return }</think>\n{"verdict": "SAFE"}'
        self.assertEqual(execscan.robust_json_parse(raw), {"verdict": "SAFE"})

    def test_plain_json_without_think_unaffected(self) -> None:
        self.assertEqual(execscan.robust_json_parse('{"risk_score": 0.5}'), {"risk_score": 0.5})

    def test_dangling_unclosed_think_yields_no_json(self) -> None:
        # model burned all tokens thinking, emitted no JSON -> honest parse failure
        raw = "<think>long reasoning truncated by max_tokens, never emits json"
        with self.assertRaises(Exception):
            execscan.robust_json_parse(raw)
