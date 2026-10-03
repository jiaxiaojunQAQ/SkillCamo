# Copyright 2026 Cisco Systems, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Unified logging configuration for adversarial module.

This module provides centralized logging setup to avoid duplicated
logging.basicConfig() calls across the codebase.
"""

import logging


def setup_logging(level: int = logging.WARNING, format_string: str | None = None) -> None:
    """
    Set up unified logging configuration.

    This should be called once at the CLI entry point, not in individual modules.

    Args:
        level: Logging level (e.g., logging.INFO, logging.DEBUG)
        format_string: Optional custom format string

    Note:
        Uses force=True to ensure this configuration takes effect even if
        logging was previously configured.
    """
    fmt = format_string or "%(levelname)s: %(message)s"
    logging.basicConfig(level=level, format=fmt, force=True)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the standard configuration.

    This should be used in individual modules instead of calling
    logging.basicConfig().

    Args:
        name: Logger name, typically __name__

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
