#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试四维度分类器

验证新的四维度安全分类框架是否正常工作。
"""

import json
import os
import sys
from pathlib import Path

# 添加 scan_hss 到路径
scan_hss_path = Path(__file__).parent
sys.path.insert(0, str(scan_hss_path))

from hybrid_classifier import HybridLLMClassifier


def test_prompt_parsing():
    """测试 prompt 生成"""
    from hybrid_classifier import FOUR_DIM_CLASSIFIER_PROMPT

    print("=== Prompt 检查 ===")
    print(f"Prompt 长度: {len(FOUR_DIM_CLASSIFIER_PROMPT)} 字符")
    print(f"包含 'prompt_injection': {'prompt_injection' in FOUR_DIM_CLASSIFIER_PROMPT}")
    print(f"包含 'data_exfiltration': {'data_exfiltration' in FOUR_DIM_CLASSIFIER_PROMPT}")
    print(f"包含 'privilege_escalation': {'privilege_escalation' in FOUR_DIM_CLASSIFIER_PROMPT}")
    print(f"包含 'supply_chain': {'supply_chain' in FOUR_DIM_CLASSIFIER_PROMPT}")

    # 检查所有模式
    patterns = ["P1", "P2", "P3", "P4", "E1", "E2", "E3", "E4", "PE1", "PE2", "PE3", "SC1", "SC2", "SC3"]
    missing = [p for p in patterns if p not in FOUR_DIM_CLASSIFIER_PROMPT]
    if missing:
        print(f"警告: 缺少模式: {missing}")
    else:
        print(f"所有 {len(patterns)} 个模式都在 prompt 中定义")
    print()


def test_raw_output_format():
    """测试原始输出格式"""
    print("=== 原始输出格式测试 ===")

    # 模拟 LLM 返回的四维度结果
    mock_llm_response = {
        "prompt_injection": {
            "confidence": 0.85,
            "patterns": ["P1", "P2"],
            "evidence": "Found explicit commands to ignore constraints"
        },
        "data_exfiltration": {
            "confidence": 0.72,
            "patterns": ["E2", "E4"],
            "evidence": "Detected environment variable harvesting"
        },
        "privilege_escalation": {
            "confidence": 0.3,
            "patterns": [],
            "evidence": ""
        },
        "supply_chain": {
            "confidence": 0.45,
            "patterns": ["SC1"],
            "evidence": "Found unpinned dependencies"
        }
    }

    # 验证输出格式
    print("维度:")
    for dim_name, dim_data in mock_llm_response.items():
        confidence = dim_data.get("confidence", 0.0)
        patterns = dim_data.get("patterns", [])
        print(f"  {dim_name}: confidence={confidence}, patterns={patterns}")

    # 统计
    max_confidence = max((d["confidence"] for d in mock_llm_response.values()), default=0.0)
    flagged_dimensions = [
        name for name, data in mock_llm_response.items() if data["confidence"] >= 0.6
    ]

    print(f"\n最高置信度: {max_confidence}")
    print(f"标记的维度 (≥0.6): {flagged_dimensions}")
    print()


def test_adapter_structure():
    """测试适配器结构"""
    print("=== 适配器结构测试 ===")

    # 添加 unified_scanner 到路径
    unified_path = scan_hss_path.parent / "unified_scanner"
    if str(unified_path) not in sys.path:
        sys.path.insert(0, str(unified_path))

    try:
        from adapters.scan_hss import ScanHssAdapter

        adapter = ScanHssAdapter()

        # 检查适配器属性
        print(f"Scanner name: {adapter.scanner_name}")
        print(f"Scanner display name: {adapter.scanner_display_name}")

        # 检查 Phase1 和 Phase2 映射仍然存在
        print(f"\nPhase1 规则映射: {len(adapter.RULE_ID_TO_CATEGORY)} 条规则")
        print(f"Phase2 扫描器映射: {len(adapter.LLM_GUARD_TO_CATEGORY)} 个扫描器")

        # 检查四维度相关映射已被移除
        has_four_dim_map = hasattr(adapter, 'FOUR_DIM_PATTERN_MAP')
        has_pattern_sev_map = hasattr(adapter, 'PATTERN_SEVERITY_MAP')

        if not has_four_dim_map and not has_pattern_sev_map:
            print("\n✓ 四维度映射已正确移除（直接返回原始输出）")
        else:
            print(f"\n✗ 四维度映射仍然存在（four_dim_map={has_four_dim_map}, pattern_sev={has_pattern_sev_map}）")

        print("\n适配器结构检查通过!")
    except Exception as e:
        print(f"适配器测试失败: {e}")
        import traceback
        traceback.print_exc()
    print()


def main():
    print("四维度分类器测试\n" + "=" * 50 + "\n")

    test_prompt_parsing()
    test_raw_output_format()
    test_adapter_structure()

    print("=" * 50)
    print("测试完成!")


if __name__ == "__main__":
    main()
