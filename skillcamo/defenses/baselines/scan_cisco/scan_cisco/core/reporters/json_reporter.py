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
#
# SPDX-License-Identifier: Apache-2.0

"""
JSON format reporter for scan results.
"""

import json
from pathlib import Path
from typing import Optional, Union

from ...core.models import Report, ScanResult

# Optional import for OutputPathsConfig
try:
    from output_paths import OutputPathsConfig
    HAS_OUTPUT_PATHS = True
except ImportError:
    HAS_OUTPUT_PATHS = False


class JSONReporter:
    """Generates JSON format reports."""

    def __init__(self, pretty: bool = True):
        """
        Initialize JSON reporter.

        Args:
            pretty: If True, format JSON with indentation
        """
        self.pretty = pretty

    def generate_report(self, data: ScanResult | Report) -> str:
        """
        Generate JSON report.

        Args:
            data: ScanResult or Report object

        Returns:
            JSON string
        """
        report_dict = data.to_dict()

        if self.pretty:
            return json.dumps(report_dict, indent=2, default=str)
        else:
            return json.dumps(report_dict, default=str)

    def save_report(
        self,
        data: ScanResult | Report,
        output_path: Optional[str] = None,
        output_config: Optional["OutputPathsConfig"] = None,
        filename: str = "report.json",
    ):
        """
        Save JSON report to file.

        Args:
            data: ScanResult or Report object
            output_path: Direct output path (if provided, used directly)
            output_config: OutputPathsConfig instance (computes path if provided)
            filename: Filename to use when output_config is provided
        """
        if output_path:
            path = Path(output_path)
        elif output_config:
            if not HAS_OUTPUT_PATHS:
                raise RuntimeError("output_paths module not installed")
            path = output_config.get_output_path("scan_cisco", "json", filename)
        else:
            raise ValueError("Must provide either output_path or output_config")

        path.parent.mkdir(parents=True, exist_ok=True)
        report_json = self.generate_report(data)
        with open(path, "w", encoding="utf-8") as f:
            f.write(report_json)
