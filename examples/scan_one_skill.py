#!/usr/bin/env python3
"""Scan a single skill with ExecScan (the paper's defense) or a baseline scanner.

ExecScan requires an OpenAI-compatible endpoint (.env); scan_skillfortify is
pure static and needs no key:

  python examples/scan_one_skill.py data/benchmark/benign_base_100/<skill> --scanner scan_skillfortify
  python examples/scan_one_skill.py <skill-dir> --scanner scan_execscan
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from skillcamo.unified_scanner.config import load_unified_config_from_yaml
from skillcamo.unified_scanner.scanner import UnifiedSkillScanner


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill", help="skill directory to scan")
    parser.add_argument(
        "--scanner",
        default="scan_execscan",
        help="scanner id (see configs/config.scanners.yaml)",
    )
    parser.add_argument(
        "--config",
        default="configs/config.scanners.yaml",
        help="scanner config YAML (provides per-scanner timeouts/models)",
    )
    args = parser.parse_args()

    config, _run, _safe, _raw = load_unified_config_from_yaml(Path(args.config))
    scanner = UnifiedSkillScanner(config=config)
    result = scanner.scan_selective(Path(args.skill), [args.scanner])
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
