# Copyright 2026
#
# Feedback-driven generator base class for iterative adversarial testing.

"""
FeedbackDrivenGenerator — Template Method base for generators that iterate
based on scanner feedback.

All feedback-driven generators share the same iteration logic:
1. First iteration: generate initial rewrite (subclass-specific)
2. If detected: analyze feedback and rewrite to evade detection
3. If not detected (bypass success): keep current output

Subclasses only need to implement 5 abstract methods that define
the "variable parts" of the algorithm.

Non-iterative generators (BashScriptDrop, ImageDrop, DirectScan) remain
as direct children of BaseGeneratorWithScript / BaseGenerator.
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .base import BaseGeneratorWithScript, FeedbackAnalysis

if TYPE_CHECKING:
    from .skill_camo.llm_advisor import LLMAdvisor

logger = logging.getLogger(__name__)


class FeedbackDrivenGenerator(BaseGeneratorWithScript):
    """
    Intermediate base class for generators that iterate using LLM feedback.

    Uses the Template Method pattern: this class provides the concrete
    generate() and analyze_feedback() implementations with the invariant
    iteration logic, while subclasses implement the variable parts via
    abstract methods.
    """

    # Severity rank used by the early-bad-stop heuristic. Higher = worse.
    _SEVERITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}

    def __init__(
        self,
        config,
        script_path: Path | None = None,
        harmful_sh_dir: Path | None = None,
        early_stop_window: int = 0,
        **kwargs,
    ):
        super().__init__(config, script_path, harmful_sh_dir)
        self._current_skill_md: str | None = None
        self._compact_feedback: dict[str, Any] | None = None
        # Early-bad-stop: if the max severity does not strictly decrease for
        # ``early_stop_window`` consecutive detected iterations, the next
        # analyze_feedback() call returns next_action="early_stop". 0 disables.
        # Set via subclass config; orchestrator honours the signal by breaking
        # the iteration loop, saving downstream LLM/scanner calls when scanner
        # has already locked onto a persistent detection signature.
        self._early_stop_window: int = max(0, int(early_stop_window))
        self._severity_history: list[int] = []

    # ------------------------------------------------------------------
    # Abstract methods — the "variable parts" each subclass must define
    # ------------------------------------------------------------------

    @abstractmethod
    def _initial_rewrite(self, context: dict[str, Any] | None = None) -> str:
        """First-iteration rewrite.

        Called when ``self._current_skill_md`` is ``None`` or feedback is
        ``None`` (i.e. the very first call in the iteration loop).

        Args:
            context: Optional extra context dict from the caller (e.g.
                ``finalized_prompt``).

        Returns:
            The rewritten SKILL.md content as a string.
        """
        ...

    @abstractmethod
    def _feedback_rewrite(
        self,
        previous_md: str,
        compact_feedback: dict,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Feedback-driven rewrite.

        Called when the scanner detected the previous iteration's output.
        The subclass should use *compact_feedback* to produce a less
        suspicious SKILL.md.

        Args:
            previous_md: The SKILL.md content from the previous iteration.
            compact_feedback: Summarised scanner feedback used as rewrite
                context for the next iteration.
            context: Optional extra context dict from the caller (e.g.
                ``finalized_prompt``).

        Returns:
            The rewritten SKILL.md content as a string.
        """
        ...

    @abstractmethod
    def _compute_compact_feedback(self, scan_result: dict) -> dict:
        """Compress the raw scan result into a feedback dict for rewriting.

        Generators should return the rewrite-oriented compact feedback shape
        consumed by their ``_feedback_rewrite()`` implementation. Current
        in-tree generators use ``LLMAdvisor.analyze_scan_result()`` for that
        compact feedback, while ``analyze_feedback()`` still records the
        deterministic ``reduce_scan_result()`` output for audit/context.
        """
        ...

    @abstractmethod
    def _deliver_skill(self, iteration: int, rewritten_skill_md: str) -> Path:
        """Write the rewritten markdown to disk and return the skill path.

        SkilljectGenerator handles file I/O directly; image-injection
        generators delegate to ``ImageInjector.inject_with_*()``.
        """
        ...

    @abstractmethod
    def _get_llm_advisor(self) -> LLMAdvisor:
        """Return this generator's LLMAdvisor instance.

        Used by ``analyze_feedback()`` to record the reduced scan result.
        """
        ...

    # ------------------------------------------------------------------
    # Strategy-name hooks (optional overrides for FeedbackAnalysis text)
    # ------------------------------------------------------------------

    def _get_detected_strategy_name(self) -> str:
        return "rewrite_with_feedback"

    def _get_detected_reason(self) -> str:
        return "Detected by scanner, will rewrite using feedback"

    def _get_success_strategy_name(self) -> str:
        return "success"

    def _get_success_reason(self) -> str:
        return "Successfully bypassed detection"

    # ------------------------------------------------------------------
    # Concrete methods — the invariant iteration algorithm
    # ------------------------------------------------------------------

    def generate(
        self,
        iteration: int,
        feedback: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> Path:
        """Unified iteration loop.

        Branch 1 (first iteration): call ``_initial_rewrite()``.
        Branch 2 (detected):         call ``_compute_compact_feedback()`` then ``_feedback_rewrite()``.
        Branch 3 (success):          reuse ``self._current_skill_md`` unchanged.

        Args:
            iteration: Current iteration number.
            feedback: Scanner feedback from the previous iteration.
            context: Optional extra context dict from the caller (e.g.
                ``finalized_prompt``).

        Returns:
            Path to the generated skill directory.
        """
        self._initialize()

        if self._current_skill_md is None or feedback is None:
            rewritten_skill_md = self._initial_rewrite(context=context)
        elif feedback.get("detected", False):
            self._compact_feedback = self._compute_compact_feedback(
                feedback.get("scan_result", {}),
            )
            rewritten_skill_md = self._feedback_rewrite(
                self._current_skill_md,
                self._compact_feedback,
                context=context,
            )
        else:
            rewritten_skill_md = self._current_skill_md

        self._current_skill_md = rewritten_skill_md

        return self._deliver_skill(iteration, rewritten_skill_md)

    def analyze_feedback(self, feedback: dict[str, Any]) -> dict[str, Any]:
        """Unified feedback analysis.

        Always includes ``compact_feedback`` and ``reduced_scan_result``
        when detected, giving a consistent output format across all
        feedback-driven generators. When ``early_stop_window`` is configured
        and the scanner severity has plateaued for that many consecutive
        detected iterations, returns ``next_action="early_stop"`` so the
        orchestrator can break the loop instead of burning more budget on a
        feedback signature the scanner has clearly locked onto.
        """
        detected = feedback.get("detected", False)

        if detected:
            reduced_scan_result = self._get_llm_advisor().reduce_scan_result(
                feedback.get("scan_result", {}),
            )
            rank = self._extract_max_severity_rank(feedback.get("scan_result", {}))
            self._severity_history.append(rank)
            if self._should_early_stop():
                return FeedbackAnalysis(
                    detected=True,
                    strategy="early_bad_stop",
                    reason=(
                        f"Severity plateaued at rank {rank} for "
                        f"{self._early_stop_window + 1} consecutive iterations — "
                        "further rewriting unlikely to reduce detection."
                    ),
                    next_action="early_stop",
                    compact_feedback=self._compact_feedback or {},
                    reduced_scan_result=reduced_scan_result,
                ).to_dict()
            return FeedbackAnalysis(
                detected=True,
                strategy=self._get_detected_strategy_name(),
                reason=self._get_detected_reason(),
                next_action="adjust_strategy",
                compact_feedback=self._compact_feedback or {},
                reduced_scan_result=reduced_scan_result,
            ).to_dict()
        else:
            self._severity_history.append(0)
            return FeedbackAnalysis(
                detected=False,
                strategy=self._get_success_strategy_name(),
                reason=self._get_success_reason(),
                next_action="success",
            ).to_dict()

    # ------------------------------------------------------------------
    # Early-bad-stop helpers
    # ------------------------------------------------------------------

    @classmethod
    def _extract_max_severity_rank(cls, scan_result: dict[str, Any]) -> int:
        """Return the worst severity rank seen across all scanners (0 = none)."""
        if not isinstance(scan_result, dict):
            return 0
        worst = 0
        # Top-level convenience field
        worst = max(worst, cls._SEVERITY_RANK.get(
            str(scan_result.get("max_severity", "")).upper(), 0,
        ))
        scanners = scan_result.get("scanners", {})
        if isinstance(scanners, dict):
            for data in scanners.values():
                if isinstance(data, dict):
                    worst = max(worst, cls._SEVERITY_RANK.get(
                        str(data.get("max_severity", "")).upper(), 0,
                    ))
        return worst

    def _should_early_stop(self) -> bool:
        """True when severity has not strictly decreased over the window."""
        window = self._early_stop_window
        if window <= 0 or len(self._severity_history) < window + 1:
            return False
        tail = self._severity_history[-(window + 1):]
        # Plateau or rise across the last (window+1) detected iterations.
        return all(later >= earlier for earlier, later in zip(tail, tail[1:]))
