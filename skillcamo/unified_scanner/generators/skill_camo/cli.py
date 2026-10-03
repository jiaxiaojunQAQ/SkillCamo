# Copyright 2026
#
# CLI for LLM-driven image command injection.

"""
Command-line interface for LLM-driven image injection framework.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from .models import InjectionConfig
from .orchestrator import ImageInjectionOrchestrator, run_injection_test
from .skill_analyzer import SkillAnalyzer
from ...utils import setup_logging as utils_setup_logging


def _short_error_message(error: Exception | str, max_len: int = 300) -> str:
    text = str(error).replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len] + "...[truncated]"


def _load_root_env():
    """Load .env from project root directory"""
    import os

    # Try multiple methods to find .env
    env_file = None

    # Method 1: Check current working directory first (most reliable)
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        env_file = cwd_env

    # Method 2: Try using __file__ if available
    if env_file is None:
        try:
            # Start from this file and go up
            current = Path(__file__).resolve().parent
            while current != current.parent:  # Not at filesystem root
                test_env = current / ".env"
                if test_env.exists():
                    env_file = test_env
                    break
                current = current.parent
        except:
            pass

    # Method 3: Try relative path as fallback
    if env_file is None:
        try:
            project_root = Path(__file__).parent.parent.parent.parent.parent
            test_env = project_root / ".env"
            if test_env.exists():
                env_file = test_env
        except:
            pass

    # Load environment variables from .env file
    if env_file and env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                # Remove quotes
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                os.environ[key] = value

    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                # Remove quotes
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                os.environ[key] = value


def cmd_run(args) -> int:
    """Run injection test command"""
    # Validate inputs
    base_skill = Path(args.base_skill)
    if not base_skill.exists():
        print(f"Error: Skill not found: {base_skill}")
        return 1

    script = Path(args.script)
    if not script.exists():
        print(f"Error: Script not found: {script}")
        return 1

    # Set API key from command line if provided
    import os
    if args.api_key:
        if args.llm_provider == "openai":
            os.environ["OPENAI_API_KEY"] = args.api_key
        elif args.llm_provider == "anthropic":
            os.environ["ANTHROPIC_API_KEY"] = args.api_key

    # Check for API key
    provider = args.llm_provider
    if provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set")
        print("Set it with: export OPENAI_API_KEY='your-key'")
        print("Or use --api-key option")
        return 1
    if provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set")
        print("Set it with: export ANTHROPIC_API_KEY='your-key'")
        print("Or use --api-key option")
        return 1

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    utils_setup_logging(
        level=level,
        format_string="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Run test
    try:
        result = run_injection_test(
            base_skill=base_skill,
            script=script,
            max_iterations=args.max_iterations,
            output_dir=args.output,
            llm_provider=provider,
            llm_model=args.llm_model,
            verbose=args.verbose,
        )

        # Print result
        print(f"\n{'='*60}")
        print(f"Result: {'SUCCESS' if result.success else 'FAILED'}")
        print(f"{'='*60}")
        print(f"Iterations: {result.total_iterations}")
        print(f"Duration: {result.duration_seconds:.1f}s")

        if result.success:
            print(f"\nBypassed at iteration {result.total_iterations}")
            if result.successful_strategy:
                print(f"Reason: {result.successful_strategy.reason}")
            print(f"\nFinal skill: {result.final_skill_path}")

        return 0 if result.success else 1

    except Exception as e:
        print(f"Error: {_short_error_message(e)}")
        return 1


def cmd_analyze(args) -> int:
    """Analyze skill command"""
    skill_path = Path(args.skill)
    if not skill_path.exists():
        print(f"Error: Skill not found: {skill_path}")
        return 1

    try:
        analyzer = SkillAnalyzer(skill_path)
        context = analyzer.analyze()

        print(f"\n=== Skill Analysis: {skill_path.name} ===")
        print(f"Total lines: {context.total_lines}")
        print(f"Sections: {len(context.sections)}")
        print(f"Has resources: {context.has_resources}")

        print("\n--- Sections ---")
        for section in context.sections:
            print(f"  {'#' * section.level} {section.name} (line {section.start_line})")

        return 0

    except Exception as e:
        print(f"Error: {_short_error_message(e)}")
        return 1


def main() -> int:
    """Main entry point"""
    # Load .env from project root
    _load_root_env()

    parser = argparse.ArgumentParser(
        description="LLM-Driven Skill Camo Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze a skill
  python -m adversarial.skill_camo.cli analyze ./test_skill

  # Run injection test (default 5 iterations)
  python -m adversarial.skill_camo.cli run \\
      --base-skill ./test_skill \\
      --script harmful_sh/exfiltration/env_exfil.sh

  # Run with more iterations
  python -m adversarial.skill_camo.cli run \\
      --base-skill ./test_skill \\
      --script harmful_sh/exfiltration/env_exfil.sh \\
      --max-iterations 10

  # Use OpenAI instead
  python -m adversarial.skill_camo.cli run \\
      --base-skill ./test_skill \\
      --script harmful_sh/exfiltration/env_exfil.sh \\
      --llm-provider openai \\
      --llm-model gpt-4
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze skill structure")
    analyze_parser.add_argument("skill", help="Path to skill directory")
    analyze_parser.set_defaults(func=cmd_analyze)

    # run command
    run_parser = subparsers.add_parser("run", help="Run injection test")
    run_parser.add_argument(
        "--base-skill",
        required=True,
        help="Path to base skill directory",
    )
    run_parser.add_argument(
        "--script",
        required=True,
        help="Path to harmful script file",
    )
    run_parser.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Maximum iterations (default: 5)",
    )
    run_parser.add_argument(
        "--output",
        default="outputs",
        help="Output directory (default: outputs)",
    )
    run_parser.add_argument(
        "--llm-provider",
        choices=["anthropic", "openai"],
        default="openai",
        help="LLM provider (default: openai)",
    )
    run_parser.add_argument(
        "--llm-model",
        default=None,
        help="LLM model (default: gpt-4o-mini for openai)",
    )
    run_parser.add_argument(
        "--api-key",
        default=None,
        help="API key (overrides environment variable)",
    )
    run_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )
    run_parser.set_defaults(func=cmd_run)

    # Parse and execute
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
