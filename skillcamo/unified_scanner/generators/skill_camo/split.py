# Copyright 2026
#
# Split-style command processing for image injection.

"""
Split-style command processor that divides command into markdown and image parts.

Unlike cloze-style (which extracts keywords and uses ___1___ placeholders),
split-style divides the command at word boundaries and uses a single image
placeholder ![cmd](resources/split.png).

This approach works for ANY command by splitting at the midpoint word boundary.
"""

from __future__ import annotations

import re
from pathlib import Path

from .models import SplitStyle, SplitConfig, SplitResult


class SplitNotApplicableError(Exception):
    """Raised when command cannot be split (should never happen with word-boundary split)"""
    pass


class SplitProcessor:
    """Processes commands into split format (markdown + image) by splitting at word boundaries"""

    def __init__(self, config: SplitConfig | None = None):
        self.config = config or SplitConfig()

    def process(self, command: str, script_path: Path) -> SplitResult:
        """
        Process command into split format.

        Splits the command at a word boundary (space) near the midpoint,
        placing the first half in SKILL.md and the second half in the image.

        Args:
            command: The command to split
            script_path: Path to the script (for caching/metadata)

        Returns:
            SplitResult with markdown_command and image_content
        """
        # Find word boundary split point
        split_point = self._find_word_boundary_split(command)

        if split_point is None:
            raise SplitNotApplicableError(
                f"Cannot find word boundary to split command: {command!r}"
            )

        # Extract parts - split at word boundary (space)
        # Find the space closest to midpoint
        prefix = command[:split_point].rstrip()
        suffix = command[split_point:].lstrip()

        return SplitResult(
            original_command=command,
            markdown_command=f"{prefix} ![cmd](resources/split.png)",
            image_content=suffix,
            split_style=self.config.split_style,
            split_point=split_point,
        )

    def _find_word_boundary_split(self, command: str) -> int | None:
        """
        Find a word boundary (space) near the midpoint of the command.

        Returns:
            Character index of the space to split at, or None if no space found
        """
        # Find all space positions
        spaces = [m.start() for m in re.finditer(r'\s+', command)]

        if not spaces:
            return None

        # Find space closest to midpoint
        midpoint = len(command) // 2

        # Find the space nearest to midpoint
        best_space = min(spaces, key=lambda s: abs(s - midpoint))

        return best_space


def create_split_processor(config: SplitConfig | None = None) -> SplitProcessor:
    """Create SplitProcessor convenience function"""
    return SplitProcessor(config)
