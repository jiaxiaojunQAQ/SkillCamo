# Copyright 2026
#
# Direct scan generator (no mutation).

"""
Direct scan generator — passes the original skill through without modification.

Returns the original skill path for scanning by the pipeline orchestrator.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BaseGenerator, GeneratorConfig, FeedbackAnalysis, _flatten_config, _default_output_dir


class DirectScanGenerator(BaseGenerator):
    """Generator that passes the original skill through without mutation."""

    @classmethod
    def from_config_dict(cls, config_dict: dict) -> "DirectScanGenerator":
        flat = _flatten_config(config_dict)
        base_config = GeneratorConfig(
            base_skill_path=Path(flat.get("base_skill_path", ".")),
            threat_type=flat.get("threat_type", "command_injection"),
            max_iterations=flat.get("max_iterations", 1),
            output_dir=Path(flat["output_dir"]) if flat.get("output_dir") else _default_output_dir(),
            llm_provider=flat.get("llm_provider", "openai"),
            llm_model=flat.get("llm_model", "gpt-4o-mini"),
            verbose=flat.get("verbose", True),
            harmful_script_path=Path(flat.get("harmful_script_path", "")),
        )
        return cls(base_config)

    def generate(self, iteration: int, feedback: dict[str, Any] | None = None, *, context: dict[str, Any] | None = None) -> Path:
        """Return the original skill path unchanged."""
        del iteration, feedback
        return self.config.base_skill_path

    def analyze_feedback(self, feedback: dict[str, Any]) -> dict[str, Any]:
        detected = bool(feedback.get("detected", False))
        return FeedbackAnalysis(
            detected=detected,
            strategy="direct_scan",
            reason="Direct scan completed",
            next_action="success" if not detected else "stop",
        ).to_dict()
