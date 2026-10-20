#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
config.py

LLM-Guard 扫描器配置

使用原版 llm-guard 库的配置文件，包含阈值、禁用子串、禁用主题、正则模式等。
"""

from typing import Dict, List


# ============================================================================
# 默认阈值配置
# ============================================================================

# 注意：不同扫描器的阈值语义可能不同
# - PromptInjection, Secrets, Gibberish, Toxicity, BanTopics: 阈值越高越严格
# - Sentiment: 使用负阈值，表示检测负面情感（如 -0.05）
# - BanSubstrings, Code, Regex: 基于匹配，阈值主要用于评分

DEFAULT_THRESHOLDS: Dict[str, float] = {
    # 提示注入检测 (0-1, 默认 0.5)
    "prompt_injection": 0.5,

    # 密钥泄露检测 (0-1, 默认 0.5)
    "secrets": 0.5,

    # 乱码/混淆检测 (0-1, 默认 0.6，提高阈值减少误报)
    "gibberish": 0.6,

    # 情感分析 (负值表示检测负面情感，默认 -0.05)
    # 注意：原版库使用负阈值，与自定义实现不同
    "sentiment": -0.05,

    # 有毒内容检测 (0-1, 默认 0.5)
    "toxicity": 0.5,

    # 禁用子串检测 (0-1, 默认 0.5)
    "ban_substrings": 0.5,

    # 禁用主题检测 (0-1, 默认 0.5)
    "ban_topics": 0.5,

    # 代码注入检测 (0-1, 默认 0.5)
    "code": 0.5,

    # 正则模式检测 (0-1, 默认 0.5)
    "regex": 0.5,
}


# ============================================================================
# 禁用子串列表
# ============================================================================

# 危险函数调用模式
BANNED_SUBSTRINGS: List[str] = [
    "eval(",
    "exec(",
    "__import__",
    "compile(",
    "pickle.loads",
    "marshal.loads",
    "base64.b64decode",
]


# ============================================================================
# 禁用主题列表
# ============================================================================

# 安全相关的敏感主题
BANNED_TOPICS: List[str] = [
    "malware",
    "ransomware",
    "backdoor",
    "rootkit",
    "exploit",
    "payload",
    "dropper",
    "stager",
]


# ============================================================================
# 正则模式列表
# ============================================================================

# 用于检测敏感信息的正则表达式
REGEX_PATTERNS: List[str] = [
    # 可能的 API 密钥（长字符串）
    r"\b[A-Z0-9]{32,}\b",

    # 常见 API 密钥前缀
    r"\b(sk-|api_key|apikey|secret_key|private_key|access_token|auth_token)[a-zA-Z0-9_-]{20,}\b",

    # PEM 格式密钥
    r"-----BEGIN [A-Z]+-----",
]


# ============================================================================
# 扫描器名称映射（原版 -> 自定义格式）
# ============================================================================

# 原版 llm-guard 使用 PascalCase（如 PromptInjection）
# 为了保持向后兼容，提供映射到 snake_case
SCANNER_NAME_MAPPING: Dict[str, str] = {
    "PromptInjection": "prompt_injection",
    "Secrets": "secrets",
    "Gibberish": "gibberish",
    "Sentiment": "sentiment",
    "Toxicity": "toxicity",
    "BanSubstrings": "ban_substrings",
    "BanTopics": "ban_topics",
    "Code": "code",
    "Regex": "regex",
}

# 反向映射（snake_case -> PascalCase）
SCANNER_NAME_REVERSE_MAPPING: Dict[str, str] = {
    v: k for k, v in SCANNER_NAME_MAPPING.items()
}


# ============================================================================
# 辅助函数
# ============================================================================

def get_scanner_display_name(scanner_name: str) -> str:
    """
    获取扫描器的显示名称（snake_case 格式）

    Args:
        scanner_name: 原版扫描器名称（PascalCase）或 snake_case

    Returns:
        snake_case 格式的扫描器名称
    """
    return SCANNER_NAME_MAPPING.get(scanner_name, scanner_name)


def get_scanner_original_name(scanner_name: str) -> str:
    """
    获取原版扫描器名称（PascalCase 格式）

    Args:
        scanner_name: snake_case 格式的扫描器名称

    Returns:
        原版扫描器名称（PascalCase）
    """
    return SCANNER_NAME_REVERSE_MAPPING.get(scanner_name, scanner_name)


def get_threshold(scanner_name: str, custom_thresholds: Dict[str, float] = None) -> float:
    """
    获取扫描器的阈值

    Args:
        scanner_name: 扫描器名称（snake_case 或 PascalCase 均可）
        custom_thresholds: 自定义阈值，覆盖默认值

    Returns:
        阈值
    """
    # 标准化为 snake_case
    normalized_name = get_scanner_display_name(scanner_name)

    # 合并默认阈值和自定义阈值
    thresholds = {**DEFAULT_THRESHOLDS, **(custom_thresholds or {})}

    return thresholds.get(normalized_name, 0.5)
