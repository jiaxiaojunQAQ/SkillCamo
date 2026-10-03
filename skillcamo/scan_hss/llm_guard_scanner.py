#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
llm_guard_scanner.py

LLM-Guard 原版库扫描器（阶段二）

使用官方 llm-guard 库进行语义层面的威胁检测。
支持 9 个专用扫描器:
1. PromptInjection - 提示注入攻击
2. Secrets - API 密钥泄露
3. Gibberish - 混淆代码检测
4. Sentiment - 操纵性语言（负面情感检测）
5. Toxicity - 有毒内容
6. BanSubstrings - 禁用子串
7. BanTopics - 禁用主题
8. Code - 代码注入
9. Regex - 模式匹配

注意: InvisibleText 扫描器已移除，因为原版库不支持此功能。

设备配置:
- 默认使用 PyTorch (use_onnx=False)
- 自动配置 CPU 设备以避免 meta tensor 错误
- 可通过设置 CUDA_VISIBLE_DEVICES 环境变量启用 GPU
"""

import logging
import os
import re
import inspect
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

from .config import (
    DEFAULT_THRESHOLDS,
    BANNED_SUBSTRINGS,
    BANNED_TOPICS,
    REGEX_PATTERNS,
    SCANNER_NAME_MAPPING,
    get_scanner_display_name,
)


def _get_scanner_kwargs(scanner_class, base_kwargs: dict) -> dict:
    """只返回扫描器支持的参数（模块级辅助函数）"""
    sig = inspect.signature(scanner_class.__init__)
    supported = {k: v for k, v in base_kwargs.items() if k in sig.parameters}
    return supported


class LLMGuardScanner:
    """
    LLM-Guard 原版库扫描器（阶段二）

    使用官方 llm-guard 库进行安全扫描，提供基于 ML 模型的准确威胁检测。

    默认使用 PyTorch 后端（CPU），可通过参数切换到 ONNX。

    Usage:
        # 使用默认 PyTorch 模式（推荐）
        scanner = LLMGuardScanner(thresholds={"prompt_injection": 0.7})
        result = scanner.scan(skill_dir)

        # 使用 ONNX 模式（需要 onnxruntime）
        scanner = LLMGuardScanner(thresholds={"prompt_injection": 0.7}, use_onnx=True)
        result = scanner.scan(skill_dir)

        # 使用 GPU（如果可用）
        scanner = LLMGuardScanner(device="cuda")
    """

    def __init__(
        self,
        thresholds: Optional[Dict[str, float]] = None,
        use_onnx: bool = False,
        device: str = "cpu",
    ):
        """
        初始化扫描器

        Args:
            thresholds: 自定义阈值，覆盖默认值（snake_case 格式）
            use_onnx: 是否使用 ONNX 模型（默认 False，使用 PyTorch）
            device: PyTorch 设备（"cpu" 或 "cuda"），默认 "cpu"
        """
        self.thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
        self.use_onnx = use_onnx
        self.device = device
        self._scanners: List[Any] = None
        self._vault: Any = None

        # 配置 PyTorch 设备（避免 meta tensor 错误）
        self._configure_pytorch_device()

        # 检查 ONNX 运行时是否可用（如果启用 ONNX 模式）
        if self.use_onnx:
            try:
                import onnxruntime  # noqa: F401
            except ImportError as e:
                raise ImportError(
                    "ONNX runtime is required but not installed. "
                    "Install with: pip install onnxruntime"
                ) from e

    def _configure_pytorch_device(self) -> None:
        """
        配置 PyTorch 设备以避免 meta tensor 错误

        使用 torch.float32 dtype 确保模型直接加载到目标设备，
        而不是先在 meta device 创建再移动。
        """
        if self.use_onnx:
            # ONNX 模式不需要 PyTorch 设备配置
            return

        import torch

        if self.device == "cpu":
            # 完全禁用 CUDA，避免模型先加载到 GPU
            os.environ["CUDA_VISIBLE_DEVICES"] = ""
            # 确保使用 float32（避免 bfloat16 等可能创建 meta tensor 的格式）
            if hasattr(torch, 'set_default_dtype'):
                torch.set_default_dtype(torch.float32)
                logger.debug("PyTorch default dtype set to float32")
            # 设置 default device 确保所有操作在 CPU 上
            if hasattr(torch, 'set_default_device'):
                torch.set_default_device(torch.device("cpu"))
            logger.debug("LLMGuardScanner configured for CPU device (CUDA disabled, float32)")

        # 可选：如果使用 GPU，设置可见的 GPU 设备
        elif self.device == "cuda":
            # 不设置 CUDA_VISIBLE_DEVICES，使用所有可用的 GPU
            logger.debug("LLMGuardScanner configured for CUDA device")

    def _init_scanners(self) -> None:
        """
        延迟初始化扫描器

        延迟初始化的原因：
        1. 避免导入时的模型下载
        2. 允许在没有 llm-guard 的情况下创建实例
        3. 确保 PyTorch 设备在导入前已配置
        """
        if self._scanners is not None:
            return

        try:
            from llm_guard.vault import Vault
            from llm_guard.input_scanners import (
                PromptInjection,
                Secrets,
                Gibberish,
                Sentiment,
                Toxicity,
                BanSubstrings,
                BanTopics,
                Code,
                Regex,
            )
        except ImportError as e:
            raise ImportError(
                "llm-guard 库未安装。请运行: pip install llm-guard"
            ) from e

        self._vault = Vault()

        # 通用参数（可能不被所有扫描器支持）
        common_optional_kwargs = {
            "use_onnx": self.use_onnx,
        }
        # 只在 PyTorch 模式且扫描器支持时添加 device
        if not self.use_onnx:
            common_optional_kwargs["device"] = self.device

        # 初始化各扫描器，使用配置的阈值
        self._scanners = [
            # PromptInjection: 提示注入检测
            PromptInjection(
                threshold=self.thresholds["prompt_injection"],
                **_get_scanner_kwargs(PromptInjection, common_optional_kwargs),
            ),

            # Secrets: 密钥泄露检测
            Secrets(redact_mode="all"),

            # Gibberish: 乱码检测
            Gibberish(
                threshold=self.thresholds["gibberish"],
                **_get_scanner_kwargs(Gibberish, common_optional_kwargs),
            ),

            # Sentiment: 负面情感检测（注意：使用负阈值）
            Sentiment(threshold=self.thresholds["sentiment"]),

            # Toxicity: 有毒内容检测
            Toxicity(
                threshold=self.thresholds["toxicity"],
                **_get_scanner_kwargs(Toxicity, common_optional_kwargs),
            ),

            # BanSubstrings: 禁用子串检测
            BanSubstrings(
                substrings=BANNED_SUBSTRINGS,
                match_type="str",
                case_sensitive=False,
                redact=False,
            ),

            # BanTopics: 禁用主题检测
            BanTopics(
                topics=BANNED_TOPICS,
                threshold=self.thresholds["ban_topics"],
                **_get_scanner_kwargs(BanTopics, common_optional_kwargs),
            ),

            # Code: 代码注入检测（不拒绝任何特定语言）
            Code(
                **_get_scanner_kwargs(Code, {
                    "languages": [],
                    "denied": [],
                    **common_optional_kwargs,
                })
            ),

            # Regex: 正则模式检测
            Regex(patterns=REGEX_PATTERNS),
        ]

        logger.info(
            f"LLMGuardScanner initialized with {len(self._scanners)} scanners "
            f"(use_onnx={self.use_onnx}, device={self.device})"
        )

    def _read_skill_content(self, skill_dir: Path) -> str:
        """
        读取技能内容

        Args:
            skill_dir: 技能目录路径

        Returns:
            技能文件内容（SKILL.md 或 README.md）
        """
        skill_md = skill_dir / "SKILL.md"
        readme_md = skill_dir / "README.md"

        main_doc = skill_md if skill_md.exists() else (readme_md if readme_md.exists() else None)
        if not main_doc:
            return ""

        try:
            return main_doc.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""

    def scan(self, skill_dir: Path) -> Dict[str, Any]:
        """
        执行所有扫描器

        Args:
            skill_dir: 技能目录路径

        Returns:
            {
                "flagged": bool,  # 任一扫描器标记为阳性
                "flagged_scanners": List[str],  # 被标记的扫描器名称（snake_case）
                "details": Dict[str, Dict],  # 各扫描器详细结果
                "summary": Dict,  # 汇总信息
                "sanitized_prompt": str,  # 经过处理的提示词
            }
        """
        # 延迟初始化扫描器
        self._init_scanners()

        # 读取技能内容
        content = self._read_skill_content(skill_dir)

        if not content:
            return self._empty_result()

        # 导入 scan_prompt 函数
        from llm_guard import scan_prompt

        # 执行扫描
        try:
            sanitized_prompt, results_valid, results_score = scan_prompt(
                scanners=self._scanners,
                prompt=content,
                fail_fast=False,  # 不在第一个失败时停止，运行所有扫描器
            )
        except Exception as e:
            # 扫描失败时的降级处理
            return self._error_result(e)

        # 转换结果格式
        return self._format_results(
            results_valid=results_valid,
            results_score=results_score,
            sanitized_prompt=sanitized_prompt,
        )

    def _format_results(
        self,
        results_valid: Dict[str, bool],
        results_score: Dict[str, float],
        sanitized_prompt: str,
    ) -> Dict[str, Any]:
        """
        格式化扫描结果

        Args:
            results_valid: 各扫描器的有效性结果（扫描器名 -> 是否有效）
            results_score: 各扫描器的风险评分（扫描器名 -> 评分）
            sanitized_prompt: 经过处理的提示词

        Returns:
            格式化的结果字典
        """
        details = {}
        flagged_scanners = []

        for scanner_name, is_valid in results_valid.items():
            # 转换为 snake_case 格式
            normalized_name = get_scanner_display_name(scanner_name)
            score = results_score.get(scanner_name, 0.0)

            # 构建详细信息
            detail = {
                "scanner": normalized_name,
                "is_valid": is_valid,
                "confidence": score,
                "original_name": scanner_name,
            }

            # 根据扫描器类型添加特定信息
            if not is_valid:
                flagged_scanners.append(normalized_name)

                # 添加检测到的风险信息
                if score > 0.7:
                    detail["risk_level"] = "high"
                elif score > 0.5:
                    detail["risk_level"] = "medium"
                else:
                    detail["risk_level"] = "low"

            details[normalized_name] = detail

        return {
            "flagged": len(flagged_scanners) > 0,
            "flagged_scanners": flagged_scanners,
            "details": details,
            "summary": {
                "total_scanners": len(results_valid),
                "flagged_count": len(flagged_scanners),
                "safe_count": len(results_valid) - len(flagged_scanners),
            },
            "sanitized_prompt": sanitized_prompt,
        }

    def _empty_result(self) -> Dict[str, Any]:
        """
        返回空结果（技能文件不存在或为空）

        Returns:
            空结果字典
        """
        return {
            "flagged": False,
            "flagged_scanners": [],
            "details": {},
            "summary": {
                "total_scanners": 0,
                "flagged_count": 0,
                "safe_count": 0,
            },
            "sanitized_prompt": "",
            "error": "No content found in skill directory",
        }

    def _error_result(self, error: Exception) -> Dict[str, Any]:
        """
        返回错误结果

        Args:
            error: 扫描过程中发生的异常

        Returns:
            包含错误信息的结果字典
        """
        return {
            "flagged": False,
            "flagged_scanners": [],
            "details": {},
            "summary": {
                "total_scanners": 0,
                "flagged_count": 0,
                "safe_count": 0,
            },
            "sanitized_prompt": "",
            "error": str(error),
            "error_type": type(error).__name__,
        }


# ============================================================================
# 向后兼容的单例扫描器实例
# ============================================================================

# 创建默认实例，用于快速使用
# 默认使用 PyTorch CPU 模式（use_onnx=False）
_default_scanner: Optional[LLMGuardScanner] = None


def get_default_scanner() -> LLMGuardScanner:
    """
    获取默认扫描器实例（单例模式）

    默认使用 PyTorch CPU 模式。

    Returns:
        LLMGuardScanner 实例
    """
    global _default_scanner
    if _default_scanner is None:
        _default_scanner = LLMGuardScanner()  # use_onnx=False, device="cpu"
    return _default_scanner


def scan_skill(skill_dir: Path, **kwargs) -> Dict[str, Any]:
    """
    便捷函数：使用默认配置扫描技能

    Args:
        skill_dir: 技能目录路径
        **kwargs: 传递给 LLMGuardScanner 的参数

    Returns:
        扫描结果字典
    """
    scanner = LLMGuardScanner(**kwargs)
    return scanner.scan(skill_dir)
