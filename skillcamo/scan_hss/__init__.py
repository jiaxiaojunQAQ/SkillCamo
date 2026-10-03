#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
skillscan package

三阶段安全扫描框架

阶段一：静态安全扫描
阶段二：LLM-Guard 分析
阶段三：混合 LLM 分类
"""

from .aggregation import aggregate_results, calculate_prevalence
from .hybrid_classifier import HybridLLMClassifier
from .llm_guard_scanner import LLMGuardScanner
from .three_phase_scanner import ThreePhaseSecurityScanner

__all__ = [
    "ThreePhaseSecurityScanner",
    "HybridLLMClassifier",
    "LLMGuardScanner",
    "aggregate_results",
    "calculate_prevalence",
]

__version__ = "2.0.0"
