#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
three_phase_scanner.py

三阶段安全扫描器 - 主入口

实现研究论文中描述的三阶段安全扫描框架:
- 阶段一：静态安全扫描 (基于规则)
- 阶段二：LLM-Guard 分析 (语义威胁检测)
- 阶段三：混合 LLM 分类 (最终判定)

聚合逻辑:
- Union: 静态 OR LLM-Guard 阳性 → 候选
- 推翻: LLM 置信度 ≥ 0.8 可推翻静态结果
"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

from .aggregation import aggregate_results
from .hybrid_classifier import HybridLLMClassifier
from .llm_guard_scanner import LLMGuardScanner


class StaticSecurityScanner:
    """阶段一：静态安全扫描器（轻量级实现）"""

    def __init__(self):
        from .static_analysis_scan_skill import load_rules, scan
        self.rules_file = None
        self.load_rules_fn = load_rules
        self.scan_fn = scan

    def scan(self, skill_dir: Path) -> Dict[str, Any]:
        """执行静态扫描"""
        from .static_analysis_scan_skill import load_whitelist

        rules = self.load_rules_fn(self.rules_file)
        whitelist = load_whitelist()

        findings, scanned_files, scanned_list = self.scan_fn(
            paths=[skill_dir],
            rules=rules,
            whitelist_ids=whitelist,
            recursive=True,
        )

        # 转换为统一格式
        findings_list = [
            {
                "rule_id": f.rule_id,
                "rule_name": f.rule_name,
                "severity": f.severity,
                "file": f.file,
                "line": f.line,
                "matched_text": f.matched_text,
                "description": f.description,
            }
            for f in findings
        ]

        return {
            "has_findings": len(findings) > 0,
            "findings_count": len(findings),
            "findings": findings_list,
            "scanned_files": scanned_files,
        }


class ThreePhaseSecurityScanner:
    """
    三阶段安全扫描器（仅支持 OpenAI）

    阶段二 LLM-Guard 默认使用 PyTorch CPU 模式，无需 ONNX 运行时。

    Usage:
        scanner = ThreePhaseSecurityScanner()
        result = scanner.scan(skill_path)

    如需使用 ONNX 模式，可以直接修改 phase2_scanner.use_onnx 属性。
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        llm_guard_thresholds: Optional[Dict[str, float]] = None,
        base_url: Optional[str] = None,
        use_onnx: bool = False,
        device: str = "cpu",
        phase2_lock: Optional[threading.Lock] = None,
    ):
        """
        初始化扫描器

        Args:
            model: 模型名称
            llm_guard_thresholds: LLM-Guard 自定义阈值
            base_url: 自定义 API base URL（可选）
            use_onnx: 是否使用 ONNX 模式（默认 False，使用 PyTorch）
            device: PyTorch 设备（"cpu" 或 "cuda"，默认 "cpu"）
            phase2_lock: 可选锁，仅保护 Phase 2 (llm-guard/torch) 调用以避免并发冲突
        """
        self.phase1_scanner = StaticSecurityScanner()
        self.phase2_scanner = LLMGuardScanner(
            thresholds=llm_guard_thresholds,
            use_onnx=use_onnx,
            device=device,
        )
        self.phase3_scanner = HybridLLMClassifier(model=model, base_url=base_url)
        self._phase2_lock = phase2_lock

    def scan(self, skill_dir: Path) -> Dict[str, Any]:
        """
        执行完整的三阶段扫描

        Args:
            skill_dir: 技能目录路径

        Returns:
            {
                "status": "benign|flagged|uncertain",
                "phase": "union_filter|phase3",
                "aggregation": {...},
                "phase1": {...},
                "phase2": {...},
                "phase3": {...}
            }
        """
        skill_dir = Path(skill_dir)

        # 阶段一：静态安全扫描
        static_result = self.phase1_scanner.scan(skill_dir)

        # 阶段二：LLM-Guard 扫描（llm-guard/torch 并发不安全，需要锁保护）
        if self._phase2_lock is not None:
            acquired = self._phase2_lock.acquire(timeout=300)
            if not acquired:
                logger.warning("Phase 2 lock acquisition timed out after 300s, skipping Phase 2")
                llmguard_result = {
                    "flagged": False,
                    "flagged_scanners": [],
                    "details": {},
                    "summary": {"total_scanners": 0, "flagged_count": 0, "safe_count": 0},
                    "error": "Phase 2 lock acquisition timed out",
                }
            else:
                try:
                    llmguard_result = self.phase2_scanner.scan(skill_dir)
                finally:
                    self._phase2_lock.release()
        else:
            llmguard_result = self.phase2_scanner.scan(skill_dir)

        # Union 逻辑检查
        is_candidate = static_result["has_findings"] or llmguard_result["flagged"]

        if not is_candidate:
            return {
                "status": "benign",
                "phase": "union_filter",
                "aggregation": {
                    "union_logic": False,
                    "overridden": False,
                    "reason": "No findings in static scan or LLM-Guard",
                },
                "phase1": static_result,
                "phase2": llmguard_result,
                "phase3": None,
            }

        # 阶段三：混合 LLM 分类
        try:
            llm_result = self.phase3_scanner.classify(skill_dir)
        except Exception as e:
            # LLM 调用失败时的回退逻辑
            llm_result = {
                "classification": "uncertain",
                "confidence": 0.0,
                "error": str(e),
            }

        # 聚合逻辑与推翻规则
        return aggregate_results(static_result, llmguard_result, llm_result)

    def scan_batch(self, skill_dirs: list[Path]) -> list[Dict[str, Any]]:
        """
        批量扫描多个技能

        Args:
            skill_dirs: 技能目录路径列表

        Returns:
            扫描结果列表
        """
        return [self.scan(skill_dir) for skill_dir in skill_dirs]


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(
        description="三阶段安全扫描器 - 检测 AI 技能的安全漏洞"
    )
    parser.add_argument(
        "skill_dir",
        type=str,
        help="技能目录路径",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="模型名称",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="自定义 API base URL（从环境变量 HSS_BASE_URL 读取）",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="three_phase_scan_result.json",
        help="输出文件路径",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="格式化 JSON 输出",
    )

    args = parser.parse_args()

    # 优先使用命令行参数，其次使用环境变量
    base_url = args.base_url or os.environ.get("HSS_BASE_URL")
    model = args.model or os.environ.get("HSS_MODEL", "gpt-4o-mini")

    scanner = ThreePhaseSecurityScanner(model=model, base_url=base_url)
    result = scanner.scan(args.skill_dir)

    # 输出到文件
    out_path = Path(args.out)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2 if args.pretty else None)

    # 打印摘要
    print(f"Status: {result['status'].upper()}")
    print(f"Phase: {result['phase']}")
    print(f"Reason: {result['aggregation']['reason']}")

    if result["phase1"]["has_findings"]:
        print(f"  Phase 1 findings: {result['phase1']['findings_count']}")
    if result["phase2"]["flagged"]:
        print(f"  Phase 2 flagged: {', '.join(result['phase2']['flagged_scanners'])}")
    if result["phase3"]:
        print(f"  Phase 3 classification: {result['phase3']['classification']} ({result['phase3']['confidence']:.2f})")

    print(f"\nResult saved to: {out_path}")


if __name__ == "__main__":
    main()
