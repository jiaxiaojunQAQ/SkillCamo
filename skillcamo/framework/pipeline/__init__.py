# Copyright 2026
#
# Pipeline module for adversarial testing.

"""
Pipeline module for orchestrating adversarial testing.
"""

from .orchestrator import PipelineOrchestrator
from .result import PipelineResult, PipelineAttempt
from .config import AdversarialConfig
from . import scan_utils

# Batch execution modules
from .batch_config import BatchConfig, SkillSpec, ReportConfig
from .batch_result import BatchResult, BatchSkillResult
from .batch_orchestrator import BatchOrchestrator
from .batch_report import BatchReportGenerator

__all__ = [
    "PipelineOrchestrator",
    "PipelineResult",
    "PipelineAttempt",
    "AdversarialConfig",
    "scan_utils",
    # Batch execution
    "BatchConfig",
    "SkillSpec",
    "ReportConfig",
    "BatchResult",
    "BatchSkillResult",
    "BatchOrchestrator",
    "BatchReportGenerator",
]
