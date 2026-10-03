#!/usr/bin/env python3
"""Closed-loop demo: SkillCamo attack against a scanner with feedback iterations.

Pipeline per iteration:
  1. LLM rewrites SKILL.md (adaptive to the skill's domain and scanner feedback)
  2. the malicious command is rendered into a bundled image
  3. the generated skill is scanned; HIGH/CRITICAL = detected
  4. if detected, compact feedback feeds the next rewrite

Requires: API keys in .env (see .env.example) for the attack LLM and for
LLM-based scanners. For a zero-key smoke of the deterministic cores, run the
unit tests instead: pytest tests/test_skill_camo_core.py

Usage:
  python examples/run_attack_demo.py \
      --skill data/benchmark/benign_base_100/<skill-name> \
      --script data/harmful_sh/<payload>.sh \
      --output outputs/demo
"""

from __future__ import annotations

import argparse
from pathlib import Path

from skillcamo.unified_scanner.generators.skill_camo.orchestrator import (
    run_injection_test,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", required=True, help="base benign skill directory")
    parser.add_argument("--script", required=True, help="harmful one-line shell script")
    parser.add_argument("--output", default="outputs/demo", help="output directory")
    parser.add_argument("--max-iterations", type=int, default=5)
    parser.add_argument("--llm-model", default="gpt-5-mini")
    args = parser.parse_args()

    result = run_injection_test(
        base_skill=Path(args.skill),
        script=Path(args.script),
        max_iterations=args.max_iterations,
        output_dir=Path(args.output),
        llm_model=args.llm_model,
    )

    print(f"bypass_success={result.success} iterations={result.total_iterations}")
    for attempt in result.attempts:
        print(f"  iter {attempt.iteration}: detected={attempt.detected}")


if __name__ == "__main__":
    main()
