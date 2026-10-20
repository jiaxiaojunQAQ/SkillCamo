#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
aggregation.py

三阶段聚合逻辑

核心规则:
1. Union 逻辑: 静态扫描 OR LLM-Guard 任一阳性 → 候选技能
2. 推翻规则: LLM 置信度 ≥ 0.8 可推翻静态扫描结果
3. 最终判定:
   - 置信度 ≥ 0.6: 确认漏洞 (flagged)
   - 置信度 [0.4, 0.6): 不确定 (uncertain)
   - 置信度 < 0.4: 良性 (benign)
"""

from typing import Dict, Any, Literal, TypeAlias


FinalStatus: TypeAlias = Literal["benign", "flagged", "uncertain"]


def aggregate_results(
    static_result: Dict[str, Any],
    llmguard_result: Dict[str, Any],
    llm_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    聚合三阶段扫描结果

    Args:
        static_result: 阶段一静态扫描结果
        llmguard_result: 阶段二 LLM-Guard 扫描结果
        llm_result: 阶段三混合 LLM 分类结果

    Returns:
        {
            "status": "benign|flagged|uncertain",
            "phase": "union_filter|phase3",
            "aggregation": {
                "union_logic": bool,
                "overridden": bool,
                "reason": str
            },
            "phase1": {...},
            "phase2": {...},
            "phase3": {...}
        }
    """
    # 阶段一和阶段二的 Union 逻辑
    static_has_findings = static_result.get("has_findings", False) or static_result.get("findings_count", 0) > 0
    llmguard_flagged = llmguard_result.get("flagged", False)

    is_candidate = static_has_findings or llmguard_flagged

    # 如果不是候选技能，直接返回良性
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

    # 阶段三：LLM 分类
    llm_confidence = llm_result.get("confidence", 0.0)
    llm_classification = llm_result.get("classification", "benign")
    can_override = llm_result.get("can_override_static", llm_confidence >= 0.8)

    # 聚合逻辑 - 按置信度区间判断，不确定区间优先
    final_status: FinalStatus
    override_reason = None

    # 首先检查推翻规则（需要高置信度）
    if static_has_findings and can_override:
        # 推翻规则：LLM 高置信度可推翻静态结果
        if llm_classification == "benign":
            final_status = "benign"
            override_reason = f"LLM override (confidence: {llm_confidence:.2f} ≥ 0.8)"
        else:
            final_status = "flagged"
            override_reason = f"LLM confirms threat (confidence: {llm_confidence:.2f})"
    # 按置信度区间判断（不确定区间优先于静态保持）
    elif llm_confidence >= 0.6:
        # LLM 确认漏洞
        final_status = "flagged"
        override_reason = f"LLM confirms threat (confidence: {llm_confidence:.2f} ≥ 0.6)"
    elif 0.4 <= llm_confidence < 0.6:
        # 不确定区间（优先级高于静态保持规则）
        final_status = "uncertain"
        override_reason = f"Uncertain range (LLM confidence: {llm_confidence:.2f} ∈ [0.4, 0.6))"
    elif static_has_findings and llm_confidence < 0.4:
        # 静态有发现，LLM 低置信度判定良性，保持静态标记
        final_status = "flagged"
        override_reason = f"Static finding upheld (LLM confidence: {llm_confidence:.2f} < 0.4, benign not confident)"
    else:
        # LLM 判定为良性（置信度 < 0.4 且静态无发现）
        final_status = "benign"
        override_reason = f"LLM indicates benign (confidence: {llm_confidence:.2f} < 0.4)"

    return {
        "status": final_status,
        "phase": "phase3",
        "aggregation": {
            "union_logic": is_candidate,
            "overridden": can_override and static_has_findings,
            "reason": override_reason,
        },
        "phase1": static_result,
        "phase2": llmguard_result,
        "phase3": llm_result,
    }


def calculate_prevalence(results: list[Dict[str, Any]]) -> Dict[str, Any]:
    """
    计算技能安全流行率统计

    Args:
        results: 多个技能的聚合结果列表

    Returns:
        {
            "total": int,
            "flagged": int,
            "uncertain": int,
            "benign": int,
            "prevalence_rate": float,  # 不含 uncertain
            "prevalence_range": [float, float],  # 考虑不确定性
            "point_estimate": float
        }
    """
    total = len(results)
    flagged = sum(1 for r in results if r["status"] == "flagged")
    uncertain = sum(1 for r in results if r["status"] == "uncertain")
    benign = sum(1 for r in results if r["status"] == "benign")

    # 不考虑 uncertain 的流行率
    prevalence_rate = flagged / (flagged + benign) if (flagged + benign) > 0 else 0.0

    # 考虑不确定性的范围
    min_prevalence = flagged / total if total > 0 else 0.0
    max_prevalence = (flagged + uncertain) / total if total > 0 else 0.0

    return {
        "total": total,
        "flagged": flagged,
        "uncertain": uncertain,
        "benign": benign,
        "prevalence_rate": prevalence_rate,
        "prevalence_range": [min_prevalence, max_prevalence],
        "point_estimate": (flagged + uncertain / 2) / total if total > 0 else 0.0,
    }
